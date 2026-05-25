import os
import time
import asyncio
import sqlite3
import threading
import random
import requests
from bs4 import BeautifulSoup

from flask import Flask
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
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# =========================================
# CONFIG
# =========================================

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN:
    raise ValueError("TOKEN não configurado")

if not CHAT_ID:
    raise ValueError("CHAT_ID não configurado")

CHAT_ID = int(CHAT_ID)

TEMPO_LOOP = 300
MAX_POSTS = 3

# =========================================
# TELEGRAM
# =========================================

telegram_app = Application.builder().token(TOKEN).build()

# =========================================
# DATABASE
# =========================================

conn = sqlite3.connect("ofertas.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS enviados (
    link TEXT PRIMARY KEY
)
""")
conn.commit()

def ja_enviado(link):
    cursor.execute("SELECT 1 FROM enviados WHERE link=?", (link,))
    return cursor.fetchone()

def salvar(link):
    cursor.execute("INSERT OR IGNORE INTO enviados(link) VALUES(?)", (link,))
    conn.commit()

# =========================================
# PRODUTOS DEFINITIVO (RSS + FALLBACK)
# =========================================

def pegar_produtos():

    produtos = []

    try:

        feeds = [
            "https://www.magazineluiza.com.br/rss/ofertas",
            "https://www.americanas.com.br/rss/ofertas"
        ]

        for feed in feeds:

            try:

                r = requests.get(
                    feed,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=20
                )

                if r.status_code != 200:
                    continue

                soup = BeautifulSoup(r.text, "xml")

                for item in soup.find_all("item"):

                    titulo = item.title.text if item.title else "Produto"
                    link = item.link.text if item.link else ""

                    produtos.append({

                        "titulo": titulo,
                        "preco": "OFERTA",
                        "link": link,
                        "imagem": None

                    })

            except:
                continue

        # fallback garantido
        if not produtos:

            produtos = [
                {
                    "titulo": "Ofertas Amazon Brasil",
                    "preco": "OFERTA",
                    "link": "https://www.amazon.com.br/gp/goldbox",
                    "imagem": None
                },
                {
                    "titulo": "Ofertas Mercado Livre",
                    "preco": "OFERTA",
                    "link": "https://www.mercadolivre.com.br/ofertas",
                    "imagem": None
                }
            ]

    except Exception as e:
        print("ERRO SISTEMA:", repr(e), flush=True)

    return produtos[:10]

# =========================================
# ENVIO TELEGRAM
# =========================================

async def enviar_produto(produto):

    try:

        texto = f"""
🔥 OFERTA ENCONTRADA

📦 {produto.get('titulo')}

💰 {produto.get('preco')}
"""

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 VER OFERTA", url=produto.get("link"))]
        ])

        await telegram_app.bot.send_message(
            chat_id=CHAT_ID,
            text=texto,
            reply_markup=keyboard
        )

        print("ENVIADO:", produto.get("titulo"), flush=True)

        salvar(produto.get("link"))

    except Exception as e:
        print("ERRO ENVIO:", repr(e), flush=True)
        await asyncio.sleep(3)

# =========================================
# LOOP DEFINITIVO
# =========================================

async def bot_loop():

    print("BOT DEFINITIVO ONLINE", flush=True)

    while True:

        try:

            produtos = pegar_produtos()

            print("PRODUTOS:", len(produtos), flush=True)

            enviados = 0

            for p in produtos:

                if enviados >= MAX_POSTS:
                    break

                if ja_enviado(p.get("link")):
                    continue

                await enviar_produto(p)

                enviados += 1

                await asyncio.sleep(random.randint(30, 80))

        except Exception as e:
            print("ERRO LOOP:", repr(e), flush=True)
            await asyncio.sleep(10)

        print("NOVO CICLO...", flush=True)
        await asyncio.sleep(TEMPO_LOOP)

# =========================================
# START
# =========================================

async def main():

    try:

        print("INICIANDO SISTEMA...", flush=True)

        threading.Thread(target=run_web, daemon=True).start()

        await telegram_app.initialize()
        await telegram_app.start()

        print("BOT ONLINE", flush=True)

        await bot_loop()

    except Exception as e:
        print("ERRO FATAL:", repr(e), flush=True)
        while True:
            time.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())