import os
import time
import random
import requests
from threading import Thread
from flask import Flask
from telegram import Bot

# --- CONFIGURAÇÕES E CREDENCIAIS ---
TOKEN_BOT = os.getenv("TOKEN_BOT", "8424473006:AAFlnQJyB55mf1RMRwFsHmVZvFED4LLliqQ")
ID_CANAL = os.getenv("ID_CANAL", "-1003788628286")
TAG_MERCADO_LIVRE = os.getenv("TAG_ML", "salu8535714")

# 🔑 CREDENCIAIS DA API DO MERCADO LIVRE
# Cole o seu App ID e a sua Secret Key entre as aspas abaixo:
ML_CLIENT_ID = os.getenv("ML_CLIENT_ID", "3774054197554006")
ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "geNE24TeMJRCG5AR8vtzPGETBuKCWm9P")

INTERVALO_POSTAGEM = 1800  # 30 minutos (1800 segundos)

# --- SERVIDOR WEB (KEEP ALIVE DO RENDER) ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot de Ofertas + Detector de Bugs Ativo!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- BUSCA DE OFERTA NA API DO MERCADO LIVRE ---
def buscar_oferta_mercadolivre():
    """Busca produtos e verifica a porcentagem de desconto"""
    try:
        # Busca produtos em destaque/ofertas no Mercado Livre
        url = "https://api.mercadolibre.com/sites/MLB/search?q=ofertas_relampago&limit=30"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            resultados = dados.get("results", [])
            
            if resultados:
                produto = random.choice(resultados)
                
                titulo = produto.get("title")
                preco_atual = produto.get("price")
                preco_original = produto.get("original_price")
                link_original = produto.get("permalink")
                
                # Monta link de afiliado com a sua tag
                link_afiliado = f"{link_original}?matt_tool={TAG_MERCADO_LIVRE}" if "?" not in link_original else f"{link_original}&matt_tool={TAG_MERCADO_LIVRE}"
                
                # Calcula se há um grande desconto (bug/super oferta)
                porcentagem_desconto = 0
                if preco_original and preco_original > preco_atual:
                    porcentagem_desconto = int(((preco_original - preco_atual) / preco_original) * 100)
                
                return {
                    "titulo": titulo,
                    "preco_atual": preco_atual,
                    "preco_original": preco_original,
                    "desconto": porcentagem_desconto,
                    "link": link_afiliado
                }
    except Exception as e:
        print(f"Erro na busca de ofertas: {e}")
    
    return None

# --- LOOP DE POSTAGEM ---
def loop_postagem_automatica():
    bot = Bot(token=TOKEN_BOT)
    print("🚀 Loop de postagem automática e detector de bugs rodando...")
    
    while True:
        try:
            oferta = buscar_oferta_mercadolivre()
            
            if oferta:
                # SE FOR UMA SUPER OFERTA / BUG (Desconto de 40% ou mais)
                if oferta['desconto'] >= 40:
                    mensagem = (
                        "🚨 **ALERTA DE BUG / SUPER DESCONTO!** 🚨\n\n"
                        f"📦 **{oferta['titulo']}**\n"
                        f"❌ De: ~~R$ {oferta['preco_original']:.2f}~~\n"
                        f"🔥 **Por apenas: R$ {oferta['preco_atual']:.2f}** ({oferta['desconto']}% OFF!)\n\n"
                        f"👉 **CORRA ANTES QUE ACABE:** {oferta['link']}\n\n"
                        "⚠️ *Preço extremamente baixo ou possível erro de sistema! Aproveite rápido!*"
                    )
                # OFERTA PADRÃO DE 30 MINUTOS
                else:
                    preco_texto = f"💰 **Preço:** R$ {oferta['preco_atual']:.2f}"
                    if oferta['preco_original']:
                        preco_texto = f"❌ De: ~~R$ {oferta['preco_original']:.2f}~~\n💰 **Por:** R$ {oferta['preco_atual']:.2f}"
                    
                    mensagem = (
                        "🔥 **OFERTA IMPERDÍVEL DO DIA!** 🔥\n\n"
                        f"📦 **{oferta['titulo']}**\n"
                        f"{preco_texto}\n\n"
                        f"👉 **Garantir no Mercado Livre:** {oferta['link']}\n\n"
                        "⚡️ *Aproveite antes que o estoque acabe!*"
                    )
                
                bot.send_message(
                    chat_id=ID_CANAL,
                    text=mensagem,
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                print("✅ Oferta postada com sucesso no canal!")
            else:
                print("⚠️ Nenhuma oferta encontrada neste ciclo.")
                
        except Exception as e:
            print(f"❌ Erro ao enviar mensagem: {e}")
            
        time.sleep(INTERVALO_POSTAGEM)

if __name__ == '__main__':
    keep_alive()
    
    t_post = Thread(target=loop_postagem_automatica)
    t_post.daemon = True
    t_post.start()
    
    while True:
        time.sleep(60)
