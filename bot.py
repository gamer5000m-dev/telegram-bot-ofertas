import os
import re
import asyncio
import sqlite3
import threading
import random
import requests

from flask import Flask
from bs4 import BeautifulSoup

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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13)"
        " AppleWebKit/537.36"
        " Chrome/120 Safari/537.36"
    )
}

FONTES = [
    "https://www.pelando.com.br/grupo/amazon",
    "https://www.pelando.com.br/grupo/shopee",
    "https://www.pelando.com.br/grupo/mercado-livre"
]

KEYWORDS_BLOQUEADAS = [
    "grupo",
    "telegram",
    "whatsapp",
    "cupom",
    "frete grátis",
    "comentários",
    "login",
    "entrar",
    "categorias"
]

# =========================================
# TELEGRAM
# =========================================

telegram_app = Application.builder().token(TOKEN).build()

# =========================================
# DATABASE
# =========================================

conn = sqlite3.connect(
    "ofertas.db",
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS enviados (
    link TEXT PRIMARY KEY
)
""")

conn.commit()

def ja_enviado(link):

    cursor.execute(
        "SELECT 1 FROM enviados WHERE link=?",
        (link,)
    )

    return cursor.fetchone()

def salvar(link):

    cursor.execute(
        "INSERT OR IGNORE INTO enviados(link) VALUES(?)",
        (link,)
    )

    conn.commit()

# =========================================
# VALIDAR IMAGEM
# =========================================

def imagem_valida(url):

    try:

        if not url:
            return False

        if ".svg" in url:
            return False

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=10,
            stream=True
        )

        if r.status_code != 200:
            return False

        content = r.headers.get(
            "Content-Type",
            ""
        )

        if "image" not in content:
            return False

        return True

    except:
        return False

# =========================================
# PEGAR PRODUTOS
# =========================================

def pegar_produtos():

    produtos = []

    for url in FONTES:

        try:

            r = requests.get(
                url,
                headers=HEADERS,
                timeout=30
            )

            soup = BeautifulSoup(
                r.text,
                "html.parser"
            )

            ofertas = soup.find_all("article")

            for item in ofertas:

                try:

                    texto = item.get_text(
                        " ",
                        strip=True
                    )

                    if "R$" not in texto:
                        continue

                    if len(texto) < 40:
                        continue

                    texto_lower = texto.lower()

                    if any(
                        palavra in texto_lower
                        for palavra in KEYWORDS_BLOQUEADAS
                    ):
                        continue

                    titulo = ""

                    h2 = item.find("h2")

                    if h2:
                        titulo = h2.get_text(
                            " ",
                            strip=True
                        )

                    if not titulo:
                        continue

                    # PREÇO

                    preco = None

                    p = re.search(
                        r"R\$\s?[\d\.,]+",
                        texto
                    )

                    if p:
                        preco = p.group(0)

                    if not preco:
                        continue

                    # DESCONTO

                    desconto = ""

                    d = re.search(
                        r"(\d+)%",
                        texto
                    )

                    if d:
                        desconto = d.group(1) + "% OFF"

                    # LINK

                    link = None

                    a = item.find("a")

                    if a:

                        href = a.get("href")

                        if href:

                            if href.startswith("/"):
                                link = (
                                    "https://www.pelando.com.br"
                                    + href
                                )

                            else:
                                link = href

                    if not link:
                        continue

                    # IMAGEM

                    imagem = None

                    img = item.find("img")

                    if img:

                        imagem = (
                            img.get("src")
                            or img.get("data-src")
                            or img.get("data-lazy-src")
                            or img.get("data-original")
                        )

                    if imagem:

                        if imagem.startswith("//"):
                            imagem = "https:" + imagem

                        if ".svg" in imagem:
                            imagem = None

                    produtos.append({
                        "titulo": titulo[:150],
                        "preco": preco,
                        "desconto": desconto,
                        "link": link,
                        "imagem": imagem
                    })

                except:
                    pass

        except Exception as e:

            print(
                "ERRO SCRAP:",
                repr(e),
                flush=True
            )

    return produtos

# =========================================
# ENVIAR TELEGRAM
# =========================================

async def enviar_produto(produto):

    titulo = produto["titulo"]
    preco = produto["preco"]
    desconto = produto["desconto"]
    link = produto["link"]
    imagem = produto["imagem"]

    texto = f"""
🔥 OFERTA ENCONTRADA

📦 {titulo}

💰 PREÇO: {preco}
"""

    if desconto:
        texto += f"\n🏷 DESCONTO: {desconto}"

    texto += "\n\n⚡ Promoção por tempo limitado"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛒 COMPRAR AGORA",
                url=link
            )
        ]
    ])

    try:

        # COM IMAGEM
        if imagem and imagem_valida(imagem):

            await telegram_app.bot.send_photo(
                chat_id=CHAT_ID,
                photo=imagem,
                caption=texto,
                reply_markup=keyboard
            )

        # SEM IMAGEM
        else:

            await telegram_app.bot.send_message(
                chat_id=CHAT_ID,
                text=texto,
                reply_markup=keyboard
            )

        print(
            "ENVIADO:",
            titulo,
            flush=True
        )

        salvar(link)

    except Exception as e:

        print(
            "ERRO ENVIO:",
            repr(e),
            flush=True
        )

# =========================================
# LOOP PRINCIPAL
# =========================================

async def bot_loop():

    print(
        "BOT INICIADO",
        flush=True
    )

    while True:

        try:

            produtos = pegar_produtos()

            random.shuffle(produtos)

            print(
                "PRODUTOS:",
                len(produtos),
                flush=True
            )

            enviados = 0

            for produto in produtos:

                if enviados >= MAX_POSTS:
                    break

                if ja_enviado(produto["link"]):
                    continue

                await enviar_produto(produto)

                enviados += 1

                # ANTI BAN TELEGRAM
                espera = random.randint(40, 90)

                print(
                    f"ANTI-SPAM: {espera}s",
                    flush=True
                )

                await asyncio.sleep(espera)

            print(
                "AGUARDANDO NOVO CICLO...",
                flush=True
            )

            await asyncio.sleep(TEMPO_LOOP)

        except Exception as e:

            print(
                "ERRO LOOP:",
                repr(e),
                flush=True
            )

            await asyncio.sleep(60)

# =========================================
# START
# =========================================

async def main():

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    await bot_loop()

if __name__ == "__main__":

    print(
        "INICIANDO SISTEMA...",
        flush=True
    )

    asyncio.run(main())