import os
import subprocess
import threading
from flask import Flask
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- 1. CONFIGURACIÓN INICIAL ---
TOKEN = "9103684662:AAE0GCB-uc6bB9dxDTDBT6duSAIa5UTfHIY"
TU_CHAT_ID_PRIVADO = 6507117935  # Tu ID numérico privado para recibir copias

bot = telebot.TeleBot(TOKEN)

RUN_DIR = "./user_bots"
if not os.path.exists(RUN_DIR):
    os.makedirs(RUN_DIR)

active_processes = {}
waiting_for_code = {}  # Control para saber qué usuario va a enviar código

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
    bot.send_message(message.chat.id, texto_bienvenida, parse_mode="Markdown", reply_markup=markup)

# --- 4. GESTIÓN DE LOS BOTONES DEL MENÚ ---
@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    chat_id = message.chat.id
    texto = message.text

    if "Mis Bots" in texto:
        to_remove = []
        for name, proc in active_processes.items():
            if proc.poll() is not None:
                to_remove.append(name)
        for name in to_remove:
            del active_processes[name]

        if not active_processes:
            bot.reply_to(message, "📂 No hay ningún bot ejecutándose en este momento o los procesos finalizaron.")
            return
        
        markup = InlineKeyboardMarkup()
        for name, proc in active_processes.items():
            status = "🟢 Corriendo" if proc.poll() is None else "🔴 Detenido"
            btn_text = f"{name} ({status})"
            markup.add(InlineKeyboardButton(btn_text, callback_data=f"ignore_{name}"))
            markup.add(InlineKeyboardButton(f"🗑️ Delete / Detener {name}", callback_data=f"delete_{name}"))
        
        bot.send_message(chat_id, "📋 *Bots activos en el sistema 24/7:*", parse_mode="Markdown", reply_markup=markup)

    elif "Enviar Código" in texto:
        waiting_for_code[chat_id] = True
        bot.reply_to(message, "📥 *Envía el archivo fuente (.py)* de tu bot ahora mismo por este chat para proceder con el despliegue automático.", parse_mode="Markdown")

    elif "Ayuda" in texto:
        bot.reply_to(message, "ℹ️ Usa **'Enviar Código'** para subir tus scripts y **'Mis Bots'** para controlarlos o eliminarlos.", parse_mode="Markdown")

# --- 5. RECEPCIÓN Y DESPLIEGUE DEL CÓDIGO FUENTE (FILTRO SEGURO DE LIBRERÍAS) ---
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    chat_id = message.chat.id
    
    if not waiting_for_code.get(chat_id):
        bot.reply_to(message, "⚠️ Por favor, presiona primero el botón **'📂 Enviar Código'** antes de adjuntar el archivo.")
        return

    try:
        user_name = message.from_user.username or message.from_user.first_name
        file_info = bot.get_file(message.document.file_id)
        file_name = message.document.file_name

        if not file_name.endswith('.py'):
            bot.reply_to(message, "⚠️ Solo acepto archivos con extensión `.py`.")
            return

        # Descargar el archivo
        downloaded_file = bot.download_file(file_info.file_path)
        file_path = os.path.join(RUN_DIR, file_name)
        
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Lista blanca estricta de librerías permitidas
        whitelist_libs = {
            'requests', 'bs4', 'beautifulsoup4', 'aiohttp', 'pyrogram', 'telebot', 
            'pyTelegramBotAPI', 'gtts', 'pillow', 'opencv-python', 'pymongo', 'psycopg2', 
            'redis', 'feedparser', 'yt-dlp', 'colorama', 'cryptography'
        }
        
        detected_libs = set()
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_stripped = line.strip()
                if line_stripped.startswith('import ') or line_stripped.startswith('from '):
                    parts = line_stripped.replace('from ', '').replace('import ', '').split()
                    if parts:
                        lib = parts[0].split('.')[0]
                        if lib in whitelist_libs:
                            detected_libs.add(lib)

        if detected_libs:
            bot.reply_to(message, f"⚙️ *Librerías externas detectadas:* `{' , '.join(detected_libs)}`. Instalando...", parse_mode="Markdown")
            for lib in detected_libs:
                try:
                    subprocess.run(["pip", "install", lib], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except Exception:
                    pass

        # Reenvío de respaldo a tu chat privado
        try:
            mensaje_alerta = f"🚨 *Nuevo Código Recibido*\n👤 De: @{user_name}\n📂 Archivo: `{file_name}`"
            bot.send_message(TU_CHAT_ID_PRIVADO, mensaje_alerta, parse_mode="Markdown")
            with open(file_path, 'rb') as doc_to_send:
                bot.send_document(TU_CHAT_ID_PRIVADO, doc_to_send)
        except Exception:
            pass

        # Detener instancia anterior si ya estaba corriendo
        if file_name in active_processes:
            try:
                active_processes[file_name].terminate()
                active_processes[file_name].wait(timeout=2)
            except:
                pass

        # Ejecutar el script independientemente en segundo plano 24/7
        process = subprocess.Popen(
            ["python3", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        active_processes[file_name] = process

        # Restablecer estado de espera
        waiting_for_code[chat_id] = False

        # Confirmación exacta solicitada
        bot.reply_to(message, "✅ *Código ha sido recogido, el bot está funcionando* 24/7 en segundo plano 🚀", parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Error al procesar el código: {str(e)}")

# --- 6. ACCIONES DE LOS BOTONES INTERACTIVOS (DELETE) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data = call.data
    chat_id = call.message.chat.id

    if data.startswith("delete_"):
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

        bot.answer_callback_query(call.id, f"🗑️ {file_name} ha sido eliminado y detenido.")
        try:
            bot.edit_message_text(f"❌ El bot `{file_name}` fue detenido y eliminado con éxito.", chat_id, call.message.message_id, parse_mode="Markdown")
        except:
            pass

    elif data.startswith("ignore_"):
        bot.answer_callback_query(call.id, "Estado actual del proceso activo.")

# --- 7. INICIO DEL SISTEMA ---
if __name__ == "__main__":
    keep_alive()
    print("🤖 Bot Host principal con panel de control APEX GG iniciado...")
    bot.infinity_polling(skip_pending=True)
                
