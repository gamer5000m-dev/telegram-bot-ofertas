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

    produtos = []

    try:

        url = "https://api.mercadolibre.com/sites/MLB/search?q=ofertas&limit=10"

        r = requests.get(url, timeout=20)

        data = r.json()

        for item in data.get("results", []):

            produtos.append({

                "titulo": item.get("title"),
                "preco": f"R$ {item.get('price')}",
                "link": item.get("permalink"),
                "imagem": item.get("thumbnail")

            })

    except Exception as e:

        print("ERRO API ML:", repr(e), flush=True)

    random.shuffle(produtos)

    return produtos

# =========================================
# ENVIAR TELEGRAM
# =========================================

async def enviar_produto(produto):

    titulo = produto["titulo"]
    preco = produto["preco"]
    link = produto["link"]
    imagem = produto.get("imagem")

    texto = f"""
🔥 OFERTA ENCONTRADA

📦 {titulo}

💰 {preco}
"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 COMPRAR AGORA", url=link)]
    ])

    try:

        if imagem:
            await telegram_app.bot.send_photo(
                chat_id=CHAT_ID,
                photo=imagem,
                caption=texto,
                reply_markup=keyboard
            )
        else:
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

    await telegram_app.bot.initialize()

    print("BOT INICIADO", flush=True)

    await bot_loop()