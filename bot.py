import os
import asyncio
import sqlite3
import requests
import hashlib
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

# ================= CACHE DE IMAGEM =================

CACHE_DIR = "cache_imgs"
os.makedirs(CACHE_DIR, exist_ok=True)

def hash_url(url):
    return hashlib.md5(url.encode()).hexdigest()

def baixar_imagem(url):
    try:
        if not url:
            return None

        file_id = hash_url(url)
        path = os.path.join(CACHE_DIR, f"{file_id}.jpg")

        # já existe no cache
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()

        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(url, headers=headers, timeout=10, stream=True, allow_redirects=True)

        content_type = r.headers.get("Content-Type", "")

        if not content_type.startswith("image/"):
            return None

        if len(r.content) < 1500:
            return None

        # salva cache
        with open(path, "wb") as f:
            f.write(r.content)

        return r.content

    except:
        return None

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

            import re
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

                await asyncio.sleep(10)

            print("AGUARDANDO...")
            await asyncio.sleep(TEMPO)

        except Exception as e:
            print("ERRO BOT:", repr(e))
            await asyncio.sleep(30)

# ================= START =================

async def main():
    import threading
    threading.Thread(target=run_web, daemon=True).start()
    await bot_loop()

if __name__ == "__main__":
    print("INICIANDO SISTEMA...")
    asyncio.run(main())