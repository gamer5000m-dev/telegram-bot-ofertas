import os
import re
import time
import asyncio
import sqlite3
import threading
import random
import requests

from flask import Flask
from bs4 import BeautifulSoup

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

# =========================================
# FLASK
# =========================================

app = Flask(__name__)

@app.route("/")
def home():
    return "BOT ONLINE"

def run_web():

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )

# =========================================
# CONFIG
# =========================================

TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

TEMPO_LOOP = 300
MAX_POSTS = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),

    "Accept-Language": "pt-BR,pt;q=0.9",

    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),

    "Connection": "keep-alive"
}

FONTES = [

    {
        "nome": "Amazon",
        "url": "https://www.amazon.com.br/gp/goldbox",
        "dominio": "amazon"
    },

    {
        "nome": "Mercado Livre",
        "url": "https://lista.mercadolivre.com.br/ofertas",
        "dominio": "mercadolivre"
    },

    {
        "nome": "Shopee",
        "url": "https://shopee.com.br/ofertas",
        "dominio": "shopee"
    }

]

KEYWORDS_BLOQUEADAS = [
    "grupo",
    "telegram",
    "whatsapp",
    "cupom",
    "frete grátis",
    "comentários",
    "login",
    "entrar",
    "categorias"
]

# =========================================
# TELEGRAM
# =========================================

telegram_app = Application.builder().token(TOKEN).build()

# =========================================
# DATABASE
# =========================================

conn = sqlite3.connect(
    "ofertas.db",
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS enviados (
    link TEXT PRIMARY KEY
)
""")

conn.commit()

def ja_enviado(link):

    cursor.execute(
        "SELECT 1 FROM enviados WHERE link=?",
        (link,)
    )

    return cursor.fetchone()

def salvar(link):

    cursor.execute(
        "INSERT OR IGNORE INTO enviados(link) VALUES(?)",
        (link,)
    )

    conn.commit()

# =========================================
# VALIDAR IMAGEM
# =========================================

def imagem_valida(url):

    try:

        if not url:
            return False

        if ".svg" in url:
            return False

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=10,
            stream=True
        )

        if r.status_code != 200:
            return False

        content = r.headers.get(
            "Content-Type",
            ""
        )

        if "image" not in content:
            return False

        return True

    except:
        return False

# =========================================
# PEGAR PRODUTOS
# =========================================

def pegar_produtos():

    produtos = []

    lojas = [

        {
            "url": "https://www.amazon.com.br/gp/goldbox",
            "base": "https://www.amazon.com.br"
        },

        {
            "url": "https://lista.mercadolivre.com.br/ofertas",
            "base": "https://www.mercadolivre.com.br"
        },

        {
            "url": "https://shopee.com.br/ofertas",
            "base": "https://shopee.com.br"
        }

    ]

    for loja in lojas:

        try:

            r = requests.get(
                loja["url"],
                headers=HEADERS,
                timeout=20
            )

            soup = BeautifulSoup(
                r.text,
                "html.parser"
            )

            links = soup.find_all("a")

            for a in links:

                href = a.get("href")

                if not href:
                    continue

                titulo = a.get_text(strip=True)

                if len(titulo) < 15:
                    continue

                # AMAZON
                if "amazon" in loja["base"]:

                    if "/dp/" not in href:
                        continue

                # MERCADO LIVRE
                elif "mercadolivre" in loja["base"]:

                    if "MLB" not in href:
                        continue

                # SHOPEE
                elif "shopee" in loja["base"]:

                    if "/product/" not in href and "-i." not in href:
                        continue

                # LINK COMPLETO
                if href.startswith("/"):

                    link = loja["base"] + href

                else:

                    link = href

                # REMOVE TRACKING
                link = link.split("?")[0]

                produtos.append({

                    "titulo": titulo[:120],
                    "preco": "OFERTA",
                    "link": link,
                    "imagem": None

                })

                if len(produtos) >= 30:
                    break

        except Exception as e:

            print(
                "ERRO LOJA:",
                repr(e),
                flush=True
            )

    # REMOVE DUPLICADOS
    vistos = set()
    filtrados = []

    for p in produtos:

        if p["link"] in vistos:
            continue

        vistos.add(p["link"])
        filtrados.append(p)

    random.shuffle(filtrados)

    return filtrados

# =========================================
# ENVIAR TELEGRAM
# =========================================

async def enviar_produto(produto):

    titulo = produto["titulo"]
    preco = produto["preco"]
    desconto = produto.get("desconto", "Oferta")
    link = produto["link"]
    imagem = produto["imagem"]

    texto = f"""
🔥 OFERTA ENCONTRADA

📦 {titulo}

💰 {preco}

⚡ Promoção por tempo limitado
"""

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛒 COMPRAR AGORA",
                url=link
            )
        ]
    ])

    try:

        # COM IMAGEM
        if imagem:

            await telegram_app.bot.send_photo(
                chat_id=CHAT_ID,
                photo=imagem,
                caption=texto,
                reply_markup=keyboard
            )

        # SEM IMAGEM
        else:

            await telegram_app.bot.send_message(
                chat_id=CHAT_ID,
                text=texto,
                reply_markup=keyboard
            )

        print(
            "ENVIADO:",
            titulo,
            flush=True
        )

        salvar(link)

    except Exception as e:

        print(
            "ERRO ENVIO:",
            repr(e),
            flush=True
        )

# =========================================
# LOOP PRINCIPAL
# =========================================

async def bot_loop():

    print(
        "BOT INICIADO",
        flush=True
    )

    while True:

        try:

            produtos = pegar_produtos()

            random.shuffle(produtos)

            print(
                "PRODUTOS:",
                len(produtos),
                flush=True
            )

            enviados = 0

            for produto in produtos:

                if enviados >= MAX_POSTS:
                    break

                if ja_enviado(produto["link"]):
                    continue

                await enviar_produto(produto)

                enviados += 1

                # ANTI BAN TELEGRAM
                espera = random.randint(40, 90)

                print(
                    f"ANTI-SPAM: {espera}s",
                    flush=True
                )

                await asyncio.sleep(espera)

            print(
                "AGUARDANDO NOVO CICLO...",
                flush=True
            )

            await asyncio.sleep(TEMPO_LOOP)

        except Exception as e:

            print(
                "ERRO LOOP:",
                repr(e),
                flush=True
            )

            await asyncio.sleep(60)

# =========================================
# START
# =========================================

async def main():

    print(
        "BOT INICIADO",
        flush=True
    )

    # inicia flask
    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    # inicia telegram
    await telegram_app.initialize()
    await telegram_app.start()

    # loop principal
    await bot_loop()

if __name__ == "__main__":

    print(
        "INICIANDO SISTEMA...",
        flush=True
    )

    try:
        asyncio.run(main())

    except Exception as e:

        print(
            "ERRO FATAL:",
            repr(e),
            flush=True
        )

        while True:
            time.sleep(60)