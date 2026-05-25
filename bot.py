import os
import time
import asyncio
import sqlite3
import threading
import random
import requests

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
# PRODUTOS (MERCADO LIVRE REAL)
# =========================================

def pegar_produtos():

    produtos = []

    try:

        url = "https://api.mercadolibre.com/sites/MLB/search?q=oferta&limit=20"

        r = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
        )

        print("STATUS API:", r.status_code, flush=True)

        # 🔥 VERIFICA SE RESPONDEU JSON REAL
        try:
            data = r.json()
        except Exception:
            print("ERRO: resposta não é JSON", flush=True)
            return []

        if "results" not in data:
            print("ERRO: API sem results", flush=True)
            return []

        for item in data["results"]:

            price = item.get("price", 0)

            if not price or price < 50:
                continue

            produtos.append({

                "titulo": item.get("title", "Produto"),
                "preco": f"R$ {price}",
                "link": item.get("permalink", ""),
                "imagem": item.get("thumbnail", "")

            })

    except Exception as e:
        print("ERRO API ML:", repr(e), flush=True)

    print("DEBUG PRODUTOS BRUTOS:", len(produtos), flush=True)

    random.shuffle(produtos)

    return produtos[:10]

# =========================================
# ENVIO TELEGRAM
# =========================================

async def enviar_produto(produto):

    try:

        titulo = produto["titulo"]
        preco = produto["preco"]
        link = produto["link"]
        imagem = produto.get("imagem")

        texto = f"""
🔥 OFERTA ENCONTRADA

📦 {titulo}

💰 {preco}

⚡ Promoção limitada
"""

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 VER OFERTA", url=link)]
        ])

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

                if ja_enviado(produto.get("link")):
                    continue

                await enviar_produto(produto)

                enviados += 1

                await asyncio.sleep(random.randint(40, 90))

        except Exception as e:
            print("ERRO LOOP:", repr(e), flush=True)
            await asyncio.sleep(10)

        print("AGUARDANDO CICLO...", flush=True)
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