import asyncio
import sqlite3
import requests
import re
import threading

from bs4 import BeautifulSoup
from flask import Flask

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.request import HTTPXRequest

# =========================================================
# CONFIGURAÇÕES
# =========================================================

TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID = -1001234567890

URL = "https://www.promobit.com.br"
TEMPO = 300
LIMITE = 3
AFILIADO = "?utm_source=telegram"

# =========================================================
# FLASK (RENDER PRECISA DISSO)
# =========================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot rodando"

def run_web():
    app.run(host="0.0.0.0", port=10000)

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

# =========================================================
# VERIFICAR REPETIÇÃO
# =========================================================

def oferta_ja_postada(link):
    cursor.execute("SELECT link FROM ofertas WHERE link=?", (link,))
    return cursor.fetchone()

def salvar_oferta(link):
    cursor.execute("INSERT INTO ofertas(link) VALUES(?)", (link,))
    conn.commit()

# =========================================================
# SCRAPING
# =========================================================

def pegar_ofertas():
    headers = {"User-Agent": "Mozilla/5.0"}

    resposta = requests.get(URL, headers=headers, timeout=30)

    soup = BeautifulSoup(resposta.text, "html.parser")

    ofertas = []
    links = soup.find_all("a")

    for item in links:
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

            imagem = "https://static.promobit.com.br/assets/img/promobit-logo.png"
            link_afiliado = link + AFILIADO

            ofertas.append({
                "titulo": titulo,
                "link": link_afiliado,
                "preco": preco,
                "imagem": imagem
            })

        except:
            pass

    return ofertas

# =========================================================
# BOT TELEGRAM
# =========================================================

async def enviar_ofertas():

    request = HTTPXRequest(
        connection_pool_size=20,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=30
    )

    bot = Bot(token=TOKEN, request=request)

    print("BOT INICIADO")

    while True:
        try:
            ofertas = pegar_ofertas()
            print("OFERTAS:", len(ofertas))

            enviados = 0

            for oferta in ofertas:

                if enviados >= LIMITE:
                    break

                titulo = oferta["titulo"]
                link = oferta["link"]
                preco = oferta["preco"]
                imagem = oferta["imagem"]

                if oferta_ja_postada(link):
                    continue

                mensagem = f"""🔥 OFERTA NOVA

📦 {titulo}

💰 {preco}
"""

                teclado = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Comprar", url=link)
                ]])

                await bot.send_photo(
                    chat_id=CHAT_ID,
                    photo=imagem,
                    caption=mensagem,
                    reply_markup=teclado
                )

                print("ENVIADO:", titulo)

                salvar_oferta(link)
                enviados += 1

                await asyncio.sleep(15)

            print("AGUARDANDO...")
            await asyncio.sleep(TEMPO)

        except Exception as erro:
            print("ERRO:", erro)
            await asyncio.sleep(30)

# =========================================================
# START (FLASK + BOT JUNTOS)
# =========================================================

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    asyncio.run(enviar_ofertas())