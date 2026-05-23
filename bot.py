import threading
import time
import os
import asyncio
import requests
import re
import sqlite3
import random

from flask import Flask
from bs4 import BeautifulSoup

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Bot

# ================= FLASK =================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot rodando OK"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ================= CONFIG =================

TOKEN = "8391542912:AAH1cduJ0E7naPhA0z6uezCgkbLn1BjyQDE"
CHAT_ID = -1003914285353

URL = "https://www.promobit.com.br"
TEMPO = 300
LIMITE = 3
AFILIADO = "?utm_source=telegram"

FALLBACK_IMAGE = "https://via.placeholder.com/600x400.png"

bot = Bot(token=TOKEN)

# ================= BANCO =================

conn = sqlite3.connect("ofertas.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS ofertas (
    link TEXT PRIMARY KEY
)
""")
conn.commit()

def ja_enviado(link):
    cursor.execute("SELECT 1 FROM ofertas WHERE link=?", (link,))
    return cursor.fetchone()

def salvar(link):
    cursor.execute("INSERT OR IGNORE INTO ofertas(link) VALUES(?)", (link,))
    conn.commit()

# ================= RATE LIMIT ANTI-BAN =================

async def rate_limit():
    await asyncio.sleep(random.uniform(8, 18))

# ================= VALIDAÇÃO DE IMAGEM =================

def imagem_valida(url):
    try:
        if not url:
            return False

        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)

        if r.status_code != 200:
            return False

        content_type = r.headers.get("Content-Type", "")
        return content_type.startswith("image/")

    except:
        return False

# ================= LINK =================

def link_valido(link):
    return link and link.startswith("http") and "promobit" in link

# ================= SCRAPING =================

def pegar_ofertas():
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(URL, headers=headers, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")

    ofertas = []

    for item in soup.find_all("a"):
        try:
            titulo = item.get_text(strip=True)
            link = item.get("href")

            if not titulo or not link:
                continue

            if len(titulo) < 20:
                continue

            if link.startswith("/"):
                link = URL + link

            if not link_valido(link):
                continue

            preco = "Preço não encontrado"
            p = re.findall(r"R\$\s?\d+[.,]?\d*", titulo)
            if p:
                preco = p[0]

            img = None
            image_tag = item.find("img")
            if image_tag:
                img = image_tag.get("data-src") or image_tag.get("src")

            ofertas.append({
                "titulo": titulo,
                "link": link + AFILIADO,
                "preco": preco,
                "imagem": img
            })

        except:
            continue

    return ofertas

# ================= BOT LOOP =================

async def bot_loop():

    print("BOT INICIADO", flush=True)

    while True:
        try:
            ofertas = pegar_ofertas()
            print("OFERTAS:", len(ofertas), flush=True)

            enviados = 0

            for o in ofertas:

                if enviados >= LIMITE:
                    break

                if ja_enviado(o["link"]):
                    continue

                msg = f"""🔥 OFERTA NOVA

📦 {o['titulo']}

💰 {o['preco']}
"""

                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Comprar", url=o["link"])
                ]])

                img = o["imagem"]

                # valida imagem real
                if not imagem_valida(img):
                    img = FALLBACK_IMAGE

                try:
                    await bot.send_photo(
                        chat_id=CHAT_ID,
                        photo=img,
                        caption=msg[:1020],
                        reply_markup=keyboard
                    )

                    salvar(o["link"])
                    enviados += 1

                    print("ENVIADO:", o["titulo"], flush=True)

                except Exception as e:
                    print("ERRO ENVIO:", repr(e), flush=True)

                await rate_limit()

            print("AGUARDANDO...", flush=True)
            await asyncio.sleep(TEMPO)

        except Exception as e:
            print("ERRO BOT:", repr(e), flush=True)
            await asyncio.sleep(30)

# ================= START =================

async def main():
    threading.Thread(target=run_web, daemon=True).start()
    await bot_loop()

if __name__ == "__main__":
    print("INICIANDO SISTEMA...", flush=True)
    asyncio.run(main())