
import os
import asyncio
import time
import random
import sqlite3
import requests
import re
from io import BytesIO

from flask import Flask
from bs4 import BeautifulSoup

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

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

app_bot = Application.builder().token(TOKEN).build()

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

# ================= ANTI-BAN RATE LIMIT =================

class RateLimiter:
    def __init__(self):
        self.last_send = 0
        self.min_delay = 12  # base segura Telegram

    async def wait(self):
        now = time.time()
        diff = now - self.last_send

        jitter = random.uniform(3, 10)
        wait_time = self.min_delay + jitter - diff

        if wait_time > 0:
            await asyncio.sleep(wait_time)

        self.last_send = time.time()

rate_limiter = RateLimiter()

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

            if "promobit" not in link:
                continue

            preco = "Preço não encontrado"

            p = re.findall(r"R\$\s?\d+[.,]?\d*", titulo)
            if p:
                preco = p[0]

            img = item.find("img")
            imagem = None

            if img:
                imagem = img.get("data-src") or img.get("src")

            ofertas.append({
                "titulo": titulo,
                "link": link + AFILIADO,
                "preco": preco,
                "imagem": imagem
            })

        except:
            continue

    return ofertas

# ================= IMAGEM SEGURA =================

def baixar_imagem(url):
    try:
        if not url:
            return None

        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)

        if not r.headers.get("Content-Type", "").startswith("image/"):
            return None

        if len(r.content) < 1500:
            return None

        return r.content

    except:
        return None

# ================= BOT LOOP =================

async def bot_loop():
    print("BOT INICIADO")

    while True:
        try:
            ofertas = pegar_ofertas()
            print("OFERTAS:", len(ofertas))

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

                teclado = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Comprar", url=o["link"])
                ]])

                # 🔥 ANTI-BAN APLICADO AQUI
                await rate_limiter.wait()

                img_bytes = baixar_imagem(o["imagem"])

                if not img_bytes:
                    img_bytes = requests.get(
                        "https://static.promobit.com.br/assets/img/promobit-logo.png"
                    ).content

                await app_bot.bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=BytesIO(img_bytes),
                    caption=msg,
                    reply_markup=teclado
                )

                salvar(o["link"])
                enviados += 1

                print("ENVIADO:", o["titulo"])

            # pausa inteligente entre ciclos (não fixa)
            await asyncio.sleep(TEMPO + random.uniform(5, 30))

        except Exception as e:
            print("ERRO BOT:", repr(e))
            await asyncio.sleep(20)

# ================= START =================

async def main():
    import threading
    threading.Thread(target=run_web, daemon=True).start()
    await bot_loop()

if __name__ == "__main__":
    print("INICIANDO SISTEMA...")
    asyncio.run(main())