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
os.makedirs(RUN_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

active_processes = {}     # file_key -> subprocess.Popen
process_logs = {}         # file_key -> log_file_path
waiting_for_code = {}     # chat_id -> True/False
maintenance_mode = False  # Estado global del modo mantenimiento

# --- GESTIÓN DE ACCESO Y USUARIOS ---
authorized_users = {TU_CHAT_ID_PRIVADO}
pending_users = {}
banned_users = set()
all_users_interacted = set()
user_language = {}        # chat_id -> 'es' or 'en'

# --- 2. DICCIONARIO DE IDIOMAS ---
TEXTS = {
    'es': {
        'welcome': "🤖 *APEX GG - Cloud Hosting Panel 24/7*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nBienvenido al panel de control de alojamiento web y bots.\n\nSelecciona una opción del menú inferior:",
        'btn_bots': "🤖 Mis Bots",
        'btn_send': "📂 Enviar Código",
        'btn_help': "ℹ️ Ayuda",
        'btn_admin': "🔐 Admin Panel",
        'btn_lang': "🌐 English / Español",
        'no_bots': "📂 No hay ningún bot ejecutándose actualmente.",
        'active_bots': "📋 *Bots Activos (24/7):*",
        'status_running': "🟢 En Línea",
        'status_stopped': "🔴 Apagado",
        'btn_console': "📊 Consola / Logs",
        'btn_delete': "🗑️ Eliminar",
        'prompt_send': "📥 *Envía el archivo fuente (.py) o proyecto en (.zip)* de tu bot para iniciar el despliegue automático.",
        'help_text': "ℹ️ *Guía del Hosting APEX GG*:\n\n1️⃣ Pulsa **Enviar Código** para subir tu script.\n2️⃣ El sistema instalará las dependencias necesarias.\n3️⃣ Controla tus servicios desde **Mis Bots**.",
        'wrong_file': "⚠️ Formato no válido. Solo se permiten archivos `.py` o comprimidos `.zip`.",
        'lang_changed': "🌐 Idioma actualizado a: **Español** 🇪🇸",
        'pending_msg': "⏳ *Acceso Pendiente de Aprobación*\nTu solicitud ha sido enviada al Administrador.",
        'banned_msg': "❌ *Acceso denegado.* Has sido baneado de este panel de hosting.",
        'maint_msg': "🛠️ *APEX GG se encuentra en Mantenimiento Programado.*"
    },
    'en': {
        'welcome': "🤖 *APEX GG - Cloud Hosting Panel 24/7*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nWelcome to your bot and application hosting control panel.\n\nSelect an option from the menu below:",
        'btn_bots': "🤖 My Bots",
        'btn_send': "📂 Send Code",
        'btn_help': "ℹ️ Help",
        'btn_admin': "🔐 Admin Panel",
        'btn_lang': "🌐 English / Spanish",
        'no_bots': "📂 No bots are currently running.",
        'active_bots': "📋 *Active Bots (24/7):*",
        'status_running': "🟢 Online",
        'status_stopped': "🔴 Offline",
        'btn_console': "📊 Console / Logs",
        'btn_delete': "🗑️ Delete",
        'prompt_send': "📥 *Send your bot source file (.py) or complete project (.zip)* to start automated cloud deployment.",
        'help_text': "ℹ️ *APEX GG Hosting Guide*:\n\n1️⃣ Click **Send Code** to upload your script.\n2️⃣ The system will automatically install required dependencies.\n3️⃣ Control your services via **My Bots**.",
        'wrong_file': "⚠️ Invalid format. Only `.py` files or `.zip` archives are allowed.",
        'lang_changed': "🌐 Language updated to: **English** 🇬🇧",
        'pending_msg': "⏳ *Access Pending Approval*\nYour request has been sent to the Administrator.",
        'banned_msg': "❌ *Access denied.* You have been banned from this hosting panel.",
        'maint_msg': "🛠️ *APEX GG is under scheduled maintenance.*"
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

# --- 4. PANEL PRINCIPAL CON CONTROL DE ACCESO (/start) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_name = message.from_user.username or message.from_user.first_name
    
    if chat_id not in user_language:
        lang_code = message.from_user.language_code or 'es'
        user_language[chat_id] = 'en' if lang_code.startswith('en') else 'es'

    all_users_interacted.add((chat_id, user_name))

    if chat_id in banned_users:
        bot.send_message(chat_id, get_text(chat_id, 'banned_msg'), parse_mode="Markdown")
        return

    if maintenance_mode and chat_id != TU_CHAT_ID_PRIVADO:
        bot.send_message(chat_id, get_text(chat_id, 'maint_msg'), parse_mode="Markdown")
        return

    if chat_id not in authorized_users:
        pending_users[chat_id] = user_name
        
        markup_admin = InlineKeyboardMarkup(row_width=2)
        markup_admin.add(
            InlineKeyboardButton("✅ Aceptar", callback_data=f"approve_{chat_id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_{chat_id}")
        )
        try:
            bot.send_message(
                TU_CHAT_ID_PRIVADO,
                f"🚨 *Nueva solicitud de acceso al Hosting*\n👤 Usuario: @{user_name}\n🆔 ID: `{chat_id}`",
                parse_mode="Markdown",
                reply_markup=markup_admin
            )
        except Exception:
            pass
            
        bot.send_message(chat_id, get_text(chat_id, 'pending_msg'), parse_mode="Markdown")
        return

    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton(get_text(chat_id, 'btn_bots')),
        KeyboardButton(get_text(chat_id, 'btn_send')),
        KeyboardButton(get_text(chat_id, 'btn_help')),
        KeyboardButton(get_text(chat_id, 'btn_lang'))
    )
    if chat_id == TU_CHAT_ID_PRIVADO:
        markup.add(KeyboardButton(get_text(chat_id, 'btn_admin')))
    
    bot.send_message(chat_id, get_text(chat_id, 'welcome'), parse_mode="Markdown", reply_markup=markup)

# --- 5. PANEL DE ADMINISTRADOR SECRETO (/admin) ---
@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    show_admin_menu(message.chat.id)

def show_admin_menu(chat_id):
    if chat_id != TU_CHAT_ID_PRIVADO:
        return  

    status_maint = "🟢 Activado" if maintenance_mode else "🔴 Desactivado"
    
    markup = InlineKeyboardMarkup(row_width=1)
    btn_toggle = InlineKeyboardButton(f"🛠️ Modo Mantenimiento ({status_maint})", callback_data="toggle_maintenance")
    btn_users = InlineKeyboardButton("👥 Ver Usuarios y Estadísticas", callback_data="admin_users")
    btn_ban = InlineKeyboardButton("🚫 Gestionar Baneos", callback_data="admin_ban_menu")
    markup.add(btn_toggle, btn_users, btn_ban)

    bot.send_message(
        chat_id, 
        "🔐 *Panel de Administrador Secreto - APEX GG*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bienvenido, Dave. Controla la seguridad y usuarios del hosting:", 
        parse_mode="Markdown", 
        reply_markup=markup
    )

# --- 6. GESTIÓN DE OPCIONES DEL MENÚ INFERIOR ---
@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    chat_id = message.chat.id
    texto = message.text

    if chat_id in banned_users:
        return

    if maintenance_mode and chat_id != TU_CHAT_ID_PRIVADO:
        bot.reply_to(message, get_text(chat_id, 'maint_msg'), parse_mode="Markdown")
        return

    if chat_id not in authorized_users and chat_id != TU_CHAT_ID_PRIVADO:
        bot.reply_to(message, get_text(chat_id, 'pending_msg'), parse_mode="Markdown")
        return

    if chat_id == TU_CHAT_ID_PRIVADO and ("Admin Panel" in texto):
        show_admin_menu(chat_id)
        return

    if "English / Spanish" in texto or "English / Español" in texto:
        user_language[chat_id] = 'en' if user_language[chat_id] == 'es' else 'es'
        
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            KeyboardButton(get_text(chat_id, 'btn_bots')),
            KeyboardButton(get_text(chat_id, 'btn_send')),
            KeyboardButton(get_text(chat_id, 'btn_help')),
            KeyboardButton(get_text(chat_id, 'btn_lang'))
        )
        if chat_id == TU_CHAT_ID_PRIVADO:
            markup.add(KeyboardButton(get_text(chat_id, 'btn_admin')))

        bot.send_message(chat_id, get_text(chat_id, 'lang_changed'), parse_mode="Markdown", reply_markup=markup)
        return

    if "Mis Bots" in texto or "My Bots" in texto:
        to_remove = []
        for name, proc in active_processes.items():
            if proc.poll() is not None:
                to_remove.append(name)
        for name in to_remove:
            del active_processes[name]

        if not active_processes and not process_logs:
            bot.reply_to(message, get_text(chat_id, 'no_bots'))
            return
        
        markup = InlineKeyboardMarkup(row_width=2)
        for name in list(active_processes.keys()) + list(process_logs.keys()):
            if name not in process_logs and name not in active_processes:
                continue
            proc = active_processes.get(name)
            status = get_text(chat_id, 'status_running') if (proc and proc.poll() is None) else get_text(chat_id, 'status_stopped')
            
            markup.add(InlineKeyboardButton(f"{name} ({status})", callback_data=f"ignore_{name}"))
            markup.add(
                InlineKeyboardButton(get_text(chat_id, 'btn_console'), callback_data=f"console_{name}"),
                InlineKeyboardButton(get_text(chat_id, 'btn_delete'), callback_data=f"delete_{name}")
            )
        
        bot.send_message(chat_id, get_text(chat_id, 'active_bots'), parse_mode="Markdown", reply_markup=markup)

    elif "Enviar Código" in texto or "Send Code" in texto:
        waiting_for_code[chat_id] = True
        bot.reply_to(message, get_text(chat_id, 'prompt_send'), parse_mode="Markdown")

    elif "Ayuda" in texto or "Help" in texto:
        bot.reply_to(message, get_text(chat_id, 'help_text'), parse_mode="Markdown")

# --- 7. RECEPCIÓN Y DESPLIEGUE AUTOMÁTICO ---
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    chat_id = message.chat.id
    
    if chat_id in banned_users or (chat_id not in authorized_users and chat_id != TU_CHAT_ID_PRIVADO):
        return

    if maintenance_mode and chat_id != TU_CHAT_ID_PRIVADO:
        bot.reply_to(message, get_text(chat_id, 'maint_msg'), parse_mode="Markdown")
        return

    if not waiting_for_code.get(chat_id):
        bot.reply_to(message, "⚠️ Por favor, presiona primero el botón de enviar código antes de adjuntar el archivo.")
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
            process_key
