import os
import time
import requests
import logging
from threading import Thread
from flask import Flask
from telegram import Bot

# --- CONFIGURAÇÕES E CREDENCIAIS ---
TOKEN_BOT = os.getenv("TOKEN_BOT", "8424473006:AAFlnQJyB55mf1RMRwFsHmVZvFED4LLliqQ")
ID_CANAL = os.getenv("ID_CANAL", "-1003788628286")
TAG_MERCADO_LIVRE = os.getenv("TAG_ML", "salu8535714")

# Credenciais da API do Mercado Livre (coloque as suas aqui ou no Render)
ML_CLIENT_ID = os.getenv("3774054197554006")
ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "geNE24TeMJRCG5AR8vtzPGETBuKCWm9P")

# Tempo entre postagens (30 minutos = 1800 segundos)
INTERVALO_POSTAGEM = 1800 

# --- SERVIDOR WEB (KEEP ALIVE DO RENDER) ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot de Ofertas Automático Rodando a cada 30 min!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- BUSCA DE OFERTA NA API DO MERCADO LIVRE ---
def buscar_oferta_mercadolivre():
    """Busca produtos em promoção/desconto no Mercado Livre via API"""
    try:
        # Busca produtos em destaque com desconto no Brasil (MLB)
        url = "https://api.mercadolibre.com/sites/MLB/search?q=ofertas_do_dia&limit=20"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            resultados = dados.get("results", [])
            
            if resultados:
                # Pega um produto da lista
                import random
                produto = random.choice(resultados)
                
                titulo = produto.get("title")
                preco = produto.get("price")
                link_original = produto.get("permalink")
                
                # Monta o link de afiliado com a sua tag
                link_afiliado = f"{link_original}?matt_tool={TAG_MERCADO_LIVRE}" if "?" not in link_original else f"{link_original}&matt_tool={TAG_MERCADO_LIVRE}"
                
                return {
                    "titulo": titulo,
                    "preco": preco,
                    "link": link_afiliado
                }
    except Exception as e:
        print(f"Erro ao buscar oferta na API: {e}")
    
    return None

# --- LOOP AUTOMÁTICO DE POSTAGEM ---
def loop_postagem_automatica():
    """Roda continuamente postando uma oferta a cada 30 minutos"""
    bot = Bot(token=TOKEN_BOT)
    print("🚀 Loop de postagem automática iniciado (30 minutos)...")
    
    while True:
        try:
            oferta = buscar_oferta_mercadolivre()
            
            if oferta:
                mensagem = (
                    "🔥 **OFERTA IMPERDÍVEL DO DIA!** 🔥\n\n"
                    f"📦 **{oferta['titulo']}**\n"
                    f"💰 **Preço:** R$ {oferta['preco']:.2f}\n\n"
                    f"👉 **Garantir com Desconto:** {oferta['link']}\n\n"
                    "⚡️ *Aproveite antes que o estoque acabe!*"
                )
                
                # Envia direto para o canal
                bot.send_message(
                    chat_id=ID_CANAL,
                    text=mensagem,
                    parse_mode="Markdown",
                    disable_web_page_preview=False
                )
                print("✅ Oferta postada com sucesso no canal!")
            else:
                print("⚠️ Não foi possível obter uma oferta nesta tentativa.")
                
        except Exception as e:
            print(f"❌ Erro na postagem automática: {e}")
            
        # Aguarda 30 minutos até a próxima postagem
        time.sleep(INTERVALO_POSTAGEM)

if __name__ == '__main__':
    keep_alive()  # Inicia servidor Flask
    
    # Inicia o loop de postagem em segundo plano
    t_post = Thread(target=loop_postagem_automatica)
    t_post.daemon = True
    t_post.start()
    
    # Mantém o script rodando
    while True:
        time.sleep(60)
