import threading
import asyncio
import time
import os
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

TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = -1001234567890

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

# ================= RATE LIMIT =================

async def rate_limit():
    await asyncio.sleep(random.uniform(8, 16))

# ================= SCRAPING =================

def link_valido(link):
    return link and link.startswith("http") and "promobit" in link

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
            tag_img = item.find("img")
            if tag_img:
                img = tag_img.get("data-src") or tag_img.get("src")

            ofertas.append({
                "titulo": titulo,
                "link": link + AFILIADO,
                "preco": preco,
                "imagem": img
            })

        except:
            continue

    return ofertas

# ================= DOWNLOAD IMAGEM (CORREÇÃO FINAL) =================

def baixar_imagem(url):
    try:
        if not url:
            return None

        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(url, headers=headers, timeout=10, stream=True)

        if r.status_code != 200:
            return None

        content_type = r.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return None

        return r.content

    except:
        return None

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

                img_bytes = baixar_imagem(o["imagem"])

                try:
                    if img_bytes:
                        await bot.send_photo(
                            chat_id=CHAT_ID,
                            photo=img_bytes,
                            caption=msg[:1020],
                            reply_markup=keyboard
                        )
                    else:
                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=msg + f"\n\n🛒 {o['link']}",
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