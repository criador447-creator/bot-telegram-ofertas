import os
import re
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Configuração de logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Carrega as variáveis de ambiente configuradas no Render
TOKEN_BOT = os.getenv("8424473006:AAFlnQJyB55mf1RMRwFsHmVZvFED4LLliqQ")
ID_CANAL = os.getenv("ID_CANAL", "Id: -1003788628286


🧠 Explanations and answers
Free AI → DeepSeek & ChatGPT

🖼 Visualize your ideas
Make Image → NanoBanana")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_boas_vindas = (
        "🤖 *Bot de Ofertas e Afiliados Ativo!*\n\n"
        "Envie qualquer mensagem de oferta, texto com link da Shopee ou Mercado Livre aqui.\n"
        "Eu vou formatar com destaque e enviar diretamente para o seu canal!"
    )
    await update.message.reply_text(texto_boas_vindas, parse_mode="Markdown")

async def processar_oferta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_usuario = update.message.text
    
    # Formatação visual atraente para o canal
    mensagem_formatada = (
        "🔥 *OFERTA IMPERDÍVEL ENCONTRADA!* 🔥\n\n"
        f"{texto_usuario}\n\n"
        "⚡️ *Gostou? Clique no link acima para garantir com desconto!*\n"
        "📦 *Estoque e preços sujeitos a alteração.*"
    )
    
    try:
        # Envia para o Canal Oficial
        await context.bot.send_message(
            chat_id=ID_CANAL,
            text=mensagem_formatada,
            parse_mode="Markdown",
            disable_web_page_preview=False
        )
        await update.message.reply_text("✅ *Oferta enviada com sucesso para o canal!*", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Erro ao enviar para o canal: {e}")
        await update.message.reply_text(f"❌ *Erro ao enviar:* {e}\n\nVerifique se o bot é administrador do canal!")

if __name__ == '__main__':
    if TOKEN_BOT == "8424473006:AAFlnQJyB55mf1RMRwFsHmVZvFED4LLliqQ":
        print("ERRO: Configure a variável TOKEN_BOT no arquivo ou no Render!")
    else:
        app = ApplicationBuilder().token(TOKEN_BOT).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), processar_oferta))
        
        print("🤖 Bot rodando com sucesso no Render...")
        app.run_polling()
