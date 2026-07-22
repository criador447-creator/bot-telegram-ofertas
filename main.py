import os
import re
import logging
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURAÇÕES DE AFILIADO ---
# Coloque aqui a sua Tag/SubID de Afiliado
TAG_SHOPEE = os.getenv("TAG_SHOPEE", "18176880013") 
TAG_MERCADO_LIVRE = os.getenv("TAG_ML", "salu8535714")

# --- SERVIDOR WEB (KEEP ALIVE) ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot de Afiliados Automático Ativo!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- LÓGICA DO BOT ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN_BOT = os.getenv("TOKEN_BOT", "8424473006:AAFlnQJyB55mf1RMRwFsHmVZvFED4LLliqQ")
ID_CANAL = os.getenv("ID_CANAL", "-1003788628286")

def converter_link_afiliado(texto):
    """Detecta links no texto e insere a tag de afiliado"""
    # Encontra URLs no texto enviado
    urls = re.findall(r'(https?://[^\s]+)', texto)
    
    texto_convertido = texto
    for url in urls:
        # Se for link do Mercado Livre
        if "mercadolivre.com" in url or "mercadolibre.com" in url:
            link_afiliado = f"{url}?matt_tool={TAG_MERCADO_LIVRE}" if "?" not in url else f"{url}&matt_tool={salu8535714}"
            texto_convertido = texto_convertido.replace(url, link_afiliado)
            
        # Se for link da Shopee
        elif "shopee.com" in url or "shp.ee" in url:
            link_afiliado = f"{url}?smtt={TAG_SHOPEE}" if "?" not in url else f"{url}&smtt={TAG_SHOPEE}"
            texto_convertido = texto_convertido.replace(url, link_afiliado)
            
    return texto_convertido

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot Automático Online! Envie um texto com qualquer link que eu converto para seu afiliado e posto no canal.")

async def processar_oferta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_usuario = update.message.text
    
    # Converte os links normais para links de afiliado
    texto_com_afiliado = converter_link_afiliado(texto_usuario)
    
    mensagem_formatada = (
        "🔥 **OFERTA IMPERDÍVEL!** 🔥\n\n"
        f"{texto_com_afiliado}\n\n"
        "⚡️ *Gostou? Clique no link acima para garantir com desconto!*"
    )
    
    try:
        await context.bot.send_message(
            chat_id=ID_CANAL,
            text=mensagem_formatada,
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
        await update.message.reply_text("✅ Oferta convertida e enviada para o canal com sucesso!")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao enviar: {e}")

if __name__ == '__main__':
    keep_alive()
    
    app = ApplicationBuilder().token(TOKEN_BOT).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), processar_oferta))
    
    print("Bot rodando...")
    app.run_polling()
