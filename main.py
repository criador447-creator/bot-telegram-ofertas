import os
import time
import random
import requests
from threading import Thread
from flask import Flask

# --- CONFIGURAÇÕES E CREDENCIAIS ---
TOKEN_BOT = os.getenv("TOKEN_BOT", "8424473006:AAFlnQJyB55mf1RMRwFsHmVZvFED4LLliqQ")
ID_CANAL = os.getenv("ID_CANAL", "-1003788628286")

TAG_MERCADO_LIVRE = os.getenv("TAG_ML", "salu8535714")
TAG_SHOPEE = os.getenv("TAG_SHOPEE", "18176880013")

INTERVALO_POSTAGEM = 600  # 10 minutos (600 segundos)

# --- SERVIDOR WEB (KEEP ALIVE DO RENDER) ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot de Ofertas Ativo no Render!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- FUNÇÃO DE ENVIO DIRETO VIA API TELEGRAM ---
def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage"
        payload = {
            "chat_id": ID_CANAL,
            "text": mensagem,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("✅ Mensagem enviada com sucesso ao Telegram!")
            return True
        else:
            print(f"❌ Erro ao enviar mensagem ao Telegram: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Exceção no envio Telegram: {e}")
    return False

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
    except Exception as e:
        print(f"❌ Erro ML: {e}")
    return None

# --- BUSCA SHOPEE ---
def buscar_oferta_shopee():
    try:
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
    except Exception as e:
        print(f"❌ Erro Shopee: {e}")
    return None

# --- FORMATAR E ENVIAR MENSAGEM ---
def processar_e_enviar(oferta):
    if oferta['desconto'] >= 40:
        mensagem = (
            "🚨 *ALERTA DE BUG / SUPER DESCONTO!* 🚨\n\n"
            f"📦 *{oferta['titulo']}*\n"
            f"❌ De: ~R$ {oferta['preco_original']:.2f}~\n"
            f"🔥 *Por apenas: R$ {oferta['preco_atual']:.2f}* ({oferta['desconto']}% OFF!)\n\n"
            f"👉 *CORRA ANTES QUE ACABE ({oferta['origem']}):*\n{oferta['link']}"
        )
    else:
        preco_texto = f"💰 *Preço:* R$ {oferta['preco_atual']:.2f}"
        if oferta['preco_original'] and oferta['preco_original'] > oferta['preco_atual']:
            preco_texto = f"❌ De: ~R$ {oferta['preco_original']:.2f}~\n💰 *Por:* R$ {oferta['preco_atual']:.2f}"
        
        mensagem = (
            f"🔥 *OFERTA IMPERDÍVEL ({oferta['origem'].upper()})!* 🔥\n\n"
            f"📦 *{oferta['titulo']}*\n"
            f"{preco_texto}\n\n"
            f"👉 *Garantir na {oferta['origem']}:*\n{oferta['link']}"
        )
        
    enviar_telegram(mensagem)

# --- LOOP AUTOMÁTICO DE 10 MINUTOS ---
def loop_postagem_automatica():
    print("🚀 Iniciando bot e enviando mensagem de teste...")
    
    # Teste imediato ao ligar
    enviar_telegram("🤖 *Bot de Ofertas conectado com sucesso!* As ofertas serão enviadas aqui a cada 10 minutos.")

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
                processar_e_enviar(oferta)
            else:
                # Tenta a outra se a primeira falhar
                oferta = buscar_oferta_mercadolivre()
                if oferta:
                    processar_e_enviar(oferta)
                else:
                    print("⚠️ Nenhuma oferta obtida neste ciclo.")
                
        except Exception as e:
            print(f"❌ Erro no loop de postagens: {e}")
            
        time.sleep(INTERVALO_POSTAGEM)

if __name__ == '__main__':
    keep_alive()
    
    t_post = Thread(target=loop_postagem_automatica)
    t_post.daemon = True
    t_post.start()
    
    while True:
        time.sleep(60)
