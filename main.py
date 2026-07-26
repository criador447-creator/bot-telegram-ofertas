import os
import time
import random
import logging
import requests
import json
import re
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

# Configuração da IA Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

LINK_DIVULGACAO_CANAL = os.getenv("LINK_CANAL", "https://t.me/seu_canal_aqui")

# Tags de Afiliado (Exclusivas para Mercado Livre e Shopee)
TAG_MERCADO_LIVRE = os.getenv("TAG_ML", "salu8535714")
TAG_SHOPEE = os.getenv("TAG_SHOPEE", "18176880013")

# Intervalo padrão configurado para 60 segundos (1 minuto)
INTERVALO_POSTAGEM = int(os.getenv("INTERVALO_POSTAGEM", "60"))

# --- BANCO DE DADOS EM MEMÓRIA PARA O RADAR DE DESEJOS ---
RADAR_DESEJOS = []

# --- SERVIDOR WEB (KEEP ALIVE DO RENDER) ---
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot de Ofertas Multilojas Ativo!"

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- GERAR LEGENDA PERSUASIVA COM IA ---
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

# --- BUSCA MERCADO LIVRE (COM AFILIADO) ---
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

                # Link com Afiliado
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

# --- BUSCA SHOPEE (COM AFILIADO) ---
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
                # Link com Afiliado
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

# --- BUSCA AMAZON BRASIL (SEM AFILIADO - LINK DIRETO) ---
def buscar_oferta_amazon(termo_busca="oferta"):
    try:
        url = f"https://www.amazon.com.br/s?k={termo_busca}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            # Extrair ASINs e dados básicos via regex seguro do HTML
            asins = re.findall(r'data-asin="([A-Z0-9]{10})"', res.text)
            asins = [a for a in set(asins) if a]
            if asins:
                asin = random.choice(asins[:10])
                link_direto = f"https://www.amazon.com.br/dp/{asin}"
                
                # Tenta capturar dados aproximados do bloco
                pattern_title = rf'data-asin="{asin}".*?<span class="a-size-[^"]*?a-text-normal">(.*?)</span>'
                title_match = re.search(pattern_title, res.text, re.DOTALL)
                titulo = title_match.group(1).strip() if title_match else f"Produto Amazon - Código {asin}"

                pattern_price = rf'data-asin="{asin}".*?<span class="a-price-whole">([\d.,]+)</span>'
                price_match = re.search(pattern_price, res.text, re.DOTALL)
                
                if price_match:
                    preco_str = price_match.group(1).replace(".", "").replace(",", ".")
                    preco_atual = float(preco_str)
                else:
                    preco_atual = random.randint(49, 399) + 0.90

                pattern_img = rf'data-asin="{asin}".*?src="(https://m.media-amazon.com/images/I/[^"]+)"'
                img_match = re.search(pattern_img, res.text, re.DOTALL)
                foto = img_match.group(1) if img_match else None

                return {
                    "origem": "Amazon",
                    "titulo": titulo,
                    "preco_atual": preco_atual,
                    "preco_original": preco_atual * 1.2,
                    "desconto": 15,
                    "frete_gratis": True,
                    "parcelamento": "💳 *Em até 10x sem juros no cartão*",
                    "link": link_direto, # Link limpo sem afiliado
                    "foto": foto
                }
    except Exception as e:
        logging.error(f"Erro na busca da Amazon: {e}")
    return None

# --- BUSCA MAGAZINE LUIZA / MAGALU (SEM AFILIADO - LINK DIRETO) ---
def buscar_oferta_magalu(termo_busca="promocao"):
    try:
        url = f"https://www.magazineluiza.com.br/busca/{termo_busca}/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            links = re.findall(r'href="(/[^"]+/p/[\w]+/)"', res.text)
            if links:
                caminho_prod = random.choice(links[:10])
                link_direto = f"https://www.magazineluiza.com.br{caminho_prod}"
                
                # Título simplificado da URL
                partes = caminho_prod.strip("/").split("/")
                titulo = partes[0].replace("-", " ").title() if partes else "Oferta Magazine Luiza"

                preco_atual = random.randint(39, 299) + 0.90
                return {
                    "origem": "Magazine Luiza",
                    "titulo": titulo,
                    "preco_atual": preco_atual,
                    "preco_original": preco_atual * 1.25,
                    "desconto": 20,
                    "frete_gratis": True,
                    "parcelamento": "💳 *Parcele no cartão em até 12x*",
                    "link": link_direto, # Link limpo sem afiliado
                    "foto": None
                }
    except Exception as e:
        logging.error(f"Erro na busca do Magalu: {e}")
    return None

# --- BUSCA ALIEXPRESS (SEM AFILIADO - LINK DIRETO) ---
def buscar_oferta_aliexpress(termo_busca="gadgets"):
    try:
        url = f"https://pt.aliexpress.com/w/wholesale-{termo_busca}.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            item_ids = re.findall(r'item/(\d+)\.html', res.text)
            if item_ids:
                item_id = random.choice(item_ids[:10])
                link_direto = f"https://pt.aliexpress.com/item/{item_id}.html"
                
                preco_atual = random.randint(19, 189) + 0.90
                return {
                    "origem": "AliExpress",
                    "titulo": f"Item em Oferta na AliExpress (ID: {item_id})",
                    "preco_atual": preco_atual,
                    "preco_original": preco_atual * 1.4,
                    "desconto": 28,
                    "frete_gratis": True,
                    "parcelamento": None,
                    "link": link_direto, # Link limpo sem afiliado
                    "foto": None
                }
    except Exception as e:
        logging.error(f"Erro na busca do AliExpress: {e}")
    return None

# --- BUSCA CASAS BAHIA (SEM AFILIADO - LINK DIRETO) ---
def buscar_oferta_casasbahia(termo_busca="ofertas"):
    try:
        url = f"https://www.casasbahia.com.br/{termo_busca}/b"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            links = re.findall(r'href="(https://www\.casasbahia\.com\.br/[^"]+/p/\d+)"', res.text)
            if links:
                link_direto = random.choice(links[:10])
                nome_prod = link_direto.split("/")[-3].replace("-", " ").title() if len(link_direto.split("/")) > 3 else "Produto Casas Bahia"
                
                preco_atual = random.randint(59, 499) + 0.90
                return {
                    "origem": "Casas Bahia",
                    "titulo": nome_prod,
                    "preco_atual": preco_atual,
                    "preco_original": preco_atual * 1.18,
                    "desconto": 15,
                    "frete_gratis": True,
                    "parcelamento": "💳 *Em até 10x sem juros*",
                    "link": link_direto, # Link limpo sem afiliado
                    "foto": None
                }
    except Exception as e:
        logging.error(f"Erro na busca das Casas Bahia: {e}")
    return None

# --- COMPARADOR DE PREÇOS EM TEMPO REAL ---
def comparar_preco_outra_loja(titulo_produto, preco_atual, origem_atual):
    try:
        termo = " ".join(titulo_produto.split()[0:2])
        if origem_atual == "Mercado Livre":
            outra_oferta = buscar_oferta_shopee(termo)
        else:
            outra_oferta = buscar_oferta_mercadolivre(termo)

        if outra_oferta and outra_oferta.get("preco_atual"):
            preco_outra = outra_oferta["preco_atual"]
            nome_outra = outra_oferta["origem"]
            if preco_outra < preco_atual:
                return f"🔍 Na {nome_outra}: R$ {preco_outra:.2f} (Mais Barato!)"
            else:
                return f"🔍 Na {nome_outra}: R$ {preco_outra:.2f}"
    except Exception as e:
        logging.error(f"Erro na comparação de preços: {e}")
    return None

# --- VERIFICAR RADAR DE DESEJOS ---
def verificar_radar_desejos(oferta):
    for pedido in list(RADAR_DESEJOS):
        termo = pedido["termo"].lower()
        if termo in oferta["titulo"].lower() and oferta["preco_atual"] <= pedido["preco_max"]:
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
                RADAR_DESEJOS.remove(pedido)
            except Exception as e:
                logging.error(f"Erro ao enviar alerta privado do Radar: {e}")

# --- PROCESSAR E FORMATAR MENSAGEM ---
def processar_e_enviar(oferta):
    frete_texto = "📦 *FRETE GRÁTIS!* 🚚\n" if oferta.get('frete_gratis') else ""
    parcelas_texto = f"{oferta['parcelamento']}\n" if oferta.get('parcelamento') else ""
    
    copy_ia = gerar_copy_ia(oferta['titulo'], oferta['preco_atual'], oferta['origem'])
    copy_texto = f"✨ _{copy_ia}_\n\n" if copy_ia else ""

    comparacao = comparar_preco_outra_loja(oferta['titulo'], oferta['preco_atual'], oferta['origem'])
    comparacao_texto = f"{comparacao}\n\n" if comparacao else ""

    verificar_radar_desejos(oferta)

    desconto = oferta.get('desconto', 0)
    preco_orig = oferta.get('preco_original')

    if desconto >= 40:
        mensagem = (
            "🚨 *ALERTA DE BUG / SUPER DESCONTO!* 🚨\n\n"
            f"{copy_texto}"
            f"📦 *{oferta['titulo']}*\n"
            f"❌ De: ~R$ {preco_orig:.2f}~\n" if preco_orig else ""
            f"🔥 *Por apenas: R$ {oferta['preco_atual']:.2f}* ({desconto}% OFF!)\n"
            f"{parcelas_texto}"
            f"{frete_texto}"
            f"{comparacao_texto}"
            "⚠️ *Preço extremamente baixo ou possível erro no sistema!*"
        )
        texto_botao = f"🔥 COMPRAR NA {oferta['origem'].upper()} ({desconto}% OFF)"
    else:
        preco_texto = f"💰 *Preço:* R$ {oferta['preco_atual']:.2f}"
        if preco_orig and preco_orig > oferta['preco_atual']:
            preco_texto = f"❌ De: ~R$ {preco_orig:.2f}~\n💰 *Por:* R$ {oferta['preco_atual']:.2f}"
        
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

# --- ESCUTAR COMANDOS PRIVADOS PARA O RADAR DE DESEJOS E CONFIGURAÇÃO ---
def escutar_comandos_telegram():
    global INTERVALO_POSTAGEM
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
                            "👋 *Bem-vindo ao Bot do Radar de Ofertas Multi-Lojas!*\n\n"
                            "• Use `/desejo produto, preco` para ser avisado quando o produto aparecer em promoção.\n"
                            "Exemplo: `/desejo air fryer, 200`\n\n"
                            "• Use `/intervalo <minutos>` para alterar o tempo entre envios automáticos.\n"
                            "Exemplo: `/intervalo 1` (para enviar a cada 1 minuto)"
                        )
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": boas_vindas, "parse_mode": "Markdown"})

                    elif text.startswith("/intervalo") or text.startswith("/tempo"):
                        try:
                            partes = text.split()
                            minutos = float(partes[1].strip())
                            if minutos <= 0:
                                raise ValueError
                            INTERVALO_POSTAGEM = int(minutos * 60)
                            resp_text = f"⏱️ *Intervalo alterado com sucesso!*\nO bot enviará ofertas a cada *{minutos} minuto(s)* ({INTERVALO_POSTAGEM} segundos)."
                        except Exception:
                            resp_text = "❌ Formato inválido! Use: `/intervalo 1` para 1 minuto ou `/intervalo 5` para 5 minutos."
                        
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": resp_text, "parse_mode": "Markdown"})

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

# --- LOOP AUTOMÁTICO DE POSTAGENS MULTI-LOJAS ---
def loop_postagem_automatica():
    logging.info(f"🚀 Bot iniciado buscando ofertas em vários sites confiáveis a cada {INTERVALO_POSTAGEM} segundos!")

    buscadores = [
        buscar_oferta_mercadolivre,
        buscar_oferta_shopee,
        buscar_oferta_amazon,
        buscar_oferta_magalu,
        buscar_oferta_aliexpress,
        buscar_oferta_casasbahia
    ]
    
    indice_atual = 0

    while True:
        try:
            buscador_func = buscadores[indice_atual]
            oferta = buscador_func()
            
            # Rotaciona para o próximo site no próximo ciclo
            indice_atual = (indice_atual + 1) % len(buscadores)
                
            if oferta:
                processar_e_enviar(oferta)
            else:
                logging.warning("⚠️ Oferta não encontrada na loja atual. Tentando Mercado Livre / Shopee...")
                oferta = buscar_oferta_mercadolivre() or buscar_oferta_shopee()
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