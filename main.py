import os
import logging
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- SERVIDOR WEB PARA MANTER O RENDER ATIVO ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot do Telegram está rodando 24/7!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- LÓGICA DO BOT DO TELEGRAM ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN_BOT = os.getenv("TOKEN_BOT", "8424473006:AAFlnQJyB55mf1RMRwFsHmVZvFED4LLliqQ")
ID_CANAL = os.getenv("ID_CANAL", "-1003788628286")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot ativo! Envie uma oferta para postar no canal.")

async def processar_oferta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_usuario = update.message.text
    
    mensagem_formatada = (
        "🔥 *OFERTA IMPERDÍVEL ENCONTRADA!* 🔥\n\n"
        f"{texto_usuario}\n\n"
        "⚡️ *Gostou? Clique no link acima para garantir com desconto!*"
    )
    
    try:
        await context.bot.send_message(
            chat_id=ID_CANAL,
            text=mensagem_formatada,
            disable_web_page_preview=false
        )
        await update.message.reply_text("✅ Oferta enviada para o canal!")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao enviar: {e}")

if __name__ == '__main__':
    keep_alive()  # Inicia o servidor web
    
    app = ApplicationBuilder().token(TOKEN_BOT).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), processar_oferta))
    
    print("Bot do Telegram rodando...")
    app.run_polling()
