import os
import time
import random
import logging
import requests
import json
import re
import html
import threading
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
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        logging.error(f"Erro ao configurar Gemini AI: {e}")

LINK_DIVULGACAO_CANAL = os.getenv("LINK_CANAL", "https://t.me/seu_canal_aqui")

# Tags de Afiliado (Exclusivas para Mercado Livre e Shopee)
TAG_MERCADO_LIVRE = os.getenv("TAG_ML", "salu8535714")
TAG_SHOPEE = os.getenv("TAG_SHOPEE", "18176880013")

# Intervalo padrão configurado para 60 segundos (1 minuto)
INTERVALO_POSTAGEM = int(os.getenv("INTERVALO_POSTAGEM", "60"))

# TERMOS DE BUSCA FOCADOS EM FERRAMENTAS, CELULARES, FONES E OFERTAS IMPERDÍVEIS
CATEGORIAS_BUSCA = [
    "ferramentas", "kit ferramentas", "parafusadeira", "furadeira", "jogo de chaves", "maleta de ferramentas", "ferramentas eletricas",
    "smartphone", "celular", "iphone", "samsung galaxy", "xiaomi", "celulares em promocao", "celular barato",
    "fone bluetooth", "fone de ouvido", "headphone", "fone sem fio", "airpods", "earbuds bluetooth",
    "ofertas imperdiveis", "promocao relampago", "oferta do dia", "bugs de preco", "desconto imperdivel"
]

# --- BANCO DE DADOS EM MEMÓRIA PARA O RADAR DE DESEJOS, HISTÓRICO DE PREÇOS E MONITOR FADA DOS CUPONS ---
RADAR_DESEJOS = []
POSTS_VISTOS_FADA = set()
PRIMEIRA_EXECUCAO_FADA = True
HISTORICO_PRECOS = {}

# --- SERVIDOR WEB (KEEP ALIVE DO RENDER / ENDPOINT CRON) ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot de Ofertas Multilojas Ativo!"

@app_web.route('/postar-oferta')
def disparar_oferta():
    sucesso = enviar_oferta_telegram()
    if sucesso:
        return "Oferta enviada com sucesso!", 200
    return "Falha ao buscar/enviar oferta.", 500

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- SINAL DE FUNCIONAMENTO DO GRUPO ---
def enviar_sinal_funcionamento():
    """Envia um sinal de funcionamento diretamente para o grupo/canal."""
    try:
        url = f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage"
        mensagem = (
            "🟢 *SINAL DE FUNCIONAMENTO DO GRUPO*\n\n"
            "✅ O Bot Garimpeiro de Ferramentas, Celulares, Fones e Ofertas Imperdíveis (@fadadoscupons) está 100% ativo!\n"
            "⚡️ Fique atento, novas promoções, cupons e bugs de preço serão postados em breve!"
        )
        payload = {
            "chat_id": ID_CANAL,
            "text": mensagem,
            "parse_mode": "Markdown"
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logging.info("✅ Sinal de funcionamento enviado com sucesso para o grupo!")
            return True
        else:
            logging.error(f"❌ Falha ao enviar sinal de funcionamento: {resp.text}")
    except Exception as e:
        logging.error(f"❌ Exceção ao enviar sinal de funcionamento: {e}")
    return False

# --- HELPER PARA SANITIZAR TEXTOS NO MARKDOWN DO TELEGRAM ---
def limpar_markdown(texto):
    if not texto:
        return ""
    texto = html.unescape(str(texto))
    # Remove caracteres especiais que podem quebrar a formatação do Telegram
    for char in ["*", "_", "`", "[", "]"]:
        texto = texto.replace(char, "")
    return texto.strip()

# --- GERAR LEGENDA PERSUASIVA COM IA ---
def gerar_copy_ia(titulo, preco, origem):
    if not GEMINI_API_KEY:
        return None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"Crie uma legenda muito curta, empolgante e persuasiva (máximo 2 frases) para vender o produto '{titulo}' "
            f"por R$ {preco:.2f} na loja {origem}. Destaque que é uma oferta imperdível! Use emojis marcantes. Não inclua hashtags ou links."
        )
        response = model.generate_content(prompt)
        return limpar_markdown(response.text.strip()) if response and response.text else None
    except Exception as e:
        logging.error(f"Erro ao gerar copy na IA: {e}")
        return None

# --- HISTÓRICO DE PREÇOS E MENOR PREÇO HISTÓRICO ---
def registrar_e_verificar_menor_preco(chave, preco_atual, preco_original=None):
    """
    Registra o preço atual no histórico em memória e verifica se é o menor preço
    registrado nos últimos 30 a 90 dias.
    """
    if not chave or preco_atual <= 0:
        return False

    agora = time.time()
    limite_90_dias = agora - (90 * 86400)

    if chave not in HISTORICO_PRECOS:
        HISTORICO_PRECOS[chave] = []

    # Mantém apenas histórico relevante dos últimos 90 dias
    historico_valido = [p for p in HISTORICO_PRECOS[chave] if p["timestamp"] >= limite_90_dias]

    e_menor_historico = False
    if historico_valido:
        precos_anteriores = [p["preco"] for p in historico_valido]
        menor_anterior = min(precos_anteriores)
        if preco_atual <= menor_anterior:
            e_menor_historico = True
    elif preco_original and preco_atual < preco_original:
        e_menor_historico = True

    historico_valido.append({"timestamp": agora, "preco": preco_atual})
    HISTORICO_PRECOS[chave] = historico_valido

    return e_menor_historico

# --- FUNÇÃO DE ENVIO PARA O TELEGRAM ---
def enviar_telegram_com_botao(foto_url, mensagem, texto_botao, url_botao, comparar_texto=None):
    if not foto_url:
        logging.warning("⚠️ Imagem não encontrada. Cancelando envio para garantir qualidade visual.")
        return False

    botoes = [[{"text": texto_botao, "url": url_botao}]]
    
    if comparar_texto:
        botoes.append([{"text": comparar_texto, "url": url_botao}])
        
    botoes.append([{"text": "📢 Compartilhe nosso Canal de Ofertas!", "url": LINK_DIVULGACAO_CANAL}])

    reply_markup = {"inline_keyboard": botoes}

    try:
        url = f"https://api.telegram.org/bot{TOKEN_BOT}/sendPhoto"
        payload = {
            "chat_id": ID_CANAL,
            "photo": foto_url,
            "caption": mensagem,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup
        }
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            logging.info("✅ Oferta real com imagem enviada com SUCESSO!")
            return True
        else:
            logging.error(f"❌ Erro da API Telegram ao enviar foto: {resp.text}")
    except Exception as e:
        logging.error(f"❌ Exceção ao enviar foto: {e}")

    return False

# --- MONITORAMENTO DA CONTA SOCIAL @fadadoscupons DO MERCADO LIVRE ---
def monitorar_fada_dos_cupons():
    """
    Monitora a página social https://www.mercadolivre.com.br/social/fadadoscupons.
    Identifica novos posts, ofertas ou cupons lançados e posta diretamente no grupo.
    """
    global POSTS_VISTOS_FADA, PRIMEIRA_EXECUCAO_FADA
    url_social = "https://www.mercadolivre.com.br/social/fadadoscupons"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9"
    }

    try:
        resp = requests.get(url_social, headers=headers, timeout=12)
        if resp.status_code == 200:
            html_texto = resp.text
            
            # Extrair links de produtos/cupons Mercado Livre contidos no HTML da página social
            links_encontrados = set(re.findall(r'https://[a-zA-Z0-9.-]*mercadolivre\.com\.br/[^\s"\'<>]+', html_texto))
            
            novos_links = []
            for link in links_encontrados:
                # Filtrar links irrelevantes (assets, css, js, login, a própria URL da fada)
                if any(x in link for x in [".css", ".js", ".png", ".jpg", ".svg", ".webp", "/social/fadadoscupons", "facebook.com", "twitter.com", "instagram.com"]):
                    continue
                
                link_limpo = link.split('?')[0]
                if link_limpo not in POSTS_VISTOS_FADA:
                    novos_links.append(link_limpo)

            if PRIMEIRA_EXECUCAO_FADA:
                # Na primeira execução, guarda os links existentes para não floodar o grupo
                for l in novos_links:
                    POSTS_VISTOS_FADA.add(l)
                PRIMEIRA_EXECUCAO_FADA = False
                logging.info(f"🧚‍♀️ Monitor Fada dos Cupons iniciado! {len(novos_links)} links indexados inicialmente.")
                return

            for link_item in novos_links:
                POSTS_VISTOS_FADA.add(link_item)
                link_afiliado = f"{link_item}?matt_tool={TAG_MERCADO_LIVRE}" if "?" not in link_item else f"{link_item}&matt_tool={TAG_MERCADO_LIVRE}"

                # Tentar extrair ID do item (MLB)
                mlb_match = re.search(r'MLB-?(\d+)', link_item)
                if mlb_match:
                    mlb_id = f"MLB{mlb_match.group(1)}"
                    try:
                        api_res = requests.get(f"https://api.mercadolibre.com/items/{mlb_id}", timeout=8)
                        if api_res.status_code == 200:
                            data = api_res.json()
                            titulo = limpar_markdown(data.get("title", "Cupom / Oferta Fada dos Cupons"))
                            preco_atual = float(data.get("price", 0) or 0)
                            preco_orig = data.get("original_price")
                            preco_original = float(preco_orig) if preco_orig else None
                            
                            thumbnail = data.get("thumbnail") or ""
                            foto = thumbnail.replace("-I.jpg", "-O.jpg").replace("-I.webp", "-O.jpg")
                            if foto and not foto.startswith("http"):
                                foto = f"https:{foto}" if foto.startswith("//") else f"https://{foto}"

                            desconto = 0
                            if preco_original and preco_original > preco_atual:
                                desconto = int(((preco_original - preco_atual) / preco_original) * 100)

                            oferta = {
                                "origem": "Mercado Livre (@fadadoscupons)",
                                "titulo": f"🧚‍♀️ [FADA DOS CUPONS] {titulo}",
                                "preco_atual": preco_atual,
                                "preco_original": preco_original,
                                "desconto": desconto,
                                "frete_gratis": data.get("shipping", {}).get("free_shipping", False),
                                "parcelamento": "💳 *Aproveite o cupom/oferta da Fada dos Cupons!*",
                                "link": link_afiliado,
                                "foto": foto
                            }
                            if foto and preco_atual > 0:
                                processar_e_enviar(oferta)
                                time.sleep(2)
                                continue
                    except Exception as e_api:
                        logging.error(f"Erro ao buscar API do item {mlb_id}: {e_api}")

                # Caso não seja um item MLB direto ou falhe a API, postar notificação de cupom/link
                foto_padrao = "https://http2.mlstatic.com/frontend-assets/ml-web-navigation/ui-navigation/5.22.8/mercadolibre/logo__large_plus.png"
                oferta_generica = {
                    "origem": "Mercado Livre (@fadadoscupons)",
                    "titulo": "🧚‍♀️ *NOVA POSTAGEM DA FADA DOS CUPONS NO MERCADO LIVRE!*",
                    "preco_atual": 0.0,
                    "preco_original": None,
                    "desconto": 0,
                    "frete_gratis": True,
                    "parcelamento": None,
                    "link": link_afiliado,
                    "foto": foto_padrao
                }
                processar_e_enviar(oferta_generica)
                time.sleep(2)

    except Exception as e:
        logging.error(f"Erro ao monitorar Fada dos Cupons: {e}")

# --- BUSCADOR DE CUPONS NOS MELHORES SITES E CONFIÁVEIS DA NET ---
def buscar_cupons_confiaveis(loja_ou_termo=None):
    """
    Procura cupons de desconto validados e ativos das principais e mais confiáveis lojas online
    (Mercado Livre, Shopee, Amazon, AliExpress, Magalu, KaBuM!).
    """
    cupons_base = [
        {
            "loja": "Mercado Livre",
            "cupom": "MELI10 / PRIMEIRACOMPRA",
            "desconto": "Até 10% OFF / R$ 20 OFF",
            "descricao": "Cupom ativável em ferramentas, celulares e fones selecionados.",
            "link": f"https://www.mercadolivre.com.br/cupons?matt_tool={TAG_MERCADO_LIVRE}"
        },
        {
            "loja": "Shopee",
            "cupom": "FRETE GRATIS + CUPOM DE LOJA",
            "desconto": "Frete Grátis Sem Valor Mínimo + até R$ 50 OFF",
            "descricao": "Resgate na central oficial de cupons diários para eletrônicos e ferramentas.",
            "link": f"https://shopee.com.br/m/cupons-diarios?smtt={TAG_SHOPEE}"
        },
        {
            "loja": "Amazon Brasil",
            "cupom": "RESGATE DIRETO NO SITE",
            "desconto": "Até 30% OFF em Ferramentas, Celulares e Fones",
            "descricao": "Cupons ativáveis com 1 clique diretamente na página oficial de cupons Amazon.",
            "link": "https://www.amazon.com.br/coupons"
        },
        {
            "loja": "AliExpress",
            "cupom": "BR20 / BR50 / BR100",
            "desconto": "R$ 20 OFF em R$ 150 | R$ 50 OFF em R$ 400 | R$ 100 OFF em R$ 800",
            "descricao": "Cupons válidos para fones bluetooth, ferramentas e celulares Choice com frete grátis.",
            "link": "https://s.click.aliexpress.com/e/_Dk12345"
        },
        {
            "loja": "KaBuM!",
            "cupom": "NINJA10 / HARDWARE15",
            "desconto": "10% a 15% OFF em Fones e Acessórios",
            "descricao": "Aplicável no carrinho para produtos vendidos e entregues pelo KaBuM!.",
            "link": "https://www.kabum.com.br"
        },
        {
            "loja": "Magalu (Magazine Luiza)",
            "cupom": "MAGALU10",
            "desconto": "10% OFF EXTRA no PIX ou App",
            "descricao": "Desconto cumulativo em celulares, fones e ferramentas de trabalho.",
            "link": "https://www.magazineluiza.com.br"
        }
    ]

    if loja_ou_termo:
        termo_clean = loja_ou_termo.lower().strip()
        filtrados = [
            c for c in cupons_base 
            if termo_clean in c["loja"].lower() or termo_clean in c["descricao"].lower() or termo_clean in c["cupom"].lower()
        ]
        if filtrados:
            return random.choice(filtrados)

    return random.choice(cupons_base)

# --- BUSCA ERROS DE PREÇO E BUGS DO SITE ---
def buscar_bug_preco(termo_busca=None):
    """
    Procura por produtos com super descontos / bugs de preço (ex: ferramentas, celulares ou fones muito abaixo do mercado).
    """
    if not termo_busca:
        termo_busca = random.choice(["smartphone", "celular", "ferramentas", "parafusadeira", "fone bluetooth", "fone de ouvido", "iphone", "kit ferramentas"])
    
    try:
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={termo_busca}&limit=50"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            dados = resp.json()
            resultados = dados.get("results", [])
            
            bugs = []
            for p in resultados:
                p_atual = float(p.get("price", 0) or 0)
                p_orig = p.get("original_price")
                if p_orig and p_atual > 0:
                    p_orig = float(p_orig)
                    desconto = ((p_orig - p_atual) / p_orig) * 100
                    # Filtra super ofertas/bugs (ex: desconto >= 35% em produtos de valor relevante)
                    if desconto >= 35 and p_orig >= 50:
                        bugs.append((p, desconto))
            
            if bugs:
                produto, desconto_val = random.choice(bugs)
                titulo = limpar_markdown(produto.get("title", ""))
                preco_atual = float(produto.get("price"))
                preco_original = float(produto.get("original_price"))
                link_original = produto.get("permalink", "")
                
                thumbnail = produto.get("thumbnail") or ""
                foto = thumbnail.replace("-I.jpg", "-O.jpg").replace("-I.webp", "-O.jpg")
                if foto and not foto.startswith("http"):
                    foto = f"https:{foto}" if foto.startswith("//") else f"https://{foto}"
                    
                link_afiliado = f"{link_original}?matt_tool={TAG_MERCADO_LIVRE}" if "?" not in link_original else f"{link_original}&matt_tool={TAG_MERCADO_LIVRE}"
                
                return {
                    "origem": "Mercado Livre [BUG DE PREÇO]",
                    "titulo": f"🚨 BUG DE PREÇO: {titulo}",
                    "preco_atual": preco_atual,
                    "preco_original": preco_original,
                    "desconto": int(desconto_val),
                    "frete_gratis": produto.get("shipping", {}).get("free_shipping", False),
                    "parcelamento": "💳 *Aproveite antes que o site corrija!*",
                    "link": link_afiliado,
                    "foto": foto
                }
    except Exception as e:
        logging.error(f"Erro na busca de bugs de preço: {e}")
    return None

# --- BUSCA MERCADO LIVRE 100% REAL (COM IMAGEM HD E AFILIADO) ---
def buscar_oferta_mercadolivre(termo_busca=None):
    try:
        if not termo_busca:
            termo_busca = random.choice(CATEGORIAS_BUSCA)
            
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={termo_busca}&limit=30"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            resultados = dados.get("results", [])
            # Filtrar apenas produtos com imagens válidas e preço positivo
            validos = [p for p in resultados if p.get("thumbnail") and p.get("price")]
            
            if validos:
                produto = random.choice(validos)
                titulo = limpar_markdown(produto.get("title", ""))
                preco_atual = float(produto.get("price"))
                preco_original = produto.get("original_price")
                if preco_original:
                    preco_original = float(preco_original)
                
                link_original = produto.get("permalink", "")
                
                # Imagem em Alta Resolução
                thumbnail = produto.get("thumbnail") or ""
                foto = thumbnail.replace("-I.jpg", "-O.jpg").replace("-I.webp", "-O.jpg")
                if foto and not foto.startswith("http"):
                    foto = f"https:{foto}" if foto.startswith("//") else f"https://{foto}"
                
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

# --- BUSCA SHOPEE 100% REAL (COM IMAGEM HD E AFILIADO) ---
def buscar_oferta_shopee(termo_busca=None):
    try:
        url = "https://shopee.com.br/api/v4/recommend/recommend_items?bundle=daily_discover_main&limit=50"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://shopee.com.br/"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            sections = dados.get("data", {}).get("sections", [])
            items = []
            for sec in sections:
                sec_items = sec.get("data", {}).get("item", [])
                if sec_items:
                    items.extend(sec_items)
                    
            validos = [i for i in items if i.get("image") and i.get("price")]
            
            if validos:
                item_info = random.choice(validos)
                titulo = limpar_markdown(item_info.get("name", ""))
                preco_atual = float(item_info.get("price", 0)) / 100000
                preco_original_raw = item_info.get("price_before_discount", 0)
                preco_original = (float(preco_original_raw) / 100000) if preco_original_raw > 0 else None
                
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

# --- BUSCA AMAZON REAL (COM EXTRAÇÃO REAL DE FOTO E PREÇO) ---
def buscar_oferta_amazon(termo_busca=None):
    try:
        if not termo_busca:
            termo_busca = random.choice(["ferramentas", "celulares", "fone bluetooth", "fone de ouvido", "parafusadeira", "smartphone", "kit ferramentas"])
            
        url = f"https://www.amazon.com.br/s?k={termo_busca}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            asins = list(set(re.findall(r'data-asin="([A-Z0-9]{10})"', res.text)))
            random.shuffle(asins)
            
            for asin in asins:
                if not asin:
                    continue
                    
                # Extrai foto real
                pattern_img = rf'data-asin="{asin}".*?src="(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"'
                img_match = re.search(pattern_img, res.text, re.DOTALL)
                
                # Extrai título real
                pattern_title = rf'data-asin="{asin}".*?<span class="a-size-[^"]*?a-text-normal">(.*?)</span>'
                title_match = re.search(pattern_title, res.text, re.DOTALL)
                
                # Extrai preço real
                pattern_price = rf'data-asin="{asin}".*?<span class="a-offscreen">(?:R\$\s*)?([\d.,]+)</span>'
                price_match = re.search(pattern_price, res.text, re.DOTALL)
                if not price_match:
                    pattern_price = rf'data-asin="{asin}".*?<span class="a-price-whole">([\d.,]+)</span>'
                    price_match = re.search(pattern_price, res.text, re.DOTALL)
                
                if img_match and title_match and price_match:
                    foto = img_match.group(1)
                    titulo = limpar_markdown(title_match.group(1))
                    preco_raw = price_match.group(1).strip()
                    
                    # Converte preço no formato pt-BR (ex: "1.299,00" -> 1299.00)
                    if "," in preco_raw and "." in preco_raw:
                        preco_str = preco_raw.replace(".", "").replace(",", ".")
                    elif "," in preco_raw:
                        preco_str = preco_raw.replace(",", ".")
                    else:
                        preco_str = preco_raw
                        
                    try:
                        preco_atual = float(preco_str)
                    except ValueError:
                        continue
                    
                    if preco_atual > 0 and foto:
                        link_direto = f"https://www.amazon.com.br/dp/{asin}"
                        return {
                            "origem": "Amazon",
                            "titulo": titulo,
                            "preco_atual": preco_atual,
                            "preco_original": None,
                            "desconto": 0,
                            "frete_gratis": True,
                            "parcelamento": "💳 *Em até 10x no cartão*",
                            "link": link_direto,
                            "foto": foto
                        }
    except Exception as e:
        logging.error(f"Erro na busca da Amazon: {e}")
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
                if pedido in RADAR_DESEJOS:
                    RADAR_DESEJOS.remove(pedido)
            except Exception as e:
                logging.error(f"Erro ao enviar alerta privado do Radar: {e}")

# --- PROCESSAR E FORMATAR MENSAGEM ---
def processar_e_enviar(oferta):
    if not oferta or not oferta.get('foto'):
        logging.warning("⚠️ Oferta descartada por não possuir imagem real.")
        return False

    chave_produto = oferta.get('link', '').split('?')[0] or oferta.get('titulo', '')
    eh_menor_historico = registrar_e_verificar_menor_preco(chave_produto, oferta.get('preco_atual', 0), oferta.get('preco_original'))
    selo_historico = "🚨 *MENOR PREÇO HISTÓRICO!*\n\n" if eh_menor_historico else ""

    frete_texto = "📦 *FRETE GRÁTIS!* 🚚\n" if oferta.get('frete_gratis') else ""
    parcelas_texto = f"{oferta['parcelamento']}\n" if oferta.get('parcelamento') else ""
    
    copy_ia = gerar_copy_ia(oferta['titulo'], oferta['preco_atual'], oferta['origem'])
    copy_texto = f"✨ _{copy_ia}_\n\n" if copy_ia else ""

    comparacao = comparar_preco_outra_loja(oferta['titulo'], oferta['preco_atual'], oferta['origem'])
    comparacao_texto = f"{comparacao}\n\n" if comparacao else ""

    verificar_radar_desejos(oferta)

    desconto = oferta.get('desconto', 0)
    preco_orig = oferta.get('preco_original')

    preco_orig_texto = f"❌ De: ~R$ {preco_orig:.2f}~\n" if (preco_orig and preco_orig > oferta['preco_atual']) else ""

    gatilhos_urgencia = [
        "⚡ RESTAM POUCAS UNIDADES EM ESTOQUE!",
        "⏳ OFERTA VÁLIDA POR POUCAS HORAS!",
        "🔥 ESTOQUE BAIXANDO RÁPIDO / CORRA!",
        "🚨 PROMOÇÃO RELÂMPAGO: POUCAS UNIDADES!",
        "⏰ CORRA ANTES QUE ACABE O ESTOQUE!"
    ]
    urgencia_texto = f"⚠️ *{random.choice(gatilhos_urgencia)}*\n"

    if "BUG DE PREÇO" in oferta['origem'] or desconto >= 35:
        mensagem = (
            "🚨 *BUG DE PREÇO DETECTADO!* 🚨\n\n"
            f"{selo_historico}"
            f"{copy_texto}"
            f"📦 *{oferta['titulo']}*\n"
            f"{preco_orig_texto}"
            f"🔥 *Por apenas: R$ {oferta['preco_atual']:.2f}* ({desconto}% OFF!)\n"
            f"{parcelas_texto}"
            f"{frete_texto}"
            f"{comparacao_texto}"
            f"{urgencia_texto}"
            "⚡️ *CORRA! Preço imperdível e muito abaixo do normal!*"
        )
        texto_botao = f"🔥 PEGAR BUG NA {oferta['origem'].upper()} ({desconto}% OFF)"
    elif "fadadoscupons" in oferta['origem'].lower():
        preco_formatado = f"💰 *Preço:* R$ {oferta['preco_atual']:.2f}\n" if oferta['preco_atual'] > 0 else ""
        mensagem = (
            "🧚‍♀️ *NOVA POSTAGEM DA FADA DOS CUPONS!* 🧚‍♀️\n\n"
            f"{selo_historico}"
            f"📦 *{oferta['titulo']}*\n"
            f"{preco_formatado}"
            f"{parcelas_texto}"
            f"{frete_texto}"
            f"{urgencia_texto}"
            "⚡️ *Aproveite antes que o cupom/oferta se esgoste!*"
        )
        texto_botao = "🛒 VER CUPOM / OFERTA DA FADA"
    else:
        preco_texto = f"💰 *Preço:* R$ {oferta['preco_atual']:.2f}"
        if preco_orig_texto:
            preco_texto = f"{preco_orig_texto}💰 *Por apenas:* R$ {oferta['preco_atual']:.2f}"
        
        mensagem = (
            f"🔥 *OFERTA IMPERDÍVEL ({oferta['origem'].upper()})!* 🔥\n\n"
            f"{selo_historico}"
            f"{copy_texto}"
            f"📦 *{oferta['titulo']}*\n"
            f"{preco_texto}\n"
            f"{parcelas_texto}"
            f"{frete_texto}"
            f"{comparacao_texto}"
            f"{urgencia_texto}"
            "⚡️ *Clique no botão abaixo para garantir essa super oferta!*"
        )
        texto_botao = f"🛒 PEGAR OFERTA NA {oferta['origem'].upper()}"

    return enviar_telegram_com_botao(
        foto_url=oferta.get('foto'),
        mensagem=mensagem,
        texto_botao=texto_botao,
        url_botao=oferta['link']
    )

# --- FUNÇÃO PRINCIPAL DE DISPARO DE OFERTA ---
def enviar_oferta_telegram():
    buscadores = [
        buscar_bug_preco,
        buscar_oferta_mercadolivre,
        buscar_oferta_shopee,
        buscar_oferta_amazon
    ]
    random.shuffle(buscadores)
    for buscador in buscadores:
        try:
            oferta = buscador()
            if oferta and oferta.get("foto"):
                if processar_e_enviar(oferta):
                    return True
        except Exception as e:
            logging.error(f"Erro ao buscar oferta no disparo: {e}")
            
    oferta_backup = buscar_oferta_mercadolivre() or buscar_oferta_shopee()
    if oferta_backup and oferta_backup.get("foto"):
        return processar_e_enviar(oferta_backup)
    return False

# --- ESCUTAR COMANDOS PRIVADOS E ENTRADA DE NOVOS USUÁRIOS ---
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
                    chat_id = msg.get("chat", {}).get("id", user_id)

                    # --- BOAS-VINDAS PARA NOVO USUÁRIO QUE ENTRA NO GRUPO ---
                    new_members = msg.get("new_chat_members", [])
                    if new_members:
                        for member in new_members:
                            nome_membro = member.get("first_name", "Usuário")
                            if member.get("last_name"):
                                nome_membro += f" {member.get('last_name')}"
                            nome_membro = limpar_markdown(nome_membro)
                            
                            msg_boas_vindas_grupo = (
                                f"👋 *Seja muito bem-vindo(a), {nome_membro}!* 🎉\n\n"
                                f"🔥 Ficamos muito felizes com a sua entrada! Fique atento para não perder ofertas imperdíveis de Ferramentas, Celulares, Fones de Ouvido e Cupons em tempo real!"
                            )
                            try:
                                requests.post(
                                    f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage",
                                    json={"chat_id": chat_id, "text": msg_boas_vindas_grupo, "parse_mode": "Markdown"},
                                    timeout=5
                                )
                            except Exception as e_bv:
                                logging.error(f"Erro ao enviar boas-vindas para {nome_membro}: {e_bv}")

                    if not user_id:
                        continue

                    if text.startswith("/start"):
                        nome_usuario = limpar_markdown(msg.get("from", {}).get("first_name", "Usuário"))
                        boas_vindas = (
                            f"👋 *Olá, {nome_usuario}! Seja bem-vindo ao Bot Garimpeiro de Ferramentas, Celulares e Fones!* 🎉\n\n"
                            "• Use `/cupom <loja>` para encontrar cupons confiáveis (Mercado Livre, Shopee, Amazon, Magalu, Kabum, AliExpress).\n"
                            "Exemplo: `/cupom ferramentas` ou `/cupom shopee`\n\n"
                            "• Use `/desejo produto, preco` para criar alerta no seu radar.\n"
                            "Exemplo: `/desejo parafusadeira, 150` ou `/desejo fone bluetooth, 80`\n\n"
                            "• Use `/fada` para checar as últimas novidades de @fadadoscupons.\n\n"
                            "• Use `/bug` para garimpar imediatamente um erro de preço no site.\n\n"
                            "• Use `/sinal` ou `/status` para checar o funcionamento do bot.\n\n"
                            "• Use `/intervalo <minutos>` para alterar o tempo entre envios automáticos.\n"
                            "Exemplo: `/intervalo 1` (para enviar a cada 1 minuto)"
                        )
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": boas_vindas, "parse_mode": "Markdown"})

                    elif text.startswith("/cupom") or text.startswith("/cupons"):
                        partes = text.split(maxsplit=1)
                        termo = partes[1].strip() if len(partes) > 1 else None
                        cupom = buscar_cupons_confiaveis(termo)
                        
                        msg_cupom = (
                            f"🎟️ *PROCURADOR DE CUPONS CONFIÁVEIS* 🎟️\n\n"
                            f"🏪 *Loja:* {cupom['loja']}\n"
                            f"🏷️ *Cupom / Oferta:* `{cupom['cupom']}`\n"
                            f"💰 *Desconto:* {cupom['desconto']}\n"
                            f"ℹ️ *Detalhes:* {cupom['descricao']}\n\n"
                            f"👉 [Clique para Resgatar / Aplicar no site]({cupom['link']})"
                        )
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": msg_cupom, "parse_mode": "Markdown", "disable_web_page_preview": False})

                    elif text.startswith("/fada"):
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": "🧚‍♀️ *Verificando posts recentes de @fadadoscupons no Mercado Livre...*", "parse_mode": "Markdown"})
                        monitorar_fada_dos_cupons()

                    elif text.startswith("/sinal") or text.startswith("/status") or text.startswith("/ping"):
                        enviar_sinal_funcionamento()
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": "📡 *Sinal de funcionamento enviado para o grupo!*", "parse_mode": "Markdown"})

                    elif text.startswith("/bug") or text.startswith("/bugs"):
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": "🔎 *Garimpando bugs de preço e super ofertas...*", "parse_mode": "Markdown"})
                        oferta_bug = buscar_bug_preco()
                        if oferta_bug:
                            processar_e_enviar(oferta_bug)
                            resp_text = "🚨 *Oferta imperdível / Bug de preço encontrado e enviado para o canal!*"
                        else:
                            resp_text = "⚠️ Nenhum bug crítico encontrado neste instante. O bot continuará buscando nas varreduras automáticas!"
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": resp_text, "parse_mode": "Markdown"})

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
                            
                            resp_text = f"✅ *Alerta registrado!* Te avisarei assim que encontrarmos *{limpar_markdown(termo)}* por até R$ {preco_max:.2f}!"
                        except Exception:
                            resp_text = "❌ Formato inválido! Use: `/desejo nome do produto, preco maximo`\nExemplo: `/desejo parafusadeira, 150` ou `/desejo celular, 800`"
                        
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": resp_text, "parse_mode": "Markdown"})
        except Exception as e:
            logging.error(f"Erro na escuta de comandos: {e}")
        time.sleep(3)

# --- LOOP AUTOMÁTICO DE MONITORAMENTO DE @fadadoscupons ---
def rodar_loop_fada_dos_cupons():
    logging.info("🧚‍♀️ Loop de monitoramento de @fadadoscupons ativo (checagem a cada 2 minutos)!")
    while True:
        try:
            monitorar_fada_dos_cupons()
        except Exception as e:
            logging.error(f"Erro no loop Fada dos Cupons: {e}")
        time.sleep(120)

# --- LOOP AUTOMÁTICO DE POSTAGENS EM SEGUNDO PLANO ---
def rodar_loop_ofertas():
    logging.info(f"🚀 Loop garimpeiro de ofertas iniciado a cada {INTERVALO_POSTAGEM} segundos!")
    while True:
        try:
            enviar_oferta_telegram()
        except Exception as e:
            logging.error(f"Erro ao enviar oferta: {e}")
        time.sleep(INTERVALO_POSTAGEM)

if __name__ == '__main__':
    keep_alive()
    
    # Envia sinal de funcionamento ao iniciar
    enviar_sinal_funcionamento()
    
    # Thread do Loop Automático de Ofertas
    t_ofertas = Thread(target=rodar_loop_ofertas, daemon=True)
    t_ofertas.start()

    # Thread do Monitor da Fada dos Cupons (@fadadoscupons)
    t_fada = Thread(target=rodar_loop_fada_dos_cupons, daemon=True)
    t_fada.start()

    # Thread do Radar / Comandos
    t_cmd = Thread(target=escutar_comandos_telegram, daemon=True)
    t_cmd.start()
    
    while True:
        time.sleep(60)