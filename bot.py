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

# =========================
# WEB SERVER (Render)
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "BOT EMPRESA ONLINE"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

TEMPO_LOOP = 300
MAX_POSTS = 3

telegram_app = Application.builder().token(TOKEN).build()

# =========================
# BANCO
# =========================

conn = sqlite3.connect("enterprise.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS sent (
    link TEXT PRIMARY KEY
)
""")
conn.commit()

def already_sent(link):
    cursor.execute("SELECT 1 FROM sent WHERE link=?", (link,))
    return cursor.fetchone()

def save(link):
    cursor.execute("INSERT OR IGNORE INTO sent(link) VALUES(?)", (link,))
    conn.commit()

# =========================
# 🔥 MULTI-FONTES REAIS
# =========================

def fetch_mercadolivre():

    items = []

    try:

        queries = ["oferta", "desconto", "promoção", "fone", "celular"]

        for q in queries:

            url = f"https://api.mercadolibre.com/sites/MLB/search?q={q}&limit=10"

            r = requests.get(url, timeout=20)
            data = r.json()

            for item in data.get("results", []):

                price = item.get("price", 0)

                if not price:
                    continue

                items.append({
                    "titulo": item.get("title"),
                    "preco": f"R$ {price}",
                    "link": item.get("permalink"),
                    "imagem": item.get("thumbnail"),
                    "fonte": "Mercado Livre"
                })

    except Exception as e:
        print("ML ERROR:", repr(e), flush=True)

    return items


def fetch_rss():

    items = []

    feeds = [
        "https://www.magazineluiza.com.br/rss/ofertas",
        "https://www.americanas.com.br/rss/ofertas"
    ]

    for feed in feeds:

        try:
            r = requests.get(feed, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            soup = None

            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "xml")

            for item in soup.find_all("item"):

                items.append({
                    "titulo": item.title.text if item.title else "Oferta",
                    "preco": "OFERTA",
                    "link": item.link.text if item.link else "",
                    "imagem": None,
                    "fonte": "RSS"
                })

        except:
            continue

    return items

# =========================
# AGREGADOR INTELIGENTE
# =========================

def get_products():

    products = []

    products += fetch_mercadolivre()
    products += fetch_rss()

    # fallback garantido (NUNCA vazio)
    if not products:

        products = [
            {
                "titulo": "Ofertas do Dia",
                "preco": "OFERTA",
                "link": "https://www.mercadolivre.com.br/ofertas",
                "imagem": None,
                "fonte": "fallback"
            }
        ]

    random.shuffle(products)

    return products[:15]

# =========================
# ENVIO TELEGRAM
# =========================

async def send_product(p):

    try:

        text = f"""
🔥 OFERTA EMPRESA

📦 {p['titulo']}
💰 {p['preco']}
📡 Fonte: {p['fonte']}
"""

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 VER OFERTA", url=p["link"])]
        ])

        await telegram_app.bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            reply_markup=keyboard
        )

        print("ENVIADO:", p["titulo"], flush=True)

        save(p["link"])

    except Exception as e:
        print("SEND ERROR:", repr(e), flush=True)

# =========================
# LOOP EMPRESA
# =========================

async def loop():

    print("BOT EMPRESA ONLINE", flush=True)

    while True:

        try:

            products = get_products()

            print("PRODUTOS:", len(products), flush=True)

            sent = 0

            for p in products:

                if sent >= MAX_POSTS:
                    break

                if already_sent(p["link"]):
                    continue

                await send_product(p)

                sent += 1

                await asyncio.sleep(random.randint(25, 60))

        except Exception as e:
            print("LOOP ERROR:", repr(e), flush=True)
            await asyncio.sleep(10)

        print("NEW CYCLE...", flush=True)
        await asyncio.sleep(TEMPO_LOOP)

# =========================
# START
# =========================

async def main():

    print("INICIANDO SISTEMA EMPRESA...", flush=True)

    threading.Thread(target=run_web, daemon=True).start()

    await telegram_app.initialize()
    await telegram_app.start()

    print("BOT EMPRESA ONLINE", flush=True)

    await loop()

if __name__ == "__main__":
    asyncio.run(main())