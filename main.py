import os
import time
import random
import logging
import requests
import json
import re
import html
import io
import threading
import google.generativeai as genai
from PIL import Image
from threading import Thread
from flask import Flask, render_template_string

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

# Intervalo padrão configurado para 60 segundos (1 minuto) para manter 24 horas ativas
INTERVALO_POSTAGEM = int(os.getenv("INTERVALO_POSTAGEM", "60"))

# TERMOS DE BUSCA FOCADOS EM PRODUTOS MAIS VENDIDOS E CAMPEÕES DE VENDAS DO MÊS
CATEGORIAS_BUSCA = [
    "mais vendidos do mes", "campeoes de vendas", "top vendas", "ferramentas mais vendidas", "kit ferramentas profissional", 
    "parafusadeira furadeira", "jogo de chaves", "maleta de ferramentas", "smartphone mais vendido", "celulares em promocao", 
    "samsung galaxy", "xiaomi", "iphone", "fone bluetooth mais vendido", "fone de ouvido sem fio", "airpods", 
    "ofertas imperdiveis", "promocao relampago", "oferta do dia", "bugs de preco", "desconto imperdivel"
]

# --- BANCO DE DADOS EM MEMÓRIA PARA O RADAR DE DESEJOS, HISTÓRICO DE PREÇOS E MONITOR FADA DOS CUPONS ---
RADAR_DESEJOS = []
POSTS_VISTOS_FADA = set()
PRIMEIRA_EXECUCAO_FADA = True
HISTORICO_PRECOS = {}

# --- SERVIDOR WEB (KEEP ALIVE 24H PARA RENDER / REPLIT / HEROKU) ---
app_web = Flask(__name__)

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot de Ofertas Imperdíveis 24h</title>
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --success: #22c55e;
            --error: #ef4444;
            --border: #334155;
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        body {
            background-color: var(--bg);
            color: var(--text);
            display: flex;
            flex-direction: column;
            min-height: 100vh;
            padding: 1rem;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            width: 100%;
            flex: 1;
        }
        header {
            text-align: center;
            padding: 2rem 1rem;
        }
        header h1 {
            font-size: clamp(1.5rem, 5vw, 2.5rem);
            margin-bottom: 0.5rem;
            color: #ffffff;
        }
        header p {
            color: var(--text-muted);
            font-size: clamp(0.9rem, 3vw, 1.1rem);
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(34, 197, 94, 0.1);
            color: var(--success);
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-weight: 600;
            font-size: 0.9rem;
            margin-top: 1rem;
            border: 1px solid rgba(34, 197, 94, 0.2);
        }
        .status-dot {
            width: 10px;
            height: 10px;
            background-color: var(--success);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px var(--success);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }
        .alert {
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 1rem 0;
            text-align: center;
            font-weight: 600;
        }
        .alert-success {
            background: rgba(34, 197, 94, 0.15);
            color: var(--success);
            border: 1px solid rgba(34, 197, 94, 0.3);
        }
        .alert-error {
            background: rgba(239, 68, 68, 0.15);
            color: var(--error);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin: 2rem 0;
        }
        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            padding: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .card h2 {
            font-size: 1.25rem;
            margin-bottom: 0.75rem;
            color: var(--text);
        }
        .card p {
            color: var(--text-muted);
            font-size: 0.95rem;
            line-height: 1.5;
            margin-bottom: 1rem;
        }
        .stat-item {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--border);
        }
        .stat-item:last-child {
            border-bottom: none;
        }
        .btn {
            display: inline-block;
            width: 100%;
            text-align: center;
            background-color: var(--primary);
            color: white;
            padding: 0.75rem 1.25rem;
            border-radius: 0.5rem;
            text-decoration: none;
            font-weight: 600;
            transition: background-color 0.2s;
            border: none;
            cursor: pointer;
            box-sizing: border-border;
        }
        .btn:hover {
            background-color: var(--primary-hover);
        }
        .btn-secondary {
            background-color: transparent;
            border: 1px solid var(--border);
            color: var(--text);
            margin-top: 0.5rem;
        }
        .btn-secondary:hover {
            background-color: var(--border);
        }
        footer {
            text-align: center;
            padding: 1.5rem;
            color: var(--text-muted);
            font-size: 0.875rem;
            border-top: 1px solid var(--border);
            margin-top: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Bot de Ofertas Imperdíveis 24h</h1>
            <p>Monitoramento automático de promoções, cupons e bugs de preço</p>
            <div class="status-badge">
                <span class="status-dot"></span> Sistema Ativo 24/7
            </div>
        </header>

        {% if mensagem %}
        <div class="alert alert-{{ status_class }}">
            {{ mensagem }}
        </div>
        {% endif %}

        <div class="grid">
            <div class="card">
                <div>
                    <h2>🚀 Disparar Oferta</h2>
                    <p>Força a busca e o envio imediato de uma oferta imperdível para o canal do Telegram.</p>
                </div>
                <a href="/postar-oferta" class="btn">Disparar Agora</a>
            </div>

            <div class="card">
                <div>
                    <h2>📊 Status do Bot</h2>
                    <div class="stat-item">
                        <span>Intervalo de postagem</span>
                        <strong>{{ intervalo }}s</strong>
                    </div>
                    <div class="stat-item">
                        <span>Links Fada dos Cupons</span>
                        <strong>{{ total_fada }}</strong>
                    </div>
                    <div class="stat-item">
                        <span>Radar de Desejos</span>
                        <strong>{{ total_radar }}</strong>
                    </div>
                </div>
                {% if mensagem %}
                <a href="/" class="btn btn-secondary">Voltar ao Painel</a>
                {% endif %}
            </div>
        </div>
    </div>
    <footer>
        &copy; Bot de Ofertas Imperdíveis 24h &bull; Layout Responsivo
    </footer>
</body>
</html>
"""

@app_web.route('/')
def home():
    return render_template_string(
        HTML_LAYOUT,
        intervalo=INTERVALO_POSTAGEM,
        total_fada=len(POSTS_VISTOS_FADA),
        total_radar=len(RADAR_DESEJOS)
    ), 200

@app_web.route('/postar-oferta')
def disparar_oferta():
    sucesso = enviar_oferta_telegram()
    mensagem = "Oferta imperdível enviada com sucesso!" if sucesso else "Falha ao buscar/enviar oferta."
    status_class = "success" if sucesso else "error"
    
    return render_template_string(
        HTML_LAYOUT,
        mensagem=mensagem,
        status_class=status_class,
        intervalo=INTERVALO_POSTAGEM,
        total_fada=len(POSTS_VISTOS_FADA),
        total_radar=len(RADAR_DESEJOS)
    ), (200 if sucesso else 500)

def run_web():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- PING AUTO-REPOSITÓRIO PARA MANTER 24 HORAS LIGADO ---
def auto_ping():
    while True:
        try:
            port = os.environ.get('PORT', '8080')
            requests.get(f"http://127.0.0.1:{port}/", timeout=5)
        except Exception:
            pass
        time.sleep(180) # Ping a cada 3 minutos

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
            f"por R$ {preco:.2f} na loja {origem}. Destaque que é uma OFERTA IMPERDÍVEL 24H e campeã de vendas! Use emojis marcantes. Não inclua hashtags ou links."
        )
        response = model.generate_content(prompt)
        if response and hasattr(response, 'text') and response.text:
            return limpar_markdown(response.text.strip())
    except Exception as e:
        logging.error(f"Erro ao gerar copy na IA: {e}")
    return None

# --- IDENTIFICAR PRODUTO POR IMAGEM / OCR COM GEMINI ---
def identificar_produto_por_imagem(image_bytes):
    if not GEMINI_API_KEY:
        logging.warning("⚠️ GEMINI_API_KEY não configurada para análise de imagem.")
        return None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        image = Image.open(io.BytesIO(image_bytes))
        prompt = (
            "Analise este print/imagem de anúncio ou produto de loja online. "
            "Identifique o nome exato do produto, marca e modelo apresentados. "
            "Retorne APENAS o nome do produto de forma concisa para busca (máximo 6 palavras). Não inclua explicações ou pontuação extra."
        )
        response = model.generate_content([prompt, image])
        if response and hasattr(response, 'text') and response.text:
            return limpar_markdown(response.text.strip())
    except Exception as e:
        logging.error(f"Erro ao identificar produto por imagem com Gemini: {e}")
    return None

# --- HISTÓRICO DE PREÇOS E MENOR PREÇO HISTÓRICO ---
def registrar_e_verificar_menor_preco(chave, preco_atual, preco_original=None):
    if not chave or preco_atual <= 0:
        return False

    agora = time.time()
    limite_90_dias = agora - (90 * 86400)

    if chave not in HISTORICO_PRECOS:
        HISTORICO_PRECOS[chave] = []

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
        
    botoes.append([{"text": "📢 Entrar no Canal Oficial de Ofertas 24h", "url": LINK_DIVULGACAO_CANAL}])

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
            logging.info("✅ Oferta imperdível 24h enviada com SUCESSO!")
            return True
        else:
            logging.error(f"❌ Erro da API Telegram ao enviar foto: {resp.text}")
    except Exception as e:
        logging.error(f"❌ Exceção ao enviar foto: {e}")

    return False

# --- MONITORAMENTO DA CONTA SOCIAL @fadadoscupons DO MERCADO LIVRE ---
def monitorar_fada_dos_cupons():
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
            
            links_encontrados = set(re.findall(r'https://[a-zA-Z0-9.-]*mercadolivre\.com\.br/[^\s"\'<>]+', html_texto))
            
            novos_links = []
            for link in links_encontrados:
                if any(x in link for x in [".css", ".js", ".png", ".jpg", ".svg", ".webp", "/social/fadadoscupons", "facebook.com", "twitter.com", "instagram.com"]):
                    continue
                
                link_limpo = link.split('?')[0]
                if link_limpo not in POSTS_VISTOS_FADA:
                    novos_links.append(link_limpo)

            if PRIMEIRA_EXECUCAO_FADA:
                for l in novos_links:
                    POSTS_VISTOS_FADA.add(l)
                PRIMEIRA_EXECUCAO_FADA = False
                logging.info(f"🧚‍♀️ Monitor Fada dos Cupons iniciado! {len(novos_links)} links indexados inicialmente.")
                return

            for link_item in novos_links:
                POSTS_VISTOS_FADA.add(link_item)
                link_afiliado = f"{link_item}?matt_tool={TAG_MERCADO_LIVRE}" if "?" not in link_item else f"{link_item}&matt_tool={TAG_MERCADO_LIVRE}"

                mlb_match = re.search(r'MLB-?(\d+)', link_item)
                if mlb_match:
                    mlb_id = f"MLB{mlb_match.group(1)}"
                    try:
                        api_res = requests.get(f"https://api.mercadolibre.com/items/{mlb_id}", timeout=8)
                        if api_res.status_code == 200:
                            data = api_res.json()
                            titulo = limpar_markdown(data.get("title", "Cupom / Oferta Imperdível Fada dos Cupons"))
                            preco_atual = float(data.get("price", 0) or 0)
                            preco_orig = data.get("original_price")
                            preco_original = float(preco_orig) if preco_orig else None
                            
                            sold_qty = data.get("sold_quantity", 0)
                            destaque_vendas = f"🔥 *OFERTA IMPERDÍVEL FADA ({sold_qty}+ unidades vendidas!)*\n" if sold_qty >= 5 else ""

                            thumbnail = data.get("thumbnail") or ""
                            foto = thumbnail.replace("-I.jpg", "-O.jpg").replace("-I.webp", "-O.jpg")
                            if foto and not foto.startswith("http"):
                                foto = f"https:{foto}" if foto.startswith("//") else f"https://{foto}"

                            desconto = 0
                            if preco_original and preco_original > preco_atual:
                                desconto = int(((preco_original - preco_atual) / preco_original) * 100)

                            oferta = {
                                "origem": "Mercado Livre (@fadadoscupons)",
                                "titulo": f"🧚‍♀️ [OFERTA IMPERDÍVEL FADA] {titulo}",
                                "preco_atual": preco_atual,
                                "preco_original": preco_original,
                                "desconto": desconto,
                                "frete_gratis": data.get("shipping", {}).get("free_shipping", False),
                                "parcelamento": "💳 *Aproveite a oferta imperdível 24h!*",
                                "vendas": destaque_vendas,
                                "link": link_afiliado,
                                "foto": foto
                            }
                            if foto and preco_atual > 0:
                                processar_e_enviar(oferta)
                                time.sleep(2)
                                continue
                    except Exception as e_api:
                        logging.error(f"Erro ao buscar API do item {mlb_id}: {e_api}")

                foto_padrao = "https://http2.mlstatic.com/frontend-assets/ml-web-navigation/ui-navigation/5.22.8/mercadolibre/logo__large_plus.png"
                oferta_generica = {
                    "origem": "Mercado Livre (@fadadoscupons)",
                    "titulo": "🧚‍♀️ *OFERTA IMPERDÍVEL DA FADA DOS CUPONS NO MERCADO LIVRE!*",
                    "preco_atual": 0.0,
                    "preco_original": None,
                    "desconto": 0,
                    "frete_gratis": True,
                    "parcelamento": None,
                    "vendas": "",
                    "link": link_afiliado,
                    "foto": foto_padrao
                }
                processar_e_enviar(oferta_generica)
                time.sleep(2)

    except Exception as e:
        logging.error(f"Erro ao monitorar Fada dos Cupons: {e}")

# --- BUSCADOR DE CUPONS NOS MELHORES SITES E CONFIÁVEIS DA NET ---
def buscar_cupons_confiaveis(loja_ou_termo=None):
    cupons_base = [
        {
            "loja": "Mercado Livre",
            "cupom": "MELI10 / PRIMEIRACOMPRA",
            "desconto": "Até 10% OFF / R$ 20 OFF",
            "descricao": "Cupom ativável em ferramentas, celulares e fones mais vendidos.",
            "link": f"https://www.mercadolivre.com.br/cupons?matt_tool={TAG_MERCADO_LIVRE}"
        },
        {
            "loja": "Shopee",
            "cupom": "FRETE GRATIS + CUPOM DE LOJA",
            "desconto": "Frete Grátis Sem Valor Mínimo + até R$ 50 OFF",
            "descricao": "Resgate na central oficial de cupons diários imperdíveis 24h.",
            "link": f"https://shopee.com.br/m/cupons-diarios?smtt={TAG_SHOPEE}"
        },
        {
            "loja": "Amazon Brasil",
            "cupom": "RESGATE DIRETO NO SITE",
            "desconto": "Até 30% OFF em Ferramentas, Celulares e Fones",
            "descricao": "Cupons imperdíveis ativáveis com 1 clique.",
            "link": "https://www.amazon.com.br/coupons"
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
    if not termo_busca:
        termo_busca = random.choice(["mais vendidos", "smartphone", "celular", "ferramentas", "parafusadeira", "fone bluetooth", "fone de ouvido", "iphone", "kit ferramentas"])
    
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
                    if desconto >= 35 and p_orig >= 50:
                        bugs.append((p, desconto))
            
            if bugs:
                bugs.sort(key=lambda x: x[0].get("sold_quantity", 0), reverse=True)
                produto, desconto_val = random.choice(bugs[:10]) if len(bugs) >= 10 else random.choice(bugs)
                
                titulo = limpar_markdown(produto.get("title", ""))
                preco_atual = float(produto.get("price", 0) or 0)
                preco_original = float(produto.get("original_price", 0) or 0)
                link_original = produto.get("permalink", "")
                sold_qty = produto.get("sold_quantity", 0)
                
                destaque_vendas = f"🚨 *OFERTA IMPERDÍVEL / BUG DE PREÇO ({sold_qty}+ vendidos)*\n" if sold_qty >= 10 else ""

                thumbnail = produto.get("thumbnail") or ""
                foto = thumbnail.replace("-I.jpg", "-O.jpg").replace("-I.webp", "-O.jpg")
                if foto and not foto.startswith("http"):
                    foto = f"https:{foto}" if foto.startswith("//") else f"https://{foto}"
                    
                link_afiliado = f"{link_original}?matt_tool={TAG_MERCADO_LIVRE}" if "?" not in link_original else f"{link_original}&matt_tool={TAG_MERCADO_LIVRE}"
                
                return {
                    "origem": "Mercado Livre [BUG / IMPERDÍVEL]",
                    "titulo": f"🚨 OFERTA IMPERDÍVEL: {titulo}",
                    "preco_atual": preco_atual,
                    "preco_original": preco_original,
                    "desconto": int(desconto_val),
                    "frete_gratis": produto.get("shipping", {}).get("free_shipping", False),
                    "parcelamento": "💳 *Aproveite esta oferta imperdível agora!*",
                    "vendas": destaque_vendas,
                    "link": link_afiliado,
                    "foto": foto
                }
    except Exception as e:
        logging.error(f"Erro na busca de bugs de preço: {e}")
    return None

# --- BUSCA MERCADO LIVRE 100% REAL FOCADA NOS PRODUTOS MAIS VENDIDOS ---
def buscar_oferta_mercadolivre(termo_busca=None):
    try:
        if not termo_busca:
            termo_busca = random.choice(CATEGORIAS_BUSCA)
            
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={termo_busca}&limit=50"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            resultados = dados.get("results", [])
            validos = [p for p in resultados if p.get("thumbnail") and p.get("price")]
            
            if validos:
                mais_vendidos = [p for p in validos if p.get("sold_quantity", 0) >= 5]
                candidatos = mais_vendidos if mais_vendidos else validos
                candidatos.sort(key=lambda x: x.get("sold_quantity", 0), reverse=True)
                
                produto = random.choice(candidatos[:15])
                
                titulo = limpar_markdown(produto.get("title", ""))
                preco_atual = float(produto.get("price"))
                preco_original = produto.get("original_price")
                sold_qty = produto.get("sold_quantity", 0)
                
                if preco_original:
                    preco_original = float(preco_original)
                
                link_original = produto.get("permalink", "")
                
                thumbnail = produto.get("thumbnail") or ""
                foto = thumbnail.replace("-I.jpg", "-O.jpg").replace("-I.webp", "-O.jpg")
                if foto and not foto.startswith("http"):
                    foto = f"https:{foto}" if foto.startswith("//") else f"https://{foto}"
                
                shipping = produto.get("shipping", {}) or {}
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
                
                destaque_vendas = f"🏆 *OFERTA IMPERDÍVEL 24H ({sold_qty}+ vendidos)*\n" if sold_qty >= 10 else ""

                return {
                    "origem": "Mercado Livre",
                    "titulo": titulo,
                    "preco_atual": preco_atual,
                    "preco_original": preco_original,
                    "desconto": desconto,
                    "frete_gratis": frete_gratis,
                    "parcelamento": parcelamento_texto,
                    "vendas": destaque_vendas,
                    "link": link_afiliado,
                    "foto": foto
                }
    except Exception as e:
        logging.error(f"Erro na busca do Mercado Livre: {e}")
    return None

# --- BUSCA SHOPEE 100% REAL FOCADA NOS PRODUTOS MAIS VENDIDOS ---
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
            sections = (dados.get("data") or {}).get("sections") or []
            items = []
            for sec in sections:
                sec_items = (sec.get("data") or {}).get("item") or (sec.get("data") or {}).get("items") or []
                if sec_items:
                    items.extend(sec_items)
                    
            validos = [i for i in items if i.get("image") and i.get("price")]
            
            if validos:
                validos.sort(key=lambda x: (x.get("historical_sold") or x.get("sold") or 0), reverse=True)
                item_info = random.choice(validos[:15])
                
                titulo = limpar_markdown(item_info.get("name", ""))
                preco_atual = float(item_info.get("price", 0)) / 100000
                preco_original_raw = item_info.get("price_before_discount", 0)
                preco_original = (float(preco_original_raw) / 100000) if preco_original_raw > 0 else None
                
                sold_qty = item_info.get("historical_sold") or item_info.get("sold") or 0
                destaque_vendas = f"🏆 *OFERTA IMPERDÍVEL SHOPEE ({sold_qty}+ vendidos)*\n" if sold_qty >= 10 else ""

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
                    "vendas": destaque_vendas,
                    "link": link_afiliado,
                    "foto": foto
                }
    except Exception as e:
        logging.error(f"Erro na busca da Shopee: {e}")
    return None

# --- BUSCA AMAZON REAL ---
def buscar_oferta_amazon(termo_busca=None):
    try:
        if not termo_busca:
            termo_busca = random.choice(["mais vendidos", "ferramentas mais vendidas", "celulares mais vendidos", "fone bluetooth mais vendido"])
            
        url = f"https://www.amazon.com.br/s?k={termo_busca}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            blocks = res.text.split('data-asin="')
            candidates = []
            
            for block in blocks[1:]:
                asin = block[:10]
                if not re.match(r'^[A-Z0-9]{10}$', asin):
                    continue
                
                img_match = re.search(r'src="(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"', block)
                title_match = re.search(r'class="a-size-[^"]*?a-text-normal">(.*?)</span>', block)
                price_match = re.search(r'class="a-offscreen">(?:R\$\s*)?([\d.,]+)</span>', block)
                if not price_match:
                    price_match = re.search(r'class="a-price-whole">([\d.,]+)</span>', block)
                
                if img_match and title_match and price_match:
                    foto = img_match.group(1)
                    titulo = limpar_markdown(title_match.group(1))
                    preco_raw = price_match.group(1).strip()
                    
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
                        candidates.append({
                            "origem": "Amazon",
                            "titulo": titulo,
                            "preco_atual": preco_atual,
                            "preco_original": None,
                            "desconto": 0,
                            "frete_gratis": True,
                            "parcelamento": "💳 *Em até 10x no cartão*",
                            "vendas": "🏆 *OFERTA IMPERDÍVEL AMAZON 24H*\n",
                            "link": link_direto,
                            "foto": foto
                        })
            
            if candidates:
                return random.choice(candidates)
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
                f"🎯 *ALERTA IMPERDÍVEL DO SEU RADAR 24H!*\n\n"
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

# --- PROCESSAR E FORMATAR MENSAGEM DE OFERTA IMPERDÍVEL ---
def processar_e_enviar(oferta):
    if not oferta or not oferta.get('foto'):
        logging.warning("⚠️ Oferta descartada por não possuir imagem real.")
        return False

    chave_produto = oferta.get('link', '').split('?')[0] or oferta.get('titulo', '')
    eh_menor_historico = registrar_e_verificar_menor_preco(chave_produto, oferta.get('preco_atual', 0), oferta.get('preco_original'))
    selo_historico = "🚨 *MENOR PREÇO HISTÓRICO! OFERTA IMPERDÍVEL!*\n\n" if eh_menor_historico else ""

    frete_texto = "📦 *FRETE GRÁTIS!* 🚚\n" if oferta.get('frete_gratis') else ""
    parcelas_texto = f"{oferta['parcelamento']}\n" if oferta.get('parcelamento') else ""
    vendas_texto = oferta.get('vendas', '')
    
    copy_ia = gerar_copy_ia(oferta['titulo'], oferta['preco_atual'], oferta['origem'])
    copy_texto = f"✨ _{copy_ia}_\n\n" if copy_ia else ""

    comparacao = comparar_preco_outra_loja(oferta['titulo'], oferta['preco_atual'], oferta['origem'])
    comparacao_texto = f"{comparacao}\n\n" if comparacao else ""

    verificar_radar_desejos(oferta)

    desconto = oferta.get('desconto', 0)
    preco_orig = oferta.get('preco_original')

    preco_orig_texto = f"❌ De: R$ {preco_orig:.2f}\n" if (preco_orig and preco_orig > oferta['preco_atual']) else ""

    gatilhos_urgencia = [
        "⚡ OFERTA IMPERDÍVEL 24H - RESTAM POUCAS UNIDADES!",
        "⏳ ALTA PROCURA! GARANTA SUA OFERTA IMPERDÍVEL AGORA!",
        "🔥 PRODUTO CAMPEÃO! ESTOQUE BAIXANDO RÁPIDO!",
        "🚨 OFERTA IMPERDÍVEL! GARANTA O SEU ANTES QUE ACABE!",
        "⏰ GRUPO ATIVO 24H - CORRA PARA APROVEITAR!"
    ]
    urgencia_texto = f"⚠️ *{random.choice(gatilhos_urgencia)}*\n"

    if "BUG" in oferta['origem'] or desconto >= 35:
        mensagem = (
            "🚨 *OFERTA IMPERDÍVEL / BUG DE PREÇO 24H!* 🚨\n\n"
            f"{selo_historico}"
            f"{vendas_texto}"
            f"{copy_texto}"
            f"📦 *{oferta['titulo']}*\n"
            f"{preco_orig_texto}"
            f"🔥 *Por apenas: R$ {oferta['preco_atual']:.2f}* ({desconto}% OFF!)\n"
            f"{parcelas_texto}"
            f"{frete_texto}"
            f"{comparacao_texto}"
            f"{urgencia_texto}"
            "⚡️ *CORRA! Oferta imperdível no ar!*"
        )
        texto_botao = f"🔥 PEGAR OFERTA IMPERDÍVEL NA {oferta['origem'].upper()} ({desconto}% OFF)"
    elif "fadadoscupons" in oferta['origem'].lower():
        preco_formatado = f"💰 *Preço:* R$ {oferta['preco_atual']:.2f}\n" if oferta['preco_atual'] > 0 else ""
        mensagem = (
            "🧚‍♀️ *OFERTA IMPERDÍVEL DA FADA DOS CUPONS 24H!* 🧚‍♀️\n\n"
            f"{selo_historico}"
            f"{vendas_texto}"
            f"📦 *{oferta['titulo']}*\n"
            f"{preco_formatado}"
            f"{parcelas_texto}"
            f"{frete_texto}"
            f"{urgencia_texto}"
            "⚡️ *Aproveite antes que a oferta imperdível acabe!*"
        )
        texto_botao = "🛒 VER OFERTA IMPERDÍVEL DA FADA"
    else:
        preco_texto = f"💰 *Preço:* R$ {oferta['preco_atual']:.2f}"
        if preco_orig_texto:
            preco_texto = f"{preco_orig_texto}💰 *Por apenas:* R$ {oferta['preco_atual']:.2f}"
        
        mensagem = (
            f"🔥 *OFERTA IMPERDÍVEL 24H ({oferta['origem'].upper()})!* 🔥\n\n"
            f"{selo_historico}"
            f"{vendas_texto}"
            f"{copy_texto}"
            f"📦 *{oferta['titulo']}*\n"
            f"{preco_texto}\n"
            f"{parcelas_texto}"
            f"{frete_texto}"
            f"{comparacao_texto}"
            f"{urgencia_texto}"
            "⚡️ *Clique no botão abaixo para garantir esta oferta imperdível!*"
        )
        texto_botao = f"🛒 PEGAR OFERTA IMPERDÍVEL NA {oferta['origem'].upper()}"

    return enviar_telegram_com_botao(
        foto_url=oferta.get('foto'),
        mensagem=mensagem,
        texto_botao=texto_botao,
        url_botao=oferta['link']
    )

# --- FUNÇÃO PRINCIPAL DE DISPARO DE OFERTA IMPERDÍVEL ---
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
                res_data = resp.json()
                updates = res_data.get("result", []) if isinstance(res_data, dict) else []
                for u in updates:
                    offset = u.get("update_id", 0) + 1
                    msg = u.get("message") or u.get("edited_message") or {}
                    text = msg.get("text") or ""
                    photos = msg.get("photo") or []
                    from_user = msg.get("from") or {}
                    user_id = from_user.get("id")
                    chat_id = (msg.get("chat") or {}).get("id") or user_id

                    new_members = msg.get("new_chat_members") or []
                    if new_members:
                        for member in new_members:
                            nome_membro = member.get("first_name", "Usuário")
                            if member.get("last_name"):
                                nome_membro += f" {member.get('last_name')}"
                            nome_membro = limpar_markdown(nome_membro)
                            
                            msg_boas_vindas_grupo = (
                                f"👋 *Seja muito bem-vindo(a), {nome_membro}!* 🎉\n\n"
                                f"🔥 Nosso grupo fica LIGADO 24 HORAS por dia enviando OFERTAS IMPERDÍVEIS em Ferramentas, Celulares, Fones de Ouvido e Cupons em tempo real!"
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

                    if photos:
                        try:
                            requests.post(
                                f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage",
                                json={"chat_id": chat_id, "text": "📸 *Imagem recebida!* Analisando a oferta imperdível com IA Gemini...", "parse_mode": "Markdown"}
                            )

                            file_id = photos[-1].get("file_id")
                            res_file = requests.get(f"https://api.telegram.org/bot{TOKEN_BOT}/getFile?file_id={file_id}", timeout=10)
                            
                            if res_file.status_code == 200:
                                file_path = res_file.json().get("result", {}).get("file_path")
                                img_url = f"https://api.telegram.org/file/bot{TOKEN_BOT}/{file_path}"
                                img_resp = requests.get(img_url, timeout=15)

                                if img_resp.status_code == 200:
                                    nome_identificado = identificar_produto_por_imagem(img_resp.content)
                                    if nome_identificado:
                                        msg_ident = (
                                            f"🤖 *Produto Identificado pela IA:* {nome_identificado}\n\n"
                                            "🔎 Buscando a oferta imperdível pelo menor preço..."
                                        )
                                        requests.post(
                                            f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage",
                                            json={"chat_id": chat_id, "text": msg_ident, "parse_mode": "Markdown"}
                                        )

                                        buscadores_ocr = [
                                            ("Mercado Livre", buscar_oferta_mercadolivre),
                                            ("Shopee", buscar_oferta_shopee),
                                            ("Amazon", buscar_oferta_amazon)
                                        ]

                                        resultados_ocr = []
                                        for nome_loja, fn_busca in buscadores_ocr:
                                            try:
                                                of = fn_busca(nome_identificado)
                                                if of and of.get("preco_atual", 0) > 0:
                                                    resultados_ocr.append(of)
                                            except Exception as e_bocr:
                                                logging.error(f"Erro ao buscar em OCR para {nome_loja}: {e_bocr}")

                                        if resultados_ocr:
                                            resultados_ocr.sort(key=lambda x: x["preco_atual"])
                                            melhor_of = resultados_ocr[0]

                                            desc_str = f" ({melhor_of['desconto']}% OFF)" if melhor_of.get('desconto') else ""
                                            frete_str = "📦 Frete Grátis!" if melhor_of.get('frete_gratis') else ""

                                            msg_resultado = (
                                                f"🏆 *OFERTA IMPERDÍVEL ENCONTRADA PARA:* {nome_identificado}\n\n"
                                                f"📦 *Produto:* {melhor_of['titulo']}\n"
                                                f"🏪 *Loja:* {melhor_of['origem']}\n"
                                                f"💰 *Preço:* R$ {melhor_of['preco_atual']:.2f}{desc_str}\n"
                                                f"{frete_str}\n\n"
                                                f"👉 [Clique para comprar esta oferta imperdível!]({melhor_of['link']})"
                                            )
                                            requests.post(
                                                f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage",
                                                json={"chat_id": chat_id, "text": msg_resultado, "parse_mode": "Markdown", "disable_web_page_preview": False}
                                            )
                                        else:
                                            requests.post(
                                                f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage",
                                                json={"chat_id": chat_id, "text": f"❌ Não encontramos ofertas imperdíveis para *{nome_identificado}* no momento.", "parse_mode": "Markdown"}
                                            )
                                    else:
                                        requests.post(
                                            f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage",
                                            json={"chat_id": chat_id, "text": "⚠️ Não foi possível identificar o produto na imagem.", "parse_mode": "Markdown"}
                                        )
                        except Exception as e_ocr:
                            logging.error(f"Erro no processamento OCR de imagem: {e_ocr}")
                        continue

                    if text.startswith("/start"):
                        nome_usuario = limpar_markdown(from_user.get("first_name", "Usuário"))
                        boas_vindas = (
                            f"👋 *Olá, {nome_usuario}! O Grupo fica ligado 24 HORAS enviando Ofertas Imperdíveis!* 🎉\n\n"
                            "📸 *Leitor de Imagem por IA:* Envie uma foto e achamos a melhor oferta imperdível!\n"
                            "• `/cupom <loja>` para buscar cupons.\n"
                            "• `/desejo produto, preco` para radar de ofertas 24h.\n"
                            "• `/oferta` para disparar uma oferta imperdível agora.\n"
                            "• `/intervalo <minutos>` para ajustar a frequência."
                        )
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": boas_vindas, "parse_mode": "Markdown"})

                    elif text.startswith("/cupom") or text.startswith("/cupons"):
                        partes = text.split(maxsplit=1)
                        termo = partes[1].strip() if len(partes) > 1 else None
                        cupom = buscar_cupons_confiaveis(termo)
                        
                        msg_cupom = (
                            f"🎟️ *CUPOM IMPERDÍVEL 24H* 🎟️\n\n"
                            f"🏪 *Loja:* {cupom['loja']}\n"
                            f"🏷️ *Cupom / Oferta:* `{cupom['cupom']}`\n"
                            f"💰 *Desconto:* {cupom['desconto']}\n"
                            f"ℹ️ *Detalhes:* {cupom['descricao']}\n\n"
                            f"👉 [Clique para Resgatar Oferta Imperdível]({cupom['link']})"
                        )
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": msg_cupom, "parse_mode": "Markdown", "disable_web_page_preview": False})

                    elif text.startswith("/fada"):
                        monitorar_fada_dos_cupons()

                    elif text.startswith("/oferta") or text.startswith("/status") or text.startswith("/ping"):
                        enviar_oferta_telegram()
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": "📦 *Oferta imperdível enviada para o canal!*", "parse_mode": "Markdown"})

                    elif text.startswith("/bug") or text.startswith("/bugs"):
                        oferta_bug = buscar_bug_preco()
                        if oferta_bug:
                            processar_e_enviar(oferta_bug)
                            resp_text = "🚨 *Oferta imperdível / Bug de preço enviado para o canal!*"
                        else:
                            resp_text = "⚠️ Buscando ofertas imperdíveis no radar automático!"
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": resp_text, "parse_mode": "Markdown"})

                    elif text.startswith("/intervalo") or text.startswith("/tempo"):
                        try:
                            partes = text.split()
                            minutos = float(partes[1].strip())
                            if minutos <= 0:
                                raise ValueError
                            INTERVALO_POSTAGEM = int(minutos * 60)
                            resp_text = f"⏱️ *Intervalo alterado com sucesso!*\nO grupo enviará ofertas imperdíveis a cada *{minutos} minuto(s)* 24 horas por dia."
                        except Exception:
                            resp_text = "❌ Formato inválido! Use: `/intervalo 1`"
                        
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": resp_text, "parse_mode": "Markdown"})

                    elif text.startswith("/desejo"):
                        try:
                            conteudo = text.replace("/desejo", "").strip()
                            partes = conteudo.split(",")
                            termo = partes[0].strip()
                            preco_max = float(partes[1].strip())
                            
                            RADAR_DESEJOS.append({"user_id": user_id, "termo": termo, "preco_max": preco_max})
                            
                            resp_text = f"✅ *Alerta 24h Registrado!* Te avisarei assim que surgir oferta imperdível de *{limpar_markdown(termo)}* por até R$ {preco_max:.2f}!"
                        except Exception:
                            resp_text = "❌ Use: `/desejo produto, preco`"
                        
                        requests.post(f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage", json={"chat_id": user_id, "text": resp_text, "parse_mode": "Markdown"})
        except Exception as e:
            logging.error(f"Erro na escuta de comandos: {e}")
        time.sleep(3)

# --- LOOP AUTOMÁTICO DE MONITORAMENTO DE @fadadoscupons 24H ---
def rodar_loop_fada_dos_cupons():
    logging.info("🧚‍♀️ Loop de monitoramento de @fadadoscupons ativo 24h!")
    while True:
        try:
            monitorar_fada_dos_cupons()
        except Exception as e:
            logging.error(f"Erro no loop Fada dos Cupons: {e}")
        time.sleep(120)

# --- LOOP AUTOMÁTICO 24 HORAS ENVIANDO OFERTAS IMPERDÍVEIS ---
def rodar_loop_ofertas():
    logging.info("🚀 Grupo 24 HORAS LIGADO enviando ofertas imperdíveis sem parar!")
    while True:
        try:
            enviar_oferta_telegram()
        except Exception as e:
            logging.error(f"Erro no loop de ofertas imperdíveis 24h: {e}")
        time.sleep(INTERVALO_POSTAGEM)

if __name__ == '__main__':
    # Mantém o servidor HTTP online 24h
    keep_alive()
    
    # Thread para auto ping mantendo 24 horas ligado em qualquer host
    t_ping = Thread(target=auto_ping, daemon=True)
    t_ping.start()

    # Thread do Loop Automático de Ofertas Imperdíveis 24h
    t_ofertas = Thread(target=rodar_loop_ofertas, daemon=True)
    t_ofertas.start()

    # Thread do Monitor da Fada dos Cupons
    t_fada = Thread(target=rodar_loop_fada_dos_cupons, daemon=True)
    t_fada.start()

    # Thread do Radar / Comandos
    t_cmd = Thread(target=escutar_comandos_telegram, daemon=True)
    t_cmd.start()
    
    # Mantém a thread principal viva para garantir operação 24/7
    while True:
        time.sleep(60)