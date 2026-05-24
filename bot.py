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
ADMIN_KEY = os.getenv("ADMIN_KEY")

TEMPO_LOOP = 300
MAX_POSTS = 5

FONTES = [
    "https://www.promobit.com.br/",
    "https://www.pelando.com.br/"
]

AFILIADO = "?utm_source=telegram"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13)"
        " AppleWebKit/537.36"
        " Chrome/120 Safari/537.36"
    )
}

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

    for url in FONTES:

        try:

            r = requests.get(
                url,
                headers=HEADERS,
                timeout=30
            )

            soup = BeautifulSoup(
                r.text,
                "html.parser"
            )

            links = soup.find_all("a")

            for item in links:

                try:

                    titulo = item.get_text(
                        " ",
                        strip=True
                    )

                    if not titulo:
                        continue

                    if len(titulo) < 25:
                        continue

                    link = item.get("href")

                    if not link:
                        continue

                    if link.startswith("/"):

                        if "promobit" in url:
                            link = (
                                "https://www.promobit.com.br"
                                + link
                            )

                        elif "pelando" in url:
                            link = (
                                "https://www.pelando.com.br"
                                + link
                            )

                    if "http" not in link:
                        continue

                    preco = "🔥 Oferta"

                    m = re.search(
                        r"R\$\s?[\d\.,]+",
                        titulo
                    )

                    if m:
                        preco = m.group(0)

                    img = item.find("img")

                    imagem = None

                    if img:

                        imagem = (
                            img.get("src")
                            or img.get("data-src")
                            or img.get("data-lazy-src")
                        )

                    produtos.append({
                        "titulo": titulo[:180],
                        "preco": preco,
                        "link": link + AFILIADO,
                        "imagem": imagem
                    })

                except:
                    pass

        except:
            pass

    return produtos

# =========================================
# ENVIAR TELEGRAM
# =========================================

async def enviar_produto(produto):

    titulo = produto["titulo"]
    preco = produto["preco"]
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

        # tenta enviar imagem real
        if imagem and imagem_valida(imagem):

            await telegram_app.bot.send_photo(
                chat_id=CHAT_ID,
                photo=imagem,
                caption=texto,
                reply_markup=keyboard
            )

        else:

            # fallback sem imagem
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

            print(
                "PRODUTOS:",
                len(produtos),
                flush=True
            )

            enviados = 0

            random.shuffle(produtos)

            for produto in produtos:

                if enviados >= MAX_POSTS:
                    break

                if ja_enviado(produto["link"]):
                    continue

                await enviar_produto(produto)

                enviados += 1

                # anti-ban inteligente
                espera = random.randint(20, 45)

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

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    await bot_loop()

if __name__ == "__main__":

    print(
        "INICIANDO SISTEMA...",
        flush=True
    )

    asyncio.run(main())