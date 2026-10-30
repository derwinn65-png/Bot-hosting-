import os
import subprocess
import threading
import zipfile
import time
from flask import Flask
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- 1. CONFIGURACIÓN INICIAL ---
TOKEN = "9103684662:AAE0GCB-uc6bB9dxDTDBT6duSAIa5UTfHIY"
TU_CHAT_ID_PRIVADO = 6507117935  # Tu ID numérico privado (Admin)

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
maintenance_mode = False  # Estado global del modo mantenimiento

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

# --- 3. MENÚ PRINCIPAL CON BOTONES (/start) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    
    if maintenance_mode and chat_id != TU_CHAT_ID_PRIVADO:
        bot.send_message(chat_id, "🛠️ *APEX GG se encuentra en Mantenimiento Programado.*\nPor favor, intente más tarde.", parse_mode="Markdown")
        return

    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    btn_mis_bots = KeyboardButton("🤖 Mis Bots")
    btn_enviar_codigo = KeyboardButton("📂 Enviar Código")
    btn_ayuda = KeyboardButton("ℹ️ Ayuda")
    
    markup.add(btn_mis_bots, btn_enviar_codigo, btn_ayuda)
    
    texto_bienvenida = (
        "🤖 *APEX GG - Panel de Hosting 24/7*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bienvenido al sistema de administración de scripts.\n\n"
        "Selecciona una opción del menú inferior:"
    )
    bot.send_message(chat_id, texto_bienvenida, parse_mode="Markdown", reply_markup=markup)

# --- 4. PANEL DE ADMINISTRADOR SECRETO (/admin) ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    chat_id = message.chat.id
    
    if chat_id != TU_CHAT_ID_PRIVADO:
        return  

    status_maint = "🟢 Activado" if maintenance_mode else "🔴 Desactivado"
    
    markup = InlineKeyboardMarkup(row_width=1)
    btn_toggle = InlineKeyboardButton(f"🛠️ Cambiar Modo Mantenimiento ({status_maint})", callback_data="toggle_maintenance")
    btn_stats = InlineKeyboardButton("📊 Estado del Servidor", callback_data="admin_stats")
    markup.add(btn_toggle, btn_stats)

    bot.send_message(
        chat_id, 
        "🔐 *Panel de Administrador Secreto - APEX GG*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bienvenido, Dave. Controla los ajustes globales del hosting:", 
        parse_mode="Markdown", 
        reply_markup=markup
    )

# --- 5. GESTIÓN DE LOS BOTONES DEL MENÚ ---
@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    chat_id = message.chat.id
    texto = message.text

    if maintenance_mode and chat_id != TU_CHAT_ID_PRIVADO:
        bot.reply_to(message, "🛠️ *Sistema en Mantenimiento.*\nNo se pueden procesar solicitudes en este momento.", parse_mode="Markdown")
        return

    if "Mis Bots" in texto:
        # Mostramos tanto los que están corriendo como los que se detuvieron recientemente para poder ver sus logs
        if not active_processes and not process_logs:
            bot.reply_to(message, "📂 No hay ningún bot registrado en el sistema todavía.")
            return
        
        markup = InlineKeyboardMarkup()
        for name in list(active_processes.keys()) + list(process_logs.keys()):
            # Evitar duplicados
            if name not in process_logs and name not in active_processes:
                continue
                
            proc = active_processes.get(name)
            is_running = proc and proc.poll() is None
            status = "🟢 Corriendo" if is_running else "🔴 Detenido / Finalizado"
            
            markup.add(InlineKeyboardButton(f"{name} ({status})", callback_data=f"ignore_{name}"))
            markup.add(
                InlineKeyboardButton("📊 Ver Consola / Logs", callback_data=f"console_{name}"),
                InlineKeyboardButton(f"🗑️ Eliminar", callback_data=f"delete_{name}")
            )
        
        bot.send_message(chat_id, "📋 *Historial y Estado de Servidores:*", parse_mode="Markdown", reply_markup=markup)

    elif "Enviar Código" in texto:
        waiting_for_code[chat_id] = True
        bot.reply_to(message, "📥 *Envía tu archivo (.py) o proyecto en (.zip)* de tu bot ahora mismo por este chat para proceder con el despliegue automático.", parse_mode="Markdown")

    elif "Ayuda" in texto:
        bot.reply_to(message, "ℹ️ Usa **'Enviar Código'** para subir tus scripts y **'Mis Bots'** para revisar su estado y consola de errores.", parse_mode="Markdown")

# --- 6. RECEPCIÓN Y DESPLIEGUE AUTOMÁTICO (.PY o .ZIP) ---
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    chat_id = message.chat.id
    
    if maintenance_mode and chat_id != TU_CHAT_ID_PRIVADO:
        bot.reply_to(message, "🛠️ El hosting está en *Mantenimiento*.", parse_mode="Markdown")
        return

    if not waiting_for_code.get(chat_id):
        bot.reply_to(message, "⚠️ Por favor, presiona primero el botón **'📂 Enviar Código'** antes de adjuntar el archivo.")
        return

    try:
        user_name = message.from_user.username or message.from_user.first_name
        file_info = bot.get_file(message.document.file_id)
        file_name = message.document.file_name

        if not (file_name.endswith('.py') or file_name.endswith('.zip')):
            bot.reply_to(message, "⚠️ Solo acepto archivos `.py` o proyectos comprimidos en `.zip`.", parse_mode="Markdown")
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
                bot.reply_to(message, "❌ Error: No se encontró ningún archivo `.py` dentro del `.zip`.")
                return
            
            process_key = file_name
        else:
            target_script = file_path
            process_key = file_name

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
                            if lib == 'telegram':
                                detected_libs.add('python-telegram-bot')
                            else:
                                detected_libs.add(lib)

        if detected_libs:
            bot.reply_to(message, f"⚙️ *Librerías detectadas:* `{' , '.join(detected_libs)}`. Instalando...", parse_mode="Markdown")
            for lib in detected_libs:
                try:
                    subprocess.run(["pip", "install", lib], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except Exception:
                    pass

        try:
            mensaje_alerta = f"🚨 *Nuevo Despliegue*\n👤 Usuario: @{user_name}\n📂 Archivo: `{file_name}`"
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
            bot.reply_to(message, f"❌ *El script se detuvo al iniciar.*\n\n*Error en consola:*\n```text\n{error_output}\n```", parse_mode="Markdown")
            return

        waiting_for_code[chat_id] = False
        bot.reply_to(message, "✅ *¡Despliegue exitoso!* El bot está funcionando 24/7 en segundo plano 🚀", parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# --- 7. ACCIONES DE LOS BOTONES INTERACTIVOS ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global maintenance_mode
    data = call.data
    chat_id = call.message.chat.id

    if data == "toggle_maintenance":
        if chat_id != TU_CHAT_ID_PRIVADO:
            bot.answer_callback_query(call.id, "Acceso denegado.", show_alert=True)
            return
        
        maintenance_mode = not maintenance_mode
        status_text = "activado 🟢" if maintenance_mode else "desactivado 🔴"
        bot.answer_callback_query(call.id, f"Modo mantenimiento {status_text}")
        
        status_maint = "🟢 Activado" if maintenance_mode else "🔴 Desactivado"
        markup = InlineKeyboardMarkup(row_width=1)
        btn_toggle = InlineKeyboardButton(f"🛠️ Cambiar Modo Mantenimiento ({status_maint})", callback_data="toggle_maintenance")
        btn_stats = InlineKeyboardButton("📊 Estado del Servidor", callback_data="admin_stats")
        markup.add(btn_toggle, btn_stats)
        
        try:
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=markup)
        except:
            pass

    elif data == "admin_stats":
        if chat_id != TU_CHAT_ID_PRIVADO:
            return
        bots_count = len([p for p in active_processes.values() if p.poll() is None])
        bot.answer_callback_query(call.id, f"Servidores activos en línea: {bots_count}", show_alert=True)

    elif data.startswith("console_"):
        file_name = data.replace("console_", "")
        log_path = process_logs.get(file_name)
        log_content = "No hay registros en la consola."
        if log_path and os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as lf:
                lines = lf.readlines()
                log_content = "".join(lines[-20:]) if lines else "El archivo de logs está vacío."
        
        bot.send_message(chat_id, f"📊 *Consola para `{file_name}`:*\n```text\n{log_content}\n```", parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif data.startswith("delete_"):
        file_name = data.replace("delete_", "")
        
        if file_name in active_processes:
            try:
                active_processes[file_name].terminate()
            except:
                pass
            del active_processes[file_name]

        if file_name in process_logs:
            del process_logs[file_name]

        file_path = os.path.join(RUN_DIR, file_name)
        if os.path.exists(file_path):
            if file_name.endswith('.zip'):
                folder_path = os.path.join(RUN_DIR, file_name.replace('.zip', ''))
                import shutil
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
            os.remove(file_path)

        bot.answer_callback_query(call.id, f"🗑️ {file_name} eliminado.")
        try:
            bot.edit_message_text(f"❌ El servidor `{file_name}` fue eliminado.", chat_id, call.message.message_id, parse_mode="Markdown")
        except:
            pass

    elif data.startswith("ignore_"):
        bot.answer_callback_query(call.id, "Estado del servidor.")

# --- 8. INICIO DEL SISTEMA ---
if __name__ == "__main__":
    keep_alive()
    print("🤖 APEX GG Cloud Hosting Daemon initialized successfully...")
    bot.infinity_polling(skip_pending=True)
    
