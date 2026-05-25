import os
import time
import asyncio
import sqlite3
import threading
import random

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
# PRODUTOS (FIXOS ESTÁVEIS)
# =========================================

def pegar_produtos():

    produtos = [

        {
            "titulo": "Echo Dot 5ª Geração Alexa",
            "preco": "R$ 299",
            "link": "https://www.amazon.com.br/dp/B09B8YWXDF"
        },

        {
            "titulo": "Fire TV Stick HD",
            "preco": "R$ 249",
            "link": "https://www.amazon.com.br/dp/B0BJM7K3W3"
        },

        {
            "titulo": "Kindle 11ª Geração",
            "preco": "R$ 399",
            "link": "https://www.amazon.com.br/dp/B09SWW583J"
        }

    ]

    random.shuffle(produtos)
    return produtos

# =========================================
# ENVIAR TELEGRAM
# =========================================

async def enviar_produto(produto):

    titulo = produto["titulo"]
    preco = produto["preco"]
    link = produto["link"]

    texto = f"""
🔥 OFERTA ENCONTRADA

📦 {titulo}

💰 {preco}
"""

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛒 COMPRAR AGORA", url=link)
        ]
    ])

    try:
        await telegram_app.bot.send_message(
            chat_id=CHAT_ID,
            text=texto,
            reply_markup=keyboard
        )

        print("ENVIADO:", titulo, flush=True)

        salvar(link)

    except Exception as e:
        print("ERRO ENVIO:", repr(e), flush=True)

# =========================================
# LOOP PRINCIPAL
# =========================================

async def bot_loop():

    print("BOT INICIADO", flush=True)

    while True:

        try:

            produtos = pegar_produtos()

            print("PRODUTOS:", len(produtos), flush=True)

            enviados = 0

            for produto in produtos:

                if enviados >= MAX_POSTS:
                    break

                if ja_enviado(produto["link"]):
                    continue

                await enviar_produto(produto)

                enviados += 1

                espera = random.randint(40, 90)

                print(f"ANTI-SPAM: {espera}s", flush=True)

                await asyncio.sleep(espera)

            print("AGUARDANDO NOVO CICLO...", flush=True)

            await asyncio.sleep(TEMPO_LOOP)

        except Exception as e:
            print("ERRO LOOP:", repr(e), flush=True)
            await asyncio.sleep(60)

# =========================================
# START
# =========================================

async def main():

    print("INICIANDO SISTEMA...", flush=True)

    threading.Thread(target=run_web, daemon=True).start()

    await telegram_app.initialize()
    await telegram_app.start()

    await bot_loop()

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except Exception as e:
        print("ERRO FATAL:", repr(e), flush=True)

        while True:
            time.sleep(60)