import asyncio
import sqlite3
import requests
import re
import threading
import os

from bs4 import BeautifulSoup
from flask import Flask

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.request import HTTPXRequest

# =========================================================
# CONFIG
# =========================================================

TOKEN = "8391542912:AAH1cduJ0E7naPhA0z6uezCgkbLn1BjyQDE"
CHAT_ID = -1003914285353

URL = "https://www.promobit.com.br"
TEMPO = 300
LIMITE = 3
AFILIADO = "?utm_source=telegram"

# =========================================================
# FLASK (RENDER KEEP ALIVE)
# =========================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot rodando"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )

# =========================================================
# BANCO DE DADOS
# =========================================================

conn = sqlite3.connect("ofertas.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS ofertas (
    link TEXT PRIMARY KEY
)
""")

conn.commit()

def oferta_ja_postada(link):
    cursor.execute("SELECT 1 FROM ofertas WHERE link=?", (link,))
    return cursor.fetchone()

def salvar_oferta(link):
    cursor.execute("INSERT OR IGNORE INTO ofertas(link) VALUES(?)", (link,))
    conn.commit()

# =========================================================
# SCRAPING (CORRIGIDO)
# =========================================================

def pegar_ofertas():
    headers = {"User-Agent": "Mozilla/5.0"}

    resposta = requests.get(URL, headers=headers, timeout=30)
    soup = BeautifulSoup(resposta.text, "html.parser")

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

            preco = "Confira no site"
            precos = re.findall(r"R\$\s?\d+[.,]?\d*", titulo)
            if precos:
                preco = precos[0]

            oferta = {
                "titulo": titulo,
                "link": link + AFILIADO,
                "preco": preco,
                "imagem": "https://static.promobit.com.br/assets/img/promobit-logo.png"
            }

            ofertas.append(oferta)

        except Exception as e:
            print("SCRAP ERROR:", repr(e))
            continue

    return ofertas

# =========================================================
# BOT
# =========================================================

async def enviar_ofertas():

    bot = Bot(
        token=TOKEN,
        request=HTTPXRequest()
    )

    print("BOT INICIADO")

    while True:
        try:
            ofertas = pegar_ofertas()
            print("OFERTAS:", len(ofertas))

            enviados = 0

            for oferta in ofertas:

                if enviados >= LIMITE:
                    break

                link = oferta["link"]

                if oferta_ja_postada(link):
                    continue

                mensagem = f"""🔥 OFERTA NOVA

📦 {oferta['titulo']}

💰 {oferta['preco']}
"""

                teclado = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Comprar", url=link)
                ]])

                await bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=oferta["imagem"],
                    caption=mensagem,
                    reply_markup=teclado
                )

                salvar_oferta(link)
                enviados += 1

                print("ENVIADO:", oferta["titulo"])

                await asyncio.sleep(10)

            print("AGUARDANDO...")
            await asyncio.sleep(TEMPO)

        except Exception as e:
            print("ERRO COMPLETO:", repr(e))
            await asyncio.sleep(30)

# =========================================================
# START (RENDER SAFE)
# =========================================================

def start_bot():
    asyncio.run(enviar_ofertas())

if __name__ == "__main__":
    print("INICIANDO SISTEMA...")

    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=start_bot, daemon=True).start()