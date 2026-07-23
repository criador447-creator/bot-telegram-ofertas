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

# Tags de Afiliado
TAG_MERCADO_LIVRE = os.getenv("TAG_ML", "salu8535714")
TAG_SHOPEE = os.getenv("TAG_SHOPEE", "18176880013")

# Credenciais API Mercado Livre
ML_CLIENT_ID = os.getenv("ML_CLIENT_ID", "3774054197554006")
ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "geNE24TeMJRCG5AR8vtzPGETBuKCWm9P")

# Credenciais API Shopee
SHOPEE_APP_ID = os.getenv("SHOPEE_APP_ID", "18176880013")
SHOPEE_SECRET = os.getenv("SHOPEE_SECRET", "4XA35B6ATAXB2KCN2F6MBY632DNPXFCG
")

# Intervalo padrão de postagem: 10 minutos (600 segundos)
INTERVALO_POSTAGEM = 600 

# --- SERVIDOR WEB (KEEP ALIVE DO RENDER) ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot de Ofertas Mercado Livre + Shopee em Execução!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- BUSCA DE OFERTA NO MERCADO LIVRE ---
def buscar_oferta_mercadolivre():
    try:
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
                
                link_afiliado = f"{link_original}?matt_tool={TAG_MERCADO_LIVRE}" if "?" not in link_original else f"{link_original}&matt_tool={TAG_MERCADO_LIVRE}"
                
                desconto = 0
                if preco_original and preco_original > preco_atual:
                    desconto = int(((preco_original - preco_atual) / preco_original) * 100)
                
                return {
                    "origem": "Mercado Livre",
                    "titulo": titulo,
                    "preco_atual": preco_atual,
                    "preco_original": preco_original,
                    "desconto": desconto,
                    "link": link_afiliado
                }
    except Exception as e:
        print(f"Erro ML: {e}")
    return None

# --- BUSCA DE OFERTA NA SHOPEE ---
def buscar_oferta_shopee():
    try:
        url = "https://shopee.com.br/api/v4/search/search_items?keyword=ofertas%20do%20dia&limit=30"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            items = dados.get("items", [])
            if items:
                item_info = random.choice(items).get("item_basic", {})
                titulo = item_info.get("name")
                preco_atual = item_info.get("price", 0) / 100000
                preco_original = item_info.get("price_before_discount", 0) / 100000
                item_id = item_info.get("itemid")
                shop_id = item_info.get("shopid")
                
                link_original = f"https://shopee.com.br/product/{shop_id}/{item_id}"
                link_afiliado = f"{link_original}?smtt={TAG_SHOPEE}"
                
                desconto = 0
                if preco_original and preco_original > preco_atual:
                    desconto = int(((preco_original - preco_atual) / preco_original) * 100)
                
                return {
                    "origem": "Shopee",
                    "titulo": titulo,
                    "preco_atual": preco_atual,
                    "preco_original": preco_original,
                    "desconto": desconto,
                    "link": link_afiliado
                }
    except Exception as e:
        print(f"Erro Shopee: {e}")
    return None

# --- FORMATAÇÃO E ENVIO DE MENSAGENS ---
def enviar_mensagem_canal(bot, oferta):
    # Alerta de Bug / Super Desconto (Desconto >= 40%)
    if oferta['desconto'] >= 40:
        mensagem = (
            "🚨 **ALERTA DE BUG / SUPER DESCONTO!** 🚨\n\n"
            f"📦 **{oferta['titulo']}**\n"
            f"❌ De: ~~R$ {oferta['preco_original']:.2f}~~\n"
            f"🔥 **Por apenas: R$ {oferta['preco_atual']:.2f}** ({oferta['desconto']}% OFF!)\n\n"
            f"👉 **CORRA ANTES QUE ACABE ({oferta['origem']}):** {oferta['link']}\n\n"
            "⚠️ *Preço extremamente baixo ou possível erro no sistema!*"
        )
    # Postagem padrão a cada 10 minutos
    else:
        preco_texto = f"💰 **Preço:** R$ {oferta['preco_atual']:.2f}"
        if oferta['preco_original'] and oferta['preco_original'] > oferta['preco_atual']:
            preco_texto = f"❌ De: ~~R$ {oferta['preco_original']:.2f}~~\n💰 **Por:** R$ {oferta['preco_atual']:.2f}"
        
        mensagem = (
            f"🔥 **OFERTA IMPERDÍVEL ({oferta['origem'].upper()})!** 🔥\n\n"
            f"📦 **{oferta['titulo']}**\n"
            f"{preco_texto}\n\n"
            f"👉 **Garantir na {oferta['origem']}:** {oferta['link']}\n\n"
            "⚡️ *Aproveite antes que o estoque acabe!*"
        )
        
    bot.send_message(
        chat_id=ID_CANAL,
        text=mensagem,
        parse_mode="Markdown",
        disable_web_page_preview=False
    )
    print(f"✅ Oferta enviada ({oferta['origem']}) - Desconto: {oferta['desconto']}%")

# --- LOOP PRINCIPAL ---
def loop_postagem_automatica():
    bot = Bot(token=TOKEN_BOT)
    print("🚀 Loop de 10 minutos (ML + Shopee + Bugs) rodando...")
    
    plataforma_atual = "ML"
    
    while True:
        try:
            oferta = None
            
            if plataforma_atual == "ML":
                oferta = buscar_oferta_mercadolivre()
                plataforma_atual = "SHOPEE"
            else:
                oferta = buscar_oferta_shopee()
                plataforma_atual = "ML"
                
            if oferta:
                enviar_mensagem_canal(bot, oferta)
            else:
                print("⚠️ Nenhuma oferta encontrada neste ciclo.")
                
        except Exception as e:
            print(f"❌ Erro na postagem automática: {e}")
            
        time.sleep(INTERVALO_POSTAGEM)

if __name__ == '__main__':
    keep_alive()
    
    t_post = Thread(target=loop_postagem_automatica)
    t_post.daemon = True
    t_post.start()
    
    while True:
        time.sleep(60)
