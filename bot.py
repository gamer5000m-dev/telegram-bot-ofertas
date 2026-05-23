import threading
import time
import os
import requests
import re
import sqlite3
import random

from flask import Flask
from bs4 import BeautifulSoup

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.request import HTTPXRequest

# ================= FLASK =================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot rodando OK"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ================= CONFIG =================

TOKEN = "8391542912:AAH1cduJ0E7naPhA0z6uezCgkbLn1BjyQDE"
CHAT_ID = -1003914285353

URL = "https://www.promobit.com.br"
TEMPO = 300
LIMITE = 3

AFILIADO = "?utm_source=telegram&utm_medium=bot&utm_campaign=ofertas"

bot = Bot(token=TOKEN, request=HTTPXRequest())

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

# ================= UTIL =================

def delay_humano():
    time.sleep(random.randint(8, 18))

def pegar_imagem(item):
    img = item.find("img")

    if img:
        return img.get("data-src") or img.get("src")

    return "https://static.promobit.com.br/assets/img/promobit-logo.png"

# ================= SCRAP =================

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

            preco = "Preço não encontrado"
            p = re.findall(r"R\$\s?\d+[.,]?\d*", titulo)
            if p:
                preco = p[0]

            imagem = pegar_imagem(item)

            ofertas.append({
                "titulo": titulo,
                "link": link + AFILIADO,
                "preco": preco,
                "imagem": imagem
            })

        except:
            continue

    return ofertas

# ================= BOT =================

def rodar_bot():
    print("BOT PROFISSIONAL INICIADO")

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

                mensagem = f"""🔥 OFERTA VERIFICADA

📦 {o['titulo']}

💰 {o['preco']}

⚡ Promoção limitada
"""

                teclado = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Comprar agora", url=o["link"])
                ]])

                bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=o["imagem"],
                    caption=mensagem,
                    reply_markup=teclado
                )

                salvar(o["link"])
                enviados += 1

                print("ENVIADO:", o["titulo"])

                delay_humano()

            print("AGUARDANDO...")
            time.sleep(TEMPO)

        except Exception as e:
            print("ERRO:", repr(e))
            time.sleep(30)

# ================= START =================

if __name__ == "__main__":
    print("INICIANDO SISTEMA...")

    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=rodar_bot, daemon=True).start()

    while True:
        time.sleep(999999)