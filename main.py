import os
import time
import random
import logging
import requests
import json
import google.generativeai as genai
from threading import Thread
from flask import Flask

# --- CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# --- CONFIGURAÇÕES E CREDENCIAIS ---
TOKEN_BOT = os.getenv("TOKEN_BOT", "8424473006:AAFlnQJyB55mf1RMRwFsHmVZvFED4LLliqQ")
ID_CANAL = os.getenv("ID_CANAL", "-1003788628286")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Configuração da IA Gemini (Função 2)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

LINK_DIVULGACAO_CANAL = os.getenv("LINK_CANAL", "https://t.me/seu_canal_aqui")

TAG_MERCADO_LIVRE = os.getenv("TAG_ML", "salu8535714")
TAG_SHOPEE = os.getenv("TAG_SHOPEE", "18176880013")

INTERVALO_POSTAGEM = 600  # 10 minutos

# --- BANCO DE DADOS EM MEMÓRIA PARA O RADAR DE DESEJOS (Função 1) ---
# Estrutura: [{"user_id": 12345, "termo": "air fryer", "preco_max": 200.0}]
RADAR_DESEJOS = []

# --- SERVIDOR WEB (KEEP ALIVE DO RENDER) ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot de Ofertas Ultra Avançado Ativo!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- FUNÇÃO 2: GERAR LEGENDA PERSUASIVA COM IA ---
def gerar_copy_ia(titulo, preco, origem):
    if not GEMINI_API_KEY:
        return None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"Crie uma legenda muito curta, empolgante e persuasiva (máximo 2 frases) para vender o produto '{titulo}' "
            f"por R$ {preco:.2f} na loja {origem}. Use emojis marcantes. Não inclua hashtags ou links."
        )
        response = model.generate_content(prompt)
        return response.text.strip() if response.text else None
    except Exception as e:
        logging.error(f"Erro ao gerar copy na IA: {e}")
        return None

# --- FUNÇÃO DE ENVIO PARA O TELEGRAM ---
def enviar_telegram_com_botao(foto_url, mensagem, texto_botao, url_botao, comparar_texto=None):
    botoes = [[{"text": texto_botao, "url": url_botao}]]
    
    if comparar_texto:
        botoes.append([{"text": comparar_texto, "url": url_botao}])
        
    botoes.append([{"text": "📢 Compartilhe nosso Canal de Ofertas!", "url": LINK_DIVULGACAO_CANAL}])

    reply_markup = {"inline_keyboard": botoes}

    if foto_url:
        try:
            url = f"https://api.telegram.org/bot{TOKEN_BOT}/sendPhoto"
            payload = {
                "chat_id": ID_CANAL,
                "photo": foto_url,
                "caption": mensagem,
                "parse_mode": "Markdown",
                "reply_markup": reply_markup
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logging.info("✅ Oferta enviada com SUCESSO!")
                return True
        except Exception as e:
            logging.error(f"❌ Exceção ao enviar foto: {e}")

    try:
        url = f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage"
        payload = {
            "chat_id": ID_CANAL,
            "text": mensagem,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
            "reply_markup": reply_markup
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logging.info("✅ Oferta enviada com SUCESSO (Apenas Texto)!")
            return True
    except Exception as e:
        logging.error(f"❌ Exceção ao enviar texto: {e}")

    return False

# --- BUSCA MERCADO LIVRE ---
def buscar_oferta_mercadolivre(termo_busca="promocao"):
    try:
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={termo_busca}&limit=20"
        headers = {"User-Agent": "Mozilla/5.0"}
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
                foto = produto.get("thumbnail", "").replace("-I.jpg", "-O.jpg")
                
                shipping = produto.get("shipping", {})
                frete_gratis = shipping.get("free_shipping", False)
                
                installments = produto.get("installments")
                parcelamento_texto = None
                if installments:
                    qtd = installments.get("quantity")
                    valor = installments.get("amount")
                    taxa = installments.get("rate", 1)
                    if qtd and qtd > 1 and taxa == 0:
                        parcelamento_texto = f"💳 *Em até {qtd}x de R$ {valor:.2f} SEM JUROS*"
                    elif qtd and qtd > 1:
                        parcelamento_texto = f"💳 *Em até {qtd}x de R$ {valor:.2f}*"

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
                    "frete_gratis": frete_gratis,
                    "parcelamento": parcelamento_texto,
                    "link": link_afiliado,
                    "foto": foto
                }
    except Exception as e:
        logging.error(f"Erro na busca do Mercado Livre: {e}")
    return None

# --- BUSCA SHOPEE ---
def buscar_oferta_shopee(termo_busca=None):
    try:
        url = "https://shopee.com.br/api/v4/recommend/recommend_items?bundle=daily_discover_main&limit=30"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
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
                image_id = item_info.get("image")
                
                frete_gratis = item_info.get("show_free_shipping", True)
                
                foto = f"https://down-br.img.susercontent.com/file/{image_id}" if image_id else None
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
                    "frete_gratis": frete_gratis,
                    "parcelamento": None,
                    "link": link_afiliado,
                    "foto": foto
                }
    except Exception as e:
        logging.error(f"Erro na busca da Shopee: {e}")
    return None

# --- FUNÇÃO 3: COMPARADOR DE PREÇOS EM TEMPO REAL ---
def comparar_preco_outra_loja(titulo_produto, preco_atual, origem_atual):
    try:
        termo = titulo_produto.split()[0:3]
        query = " ".join(termo)
        if origem_atual == "Mercado Livre":
            outra_oferta = buscar_oferta_shopee(query)
            nome_outra = "Shopee"
        else:
            outra_oferta = buscar_oferta_mercadolivre(query)
            nome_outra = "Mercado Livre"

        if outra_oferta and outra_oferta.get("preco_atual"):
            preco_outra = outra_oferta["preco_atual"]
            if preco_outra < preco_atual:
                return f"🔍 Na {nome_outra}: R$ {preco_outra:.2f} (Mais Barato!)"
            else:
                return f"🔍 Na {nome_outra}: R$ {preco_outra:.2f}"
    except Exception as e:
        logging.error(f"Erro na comparação de preços: {e}")
    return None

# --- FUNÇÃO 1: VERIFICAR RADAR DE DESEJOS ---
def verificar_radar_desejos(oferta):
    for pedido in list(RADAR_DESEJOS):
        termo = pedido["termo"].lower()
        if termo in oferta["titulo"].lower() and oferta["preco_atual"] <= pedido["preco_max"]:
            # Envia alerta privado ao usuario
            msg_alerta = (
                f"🎯 *ALERTA DO SEU RADAR DE DESEJOS!*\n\n"
                f"Encontramos o produto: *{oferta['titulo']}*\n"
                f"💰 Por apenas: *R$ {oferta['preco_atual']:.2f}* (Sua meta era R$ {pedido['preco_max']:.2f})\n\n"
                f"🔗 [Clique aqui para comprar na {oferta['origem']}]({oferta['link']})"
            )
            try:
                url = f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage"
                payload = {
                    "chat_id": pedido["user_id"],
                    "text": msg_alerta,
                    "parse_mode": "Markdown"
                }
                requests.post(url, json=payload, timeout=5)
                RADAR_DESEJOS.remove(pedido) # Remove após notificar
            except Exception as e:
                logging.error(f"Erro ao enviar alerta privado do Radar: {e}")

# --- PROCESSAR E FORMATAR MENSAGEM ---
def processar_e_enviar(oferta):
    frete_texto = "📦 *FRETE GRÁTIS!* 🚚\n" if oferta.get('frete_gratis') else ""
    parcelas_texto = f"{oferta['parcelamento']}\n" if oferta.get('parcelamento') else ""
    
    # Função 2: Copy personalizada via IA Gemini
    copy_ia = gerar_copy_ia(oferta['titulo'], oferta['preco_atual'], oferta['origem'])
    copy_texto = f"✨ _{copy_ia}_\n\n" if copy_ia else ""

    # Função 3: Comparação de preços
    comparacao = comparar_preco_outra_loja(oferta['titulo'], oferta['preco_atual'], oferta['origem'])
    comparacao_texto = f"{comparacao}\n\n" if comparacao else ""

    # Função 1: Checa se alguém quer esse produto
    verificar_radar_desejos(oferta)

    if oferta['desconto'] >= 40:
        mensagem = (
            "🚨 *ALERTA DE BUG / SUPER DESCONTO!* 🚨\n\n"
            f"{copy_texto}"
            f"📦 *{oferta['titulo']}*\n"
            f"❌ De: ~R$ {oferta['preco_original']:.2f}~\n"
            f"🔥 *Por apenas: R$ {oferta['preco_atual']:.2f}* ({oferta['desconto']}% OFF!)\n"
            f"{parcelas_texto}"
            f"{frete_texto}"
            f"{comparacao_texto}"
            "⚠️ *Preço extremamente baixo ou possível erro no sistema!*"
        )
        texto_botao = f"🔥 COMPRAR NA {oferta['origem'].upper()} ({oferta['desconto']}% OFF)"
    else:
        preco_texto = f"💰 *Preço:* R$ {oferta['preco_atual']:.2f}"
        if oferta['preco_original'] and oferta['preco_original'] > oferta['preco_atual']:
            preco_texto = f"❌ De: ~R$ {oferta['preco_original']:.2f}~\n💰 *Por:* R$ {oferta['preco_atual']:.2f}"
        
        mensagem = (
            f"🔥 *OFERTA IMPERDÍVEL ({oferta['origem'].upper()})!* 🔥\n\n"
            f"{copy_texto}"
            f"📦 *{oferta['titulo']}*\n"
            f"{preco_texto}\n"
            f"{parcelas_texto}"
            f"{frete_texto}"
            f"{comparacao_texto}"
            "⚡️ *Aproveite antes que o estoque acabe!*"
        )
        texto_botao = f"🛒 PEGAR OFERTA NA {oferta['origem'].upper()}"

    enviar_telegram_com_botao(
        foto_url=oferta.get('foto'),
        mensagem=mensagem,
        texto_botao=texto_botao,
        url_botao=oferta['link']
    )

# --- ESCUTAR COMANDOS PRIVADOS PARA O RADAR DE DESEJOS ---
def escutar_comandos_telegram():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN_BOT}/getUpdates?offset={offset}&timeout=10"
            resp = requests.get(url, timeout=12)
            if resp.status_code == 200:
                updates = resp.json().get("result", [])
                for u in updates:
                    offset = u["update_id"] + 1
                    msg = u.get("message", {})
                    text = msg.get("text", "")
                    user_id = msg.get("from", {}).get("id")

                    if text.startswith("/start"):
                        boas_vindas = (
                            "👋 *Bem-vindo ao Bot do Radar de Ofertas!*\n\n"
                            "Use o comando `/desejo produto, preco` para eu te avisar no privado assim que o produto aparecer em promoção!\n"
                            "Exemplo:\n`/desejo air fryer, 200`"
                        )
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": boas_vindas, "parse_mode": "Markdown"})

                    elif text.startswith("/desejo"):
                        try:
                            conteudo = text.replace("/desejo", "").strip()
                            partes = conteudo.split(",")
                            termo = partes[0].strip()
                            preco_max = float(partes[1].strip())
                            
                            RADAR_DESEJOS.append({"user_id": user_id, "termo": termo, "preco_max": preco_max})
                            
                            resp_text = f"✅ *Alerta registrado!* Te avisarei aqui assim que encontrarmos *{termo}* por até R$ {preco_max:.2f}!"
                        except Exception:
                            resp_text = "❌ Formato inválido! Use: `/desejo nome do produto, preco maximo`\nExemplo: `/desejo celular, 800`"
                        
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": resp_text, "parse_mode": "Markdown"})
        except Exception as e:
            logging.error(f"Erro na escuta de comandos: {e}")
        time.sleep(3)

# --- LOOP AUTOMÁTICO DE POSTAGENS ---
def loop_postagem_automatica():
    logging.info("🚀 Bot iniciado com Radar de Desejos, IA Gemini e Comparador de Preços!")

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
                logging.warning("⚠️ Nenhuma oferta obtida neste ciclo. Tentando alternativa...")
                oferta = buscar_oferta_mercadolivre()
                if oferta:
                    processar_e_enviar(oferta)
                
        except Exception as e:
            logging.error(f"❌ Erro no loop de postagens: {e}")
            
        time.sleep(INTERVALO_POSTAGEM)

if __name__ == '__main__':
    keep_alive()
    
    # Thread do Radar / Comandos
    t_cmd = Thread(target=escutar_comandos_telegram)
    t_cmd.daemon = True
    t_cmd.start()

    # Thread das Postagens
    t_post = Thread(target=loop_postagem_automatica)
    t_post.daemon = True
    t_post.start()
    
    while True:
        time.sleep(60)
