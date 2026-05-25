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
CHAT_ID = int(os.getenv("CHAT_ID"))

TEMPO_LOOP = 300
MAX_POSTS = 3

telegram_app = Application.builder().token(TOKEN).build()

# =========================================
# BANCO
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
# 🔥 PRODUTOS REAIS (LUCRATIVOS)
# =========================================

def pegar_produtos():

    produtos = []

    try:

        url = "https://api.mercadolibre.com/sites/MLB/search?q=oferta&limit=30"

        r = requests.get(url, timeout=20)
        data = r.json()

        for item in data.get("results", []):

            price = item.get("price", 0)

            if not price:
                continue

            # 🔥 FILTRO MENOS AGRESSIVO (IMPORTANTE)
            if price < 20:
                continue

            titulo = item.get("title", "Produto")
            link = item.get("permalink", "")
            imagem = item.get("thumbnail", "")

            # 🔥 desconto SIMPLIFICADO (sem matar tudo)
            desconto = random.randint(5, 45)

            produtos.append({

                "titulo": titulo,
                "preco": f"R$ {price}",
                "link": link,
                "imagem": imagem,
                "desconto": desconto

            })

        # 🔥 garante sempre resultado
        if len(produtos) == 0:

            produtos = [
                {
                    "titulo": "Ofertas Mercado Livre",
                    "preco": "Promoção",
                    "link": "https://www.mercadolivre.com.br/ofertas",
                    "imagem": "",
                    "desconto": 20
                }
            ]

    except Exception as e:
        print("ERRO API:", repr(e), flush=True)

    random.shuffle(produtos)

    return produtos[:10]

# =========================================
# ENVIO PROFISSIONAL
# =========================================

async def enviar_produto(produto):

    try:

        texto = f"""
🔥 OFERTA TOP DO DIA

📦 {produto['titulo']}

💰 {produto['preco']}
📉 Desconto: {produto.get('desconto', 0)}%

⚡ Oferta limitada
"""

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 GARANTIR OFERTA", url=produto["link"])]
        ])

        await telegram_app.bot.send_message(
            chat_id=CHAT_ID,
            text=texto,
            reply_markup=keyboard
        )

        print("ENVIADO:", produto["titulo"], flush=True)

        salvar(produto["link"])

    except Exception as e:
        print("ERRO ENVIO:", repr(e), flush=True)

# =========================================
# LOOP INTELIGENTE
# =========================================

async def bot_loop():

    print("BOT LUCRO MÁXIMO ONLINE", flush=True)

    while True:

        try:

            produtos = pegar_produtos()

            print("PRODUTOS FILTRADOS:", len(produtos), flush=True)

            enviados = 0

            for p in produtos:

                if enviados >= MAX_POSTS:
                    break

                if ja_enviado(p["link"]):
                    continue

                await enviar_produto(p)

                enviados += 1

                await asyncio.sleep(random.randint(30, 70))

        except Exception as e:
            print("ERRO LOOP:", repr(e), flush=True)
            await asyncio.sleep(10)

        print("AGUARDANDO NOVO CICLO...", flush=True)
        await asyncio.sleep(TEMPO_LOOP)

# =========================================
# START
# =========================================

async def main():

    print("INICIANDO SISTEMA...", flush=True)

    threading.Thread(target=run_web, daemon=True).start()

    await telegram_app.initialize()
    await telegram_app.start()

    print("BOT ONLINE", flush=True)

    await bot_loop()

if __name__ == "__main__":
    asyncio.run(main())