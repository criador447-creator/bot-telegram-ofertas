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
TAG_SHOPEE = os.getenv("TAG_SHOPEE", "18176880013")

INTERVALO_POSTAGEM = 600 # 10 minutos

# --- SERVIDOR WEB (KEEP ALIVE) ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot de Ofertas Ativo!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- BUSCA MERCADO LIVRE ---
def buscar_oferta_mercadolivre():
    try:
        url = "https://api.mercadolibre.com/sites/MLB/search?q=promocao&limit=30"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        
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
        else:
            print(f"⚠️ Mercado Livre respondeu com status: {response.status_code}")
    except Exception as e:
        print(f"❌ Erro ML: {e}")
    return None

# --- BUSCA SHOPEE ---
def buscar_oferta_shopee():
    try:
        # Busca alternativa para contornar bloqueios simples
        url = "https://shopee.com.br/api/v4/recommend/recommend_items?bundle=daily_discover_main&limit=30"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://shopee.com.br/"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            items = dados.get("data", {}).get("sections", [{}])[0].get("data", {}).get("item", [])
            if items:
                item_info = random.choice(items)
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
        else:
            print(f"⚠️ Shopee bloqueou a requisição (Status {response.status_code})")
    except Exception as e:
        print(f"❌ Erro Shopee: {e}")
    return None

# --- ENVIO DE MENSAGEM ---
def enviar_mensagem_canal(bot, oferta):
    if oferta['desconto'] >= 40:
        mensagem = (
            "🚨 **ALERTA DE BUG / SUPER DESCONTO!** 🚨\n\n"
            f"📦 **{oferta['titulo']}**\n"
            f"❌ De: ~~R$ {oferta['preco_original']:.2f}~~\n"
            f"🔥 **Por apenas: R$ {oferta['preco_atual']:.2f}** ({oferta['desconto']}% OFF!)\n\n"
            f"👉 **CORRA ANTES QUE ACABE ({oferta['origem']}):** {oferta['link']}"
        )
    else:
        preco_texto = f"💰 **Preço:** R$ {oferta['preco_atual']:.2f}"
        if oferta['preco_original'] and oferta['preco_original'] > oferta['preco_atual']:
            preco_texto = f"❌ De: ~~R$ {oferta['preco_original']:.2f}~~\n💰 **Por:** R$ {oferta['preco_atual']:.2f}"
        
        mensagem = (
            f"🔥 **OFERTA IMPERDÍVEL ({oferta['origem'].upper()})!** 🔥\n\n"
            f"📦 **{oferta['titulo']}**\n"
            f"{preco_texto}\n\n"
            f"👉 **Garantir na {oferta['origem']}:** {oferta['link']}"
        )
        
    bot.send_message(
        chat_id=ID_CANAL,
        text=mensagem,
        parse_mode="Markdown",
        disable_web_page_preview=False
    )
    print(f"✅ Oferta enviada ({oferta['origem']}) - Desconto: {oferta['desconto']}%")

# --- LOOP AUTOMÁTICO ---
def loop_postagem_automatica():
    bot = Bot(token=TOKEN_BOT)
    
    # 🧪 TESTE INICIAL: Envia mensagem imediatamente ao ligar
    try:
        bot.send_message(chat_id=ID_CANAL, text="🤖 **Bot de Ofertas iniciado com sucesso!** Acompanhe as postagens automaticamente.")
        print("✅ Mensagem de teste inicial enviada para o canal!")
    except Exception as e:
        print(f"❌ Erro no teste inicial (Verifique se o bot é Admin do canal): {e}")

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
                # Se falhar uma, tenta a outra imediatamente
                oferta = buscar_oferta_mercadolivre()
                if oferta:
                    enviar_mensagem_canal(bot, oferta)
                else:
                    print("⚠️ Nenhuma oferta obtida neste ciclo. Tentando novamente no próximo.")
                
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
