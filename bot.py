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

        # 🔥 BASE REAL (AFILIADO / PRODUTOS FIXOS MONETIZÁVEIS)
        produtos = [
            {
                "titulo": "Echo Dot 5ª Geração Alexa (OFERTA REAL)",
                "preco": "R$ 299",
                "link": "https://www.amazon.com.br/dp/B09B8YWXDF?tag=SEU_AFFILIATE_ID",
                "imagem": None
            },
            {
                "titulo": "Fire TV Stick HD (OFERTA REAL)",
                "preco": "R$ 249",
                "link": "https://www.amazon.com.br/dp/B0BJM7K3W3?tag=SEU_AFFILIATE_ID",
                "imagem": None
            },
            {
                "titulo": "Kindle 11ª Geração (OFERTA REAL)",
                "preco": "R$ 399",
                "link": "https://www.amazon.com.br/dp/B09SWW583J?tag=SEU_AFFILIATE_ID",
                "imagem": None
            }
        ]

    except Exception as e:
        print("ERRO PRODUTOS:", repr(e), flush=True)

    return produtos

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