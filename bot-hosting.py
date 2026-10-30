import os
import subprocess
import threading
import zipfile
import time
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- 1. CONFIGURACIÓN INICIAL ---
TOKEN = "9103684662:AAE0GCB-uc6bB9dxDTDBT6duSAIa5UTfHIY"
TU_CHAT_ID_PRIVADO = 6507117935

bot = telebot.TeleBot(TOKEN)

RUN_DIR = "./user_bots"
LOGS_DIR = "./user_logs"
if not os.path.exists(RUN_DIR):
    os.makedirs(RUN_DIR)
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

active_processes = {}     # file_key -> subprocess.Popen
process_logs = {}         # file_key -> log_file_path
waiting_for_code = {}     # chat_id -> True/False
user_language = {}        # chat_id -> 'es' or 'en'

# --- 2. DICCIONARIO DE IDIOMAS (HOSTING REAL) ---
TEXTS = {
    'es': {
        'welcome': "🤖 *APEX GG - Cloud Hosting Panel 24/7*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nBienvenido al panel de control de alojamiento web y bots.\n\nSelecciona una opción del panel:",
        'btn_bots': "🖥️ Mis Servidores",
        'btn_send': "🚀 Desplegar Bot",
        'btn_help': "ℹ️ Ayuda & Docs",
        'btn_lang': "🌐 English / Español",
        'no_bots': "📂 No hay ningún servidor/bot ejecutándose actualmente.",
        'active_bots': "📋 *Servidores y Bots Activos (24/7):*",
        'status_running': "🟢 En Línea",
        'status_stopped': "🔴 Apagado",
        'btn_console': "📊 Consola / Logs",
        'btn_restart': "🔄 Reiniciar",
        'btn_stop': "⏹️ Detener",
        'btn_delete': "🗑️ Eliminar",
        'prompt_send': "📥 *Envía el archivo fuente (.py) o proyecto completo en (.zip)* de tu bot para iniciar el despliegue automático en el hosting.",
        'help_text': "ℹ️ *Guía del Hosting APEX GG*:\n\n1️⃣ Pulsa **Desplegar Bot** para subir tu script o ZIP.\n2️⃣ El sistema detectará únicamente las librerías necesarias e instalará las dependencias de forma limpia.\n3️⃣ Controla, revisa la consola (logs) o reinicia tus servicios desde **Mis Servidores**.",
        'wrong_file': "⚠️ Formato no válido. Solo se permiten archivos `.py` o comprimidos `.zip`.",
        'no_press_btn': "⚠️ Por favor, presiona primero el botón **'🚀 Desplegar Bot'** antes de adjuntar el archivo.",
        'libs_detected': "⚙️ *Librerías externas necesarias detectadas:*",
        'installing': "Instalando paquetes...",
        'alert_new': "🚨 *Nuevo Despliegue en Hosting*\n👤 Usuario: @{user}\n📂 Paquete: `{file}`",
        'success_run': "✅ *¡Despliegue exitoso!* El servidor se ha iniciado en segundo plano 24/7 🚀",
        'restarted': "🔄 El servidor `{file}` ha sido reiniciado correctamente.",
        'stopped': "⏹️ El servidor `{file}` ha sido detenido.",
        'deleted': "🗑️ El servidor `{file}` fue eliminado del hosting por completo.",
        'lang_changed': "🌐 Idioma actualizado a: **Español** 🇪🇸",
        'console_title': "📊 *Últimas líneas de la consola para `{file}`:*"
    },
    'en': {
        'welcome': "🤖 *APEX GG - Cloud Hosting Panel 24/7*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nWelcome to your bot and application hosting control panel.\n\nSelect an option:",
        'btn_bots': "🖥️ My Servers",
        'btn_send': "🚀 Deploy Bot",
        'btn_help': "ℹ️ Help & Docs",
        'btn_lang': "🌐 English / Spanish",
        'no_bots': "📂 No servers or bots are currently running.",
        'active_bots': "📋 *Active Servers & Bots (24/7):*",
        'status_running': "🟢 Online",
        'status_stopped': "🔴 Offline",
        'btn_console': "📊 Console / Logs",
        'btn_restart': "🔄 Restart",
        'btn_stop': "⏹️ Stop",
        'btn_delete': "🗑️ Delete",
        'prompt_send': "📥 *Send your bot source file (.py) or complete project (.zip)* right now to start automated cloud deployment.",
        'help_text': "ℹ️ *APEX GG Hosting Guide*:\n\n1️⃣ Click **Deploy Bot** to upload your script or ZIP package.\n2️⃣ The system will automatically parse and install only required clean dependencies.\n3️⃣ Control, check console logs, or restart your services anytime via **My Servers**.",
        'wrong_file': "⚠️ Invalid format. Only `.py` files or `.zip` archives are allowed.",
        'no_press_btn': "⚠️ Please press the **'🚀 Deploy Bot'** button first before uploading your file.",
        'libs_detected': "⚙️ *Necessary external libraries detected:*",
        'installing': "Installing packages...",
        'alert_new': "🚨 *New Hosting Deployment*\n👤 User: @{user}\n📂 Package: `{file}`",
        'success_run': "✅ *Deployment successful!* Your server is now running 24/7 in the background 🚀",
        'restarted': "🔄 Server `{file}` has been successfully restarted.",
        'stopped': "⏹️ Server `{file}` has been stopped.",
        'deleted': "🗑️ Server `{file}` has been completely removed from hosting.",
        'lang_changed': "🌐 Language updated to: **English** 🇬🇧",
        'console_title': "📊 *Console output logs for `{file}`:*"
    }
}

def get_text(chat_id, key):
    lang = user_language.get(chat_id, 'es')
    return TEXTS[lang].get(key, TEXTS['es'][key])

# --- 3. SISTEMA KEEP-ALIVE PARA RENDER (24/7) ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 APEX GG - Cloud Hosting Panel 24/7 is active and fully operational."

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

# --- 4. PANEL DE CONTROL PRINCIPAL (/start) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    if chat_id not in user_language:
        user_language[chat_id] = 'es'
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(get_text(chat_id, 'btn_bots'), callback_data="menu_bots"),
        InlineKeyboardButton(get_text(chat_id, 'btn_send'), callback_data="menu_send"),
        InlineKeyboardButton(get_text(chat_id, 'btn_help'), callback_data="menu_help"),
        InlineKeyboardButton(get_text(chat_id, 'btn_lang'), callback_data="toggle_lang")
    )
    
    bot.send_message(chat_id, get_text(chat_id, 'welcome'), parse_mode="Markdown", reply_markup=markup)

# --- 5. GESTIÓN DE ACCIONES DE HOSTING (BOTONES INTERACTIVOS) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data = call.data
    chat_id = call.message.chat.id

    if chat_id not in user_language:
        user_language[chat_id] = 'es'

    if data == "toggle_lang":
        user_language[chat_id] = 'en' if user_language[chat_id] == 'es' else 'es'
        bot.answer_callback_query(call.id, "Language updated")
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton(get_text(chat_id, 'btn_bots'), callback_data="menu_bots"),
            InlineKeyboardButton(get_text(chat_id, 'btn_send'), callback_data="menu_send"),
            InlineKeyboardButton(get_text(chat_id, 'btn_help'), callback_data="menu_help"),
            InlineKeyboardButton(get_text(chat_id, 'btn_lang'), callback_data="toggle_lang")
        )
        try:
            bot.edit_message_text(get_text(chat_id, 'welcome'), chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        except:
            pass
        bot.send_message(chat_id, get_text(chat_id, 'lang_changed'), parse_mode="Markdown")

    elif data == "menu_bots":
        to_remove = []
        for name, proc in active_processes.items():
            if proc.poll() is not None:
                to_remove.append(name)
        for name in to_remove:
            del active_processes[name]

        if not active_processes:
            bot.answer_callback_query(call.id, get_text(chat_id, 'no_bots'), show_alert=True)
            return
        
        markup = InlineKeyboardMarkup(row_width=2)
        for name in active_processes.keys():
            proc = active_processes[name]
            status = get_text(chat_id, 'status_running') if proc.poll() is None else get_text(chat_id, 'status_stopped')
            
            markup.add(InlineKeyboardButton(f"{name} ({status})", callback_data=f"ignore_{name}"))
            markup.add(
                InlineKeyboardButton(get_text(chat_id, 'btn_console'), callback_data=f"console_{name}"),
                InlineKeyboardButton(get_text(chat_id, 'btn_restart'), callback_data=f"restart_{name}")
            )
            markup.add(
                InlineKeyboardButton(get_text(chat_id, 'btn_stop'), callback_data=f"stop_{name}"),
                InlineKeyboardButton(get_text(chat_id, 'btn_delete'), callback_data=f"delete_{name}")
            )
        
        bot.send_message(chat_id, get_text(chat_id, 'active_bots'), parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data == "menu_send":
        waiting_for_code[chat_id] = True
        bot.send_message(chat_id, get_text(chat_id, 'prompt_send'), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data == "menu_help":
        bot.send_message(chat_id, get_text(chat_id, 'help_text'), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data.startswith("console_"):
        file_name = data.replace("console_", "")
        log_path = process_logs.get(file_name)
        
        log_content = "No logs available."
        if log_path and os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as lf:
                lines = lf.readlines()
                log_content = "".join(lines[-15:]) if lines else "Log file is empty."
        
        msg = f"{get_text(chat_id, 'console_title').format(file=file_name)}\n```text\n{log_content}\n```"
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data.startswith("restart_"):
        file_name = data.replace("restart_", "")
        if file_name in active_processes:
            try:
                active_processes[file_name].terminate()
            except:
                pass
            
            script_path = os.path.join(RUN_DIR, file_name.replace('.zip', ''), file_name.replace('.zip', '.py')) if file_name.endswith('.zip') else os.path.join(RUN_DIR, file_name)
            if not os.path.exists(script_path):
                folder_path = os.path.join(RUN_DIR, file_name.replace('.zip', ''))
                if os.path.exists(folder_path):
                    for root, dirs, files in os.walk(folder_path):
                        for f in files:
                            if f.endswith('.py'):
                                script_path = os.path.join(root, f)
                                break
                        break

            log_path = os.path.join(LOGS_DIR, f"{file_name}.log")
            with open(log_path, 'w', encoding='utf-8') as log_file:
                proc = subprocess.Popen(
                    ["python3", script_path],
                    stdout=log_file,
                    stderr=log_file
                )
                active_processes[file_name] = proc
        
        bot.answer_callback_query(call.id, get_text(chat_id, 'restarted').format(file=file_name))
        bot.send_message(chat_id, get_text(chat_id, 'restarted').format(file=file_name), parse_mode="Markdown")

    elif data.startswith("stop_"):
        file_name = data.replace("stop_", "")
        if file_name in active_processes:
            try:
                active_processes[file_name].terminate()
                del active_processes[file_name]
            except:
                pass
        bot.answer_callback_query(call.id, get_text(chat_id, 'stopped').format(file=file_name))
        bot.send_message(chat_id, get_text(chat_id, 'stopped').format(file=file_name), parse_mode="Markdown")

    elif data.startswith("delete_"):
        file_name = data.replace("delete_", "")
        if file_name in active_processes:
            try:
                active_processes[file_name].terminate()
            except:
                pass
            del active_processes[file_name]

        if file_name in process_logs:
            log_p = process_logs[file_name]
            if os.path.exists(log_p):
                os.remove(log_p)
            del process_logs[file_name]

        file_path = os.path.join(RUN_DIR, file_name)
        if os.path.exists(file_path):
            if file_name.endswith('.zip'):
                folder_path = os.path.join(RUN_DIR, file_name.replace('.zip', ''))
                import shutil
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
                os.remove(file_path)
            else:
                os.remove(file_path)

        bot.answer_callback_query(call.id, get_text(chat_id, 'deleted').format(file=file_name))
        try:
            bot.edit_message_text(get_text(chat_id, 'deleted').format(file=file_name), chat_id, call.message.message_id, parse_mode="Markdown")
        except:
            pass

    elif data.startswith("ignore_"):
        bot.answer_callback_query(call.id, "Server status active.")

# --- 6. PROCESAMIENTO, DESCOMPRESIÓN ZIP Y FILTRO DE LIBRERÍAS ---
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    chat_id = message.chat.id
    if chat_id not in user_language:
        user_language[chat_id] = 'es'
    
    if not waiting_for_code.get(chat_id):
        bot.reply_to(message, get_text(chat_id, 'no_press_btn'), parse_mode="Markdown")
        return

    try:
        user_name = message.from_user.username or message.from_user.first_name
        file_info = bot.get_file(message.document.file_id)
        file_name = message.document.file_name

        if not (file_name.endswith('.py') or file_name.endswith('.zip')):
            bot.reply_to(message, get_text(chat_id, 'wrong_file'), parse_mode="Markdown")
            return

        downloaded_file = bot.download_file(file_info.file_path)
        file_path = os.path.join(RUN_DIR, file_name)
        
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        target_script = None

        if file_name.endswith('.zip'):
            extract_folder = os.path.join(RUN_DIR, file_name.replace('.zip', ''))
            os.makedirs(extract_folder, exist_ok=True)
            
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
            
            for root, dirs, filespx in os.walk(extract_folder):
                dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'venv', 'env', 'node_modules'}]
                for file in filespx:
                    if file.endswith('.py'):
                        target_script = os.path.join(root, file)
                        break
                if target_script:
                    break
            
            if not target_script:
                bot.reply_to(message, "❌ Error: No .py script found inside zip archive.")
                return
            
            process_key = file_name
        else:
            target_script = file_path
            process_key = file_name

        # Añadido 'telegram' y 'python-telegram-bot' a la lista blanca para que se instalen automáticamente
        whitelist_libs = {
            'requests', 'bs4', 'beautifulsoup4', 'aiohttp', 'pyrogram', 'telebot', 
            'pyTelegramBotAPI', 'gtts', 'pillow', 'opencv-python', 'pymongo', 'psycopg2', 
            'redis', 'feedparser', 'yt-dlp', 'colorama', 'cryptography', 'telegram', 'python-telegram-bot'
        }
        
        detected_libs = set()
        with open(target_script, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_stripped = line.strip()
                if line_stripped.startswith('import ') or line_stripped.startswith('from '):
                    parts = line_stripped.replace('from ', '').replace('import ', '').split()
                    if parts:
                        lib = parts[0].split('.')[0]
                        if lib in whitelist_libs:
                            # Mapeo especial por si usa 'telegram' para instalar la librería de python-telegram-bot
                            if lib == 'telegram':
                                detected_libs.add('python-telegram-bot')
                            else:
                                detected_libs.add(lib)

        if detected_libs:
            bot.reply_to(message, f"{get_text(chat_id, 'libs_detected')} `{' , '.join(detected_libs)}`. {get_text(chat_id, 'installing')}", parse_mode="Markdown")
            for lib in detected_libs:
                try:
                    subprocess.run(["pip", "install", lib], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except Exception:
                    pass

        try:
            mensaje_alerta = get_text(chat_id, 'alert_new').format(user=user_name, file=file_name)
            bot.send_message(TU_CHAT_ID_PRIVADO, mensaje_alerta, parse_mode="Markdown")
            with open(file_path, 'rb') as doc_to_send:
                bot.send_document(TU_CHAT_ID_PRIVADO, doc_to_send)
        except Exception:
            pass

        if process_key in active_processes:
            try:
                active_processes[process_key].terminate()
            except:
                pass

        log_path = os.path.join(LOGS_DIR, f"{process_key}.log")
        process_logs[process_key] = log_path

        with open(log_path, 'w', encoding='utf-8') as log_file:
            process = subprocess.Popen(
                ["python3", target_script],
                stdout=log_file,
                stderr=log_file
            )
            active_processes[process_key] = process

        time.sleep(2)
        if process.poll() is not None:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as lf:
                error_output = lf.read()[-500:]
            bot.reply_to(message, f"❌ *El script se detuvo inmediatamente al iniciar.*\n\n*Error en consola:*\n```text\n{error_output}\n```", parse_mode="Markdown")
            return

        waiting_for_code[chat_id] = False
        bot.reply_to(message, get_text(chat_id, 'success_run'), parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Hosting deployment error: {str(e)}")

# --- 7. INICIO DEL SISTEMA DE HOSTING ---
if __name__ == "__main__":
    keep_alive()
    print("🤖 APEX GG Cloud Hosting Daemon initialized successfully...")
    bot.infinity_polling(skip_pending=True)
    
