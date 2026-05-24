import os
import asyncio
import sqlite3
import threading
import requests
import random
import time

from flask import Flask, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

# =========================================
# FLASK WEB
# =========================================

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "bot": "Canal de Ofertas"
    })

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

TOKEN = os.environ.get("TOKEN")
CHAT_ID = int(os.environ.get("CHAT_ID"))

TEMPO_LOOP = 300

# anti-ban inteligente
DELAY_MIN = 15
DELAY_MAX = 40

# quantidade máxima por ciclo
MAX_ENVIOS = 5

# desconto mínimo
DESCONTO_MINIMO = 20

# =========================================
# TELEGRAM
# =========================================

telegram_app = Application.builder().token(TOKEN).build()

# =========================================
# BANCO SQLITE
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
    cursor.execute(
        "SELECT 1 FROM enviados WHERE link=?",
        (link,)
    )

    return cursor.fetchone() is not None

def salvar(link):
    cursor.execute(
        "INSERT OR IGNORE INTO enviados(link) VALUES(?)",
        (link,)
    )

    conn.commit()

# =========================================
# CATEGORIAS
# =========================================

CATEGORIAS = {
    "iphone": "📱 Smartphones",
    "samsung": "📱 Smartphones",
    "xiaomi": "📱 Smartphones",
    "notebook": "💻 Informática",
    "pc gamer": "💻 Informática",
    "tv": "📺 TVs",
    "monitor": "📺 TVs",
    "fone": "🎧 Áudio",
    "headset": "🎧 Áudio",
    "air fryer": "🍳 Cozinha",
    "cadeira gamer": "🪑 Gamer",
    "playstation": "🎮 Games",
    "xbox": "🎮 Games"
}

def descobrir_categoria(nome):

    nome = nome.lower()

    for chave, categoria in CATEGORIAS.items():

        if chave in nome:
            return categoria

    return "🛒 Ofertas"

# =========================================
# APIs / FEEDS
# =========================================

def pegar_produtos():

    produtos = []

    # =====================================
    # MERCADO LIVRE
    # =====================================

    try:

        url = "https://api.mercadolibre.com/sites/MLB/search?q=iphone"

        r = requests.get(url, timeout=30)

        data = r.json()

        for item in data.get("results", [])[:10]:

            preco = float(item.get("price", 0))

            original = item.get("original_price")

            desconto = 0

            if original and original > preco:
                desconto = int(
                    ((original - preco) / original) * 100
                )

            if desconto < DESCONTO_MINIMO:
                continue

            produtos.append({
                "titulo": item.get("title"),
                "preco": f"R$ {preco:.2f}",
                "desconto": desconto,
                "imagem": item.get("thumbnail"),
                "link": item.get("permalink"),
                "loja": "🟨 Mercado Livre"
            })

    except Exception as e:
        print("ERRO ML:", e, flush=True)

    # =====================================
    # AMAZON (RSS FEED)
    # =====================================

    try:

        feed = requests.get(
            "https://rss.app/feeds/v1.1/_amazon.xml",
            timeout=30
        )

        if feed.status_code == 200:

            # fallback fake parsing
            pass

    except Exception as e:
        print("ERRO AMAZON:", e, flush=True)

    # =====================================
    # SHOPEE (fallback)
    # =====================================

    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(
            "https://shopee.com.br/search?keyword=iphone",
            headers=headers,
            timeout=30
        )

        if r.status_code == 200:
            pass

    except Exception as e:
        print("ERRO SHOPEE:", e, flush=True)

    return produtos

# =========================================
# TEXTO BONITO
# =========================================

def montar_legenda(produto):

    categoria = descobrir_categoria(
        produto["titulo"]
    )

    texto = f"""
🔥 OFERTA ENCONTRADA

{categoria}

📦 {produto['titulo']}

💰 {produto['preco']}

🏷 Desconto: {produto['desconto']}%

🏪 {produto['loja']}

⚡ Promoção pode acabar a qualquer momento!
"""

    return texto

# =========================================
# ENVIO TELEGRAM
# =========================================

async def enviar_produto(produto):

    try:

        legenda = montar_legenda(produto)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🛒 COMPRAR AGORA",
                    url=produto["link"]
                )
            ]
        ])

        imagem = produto["imagem"]

        if imagem and imagem.startswith("//"):
            imagem = "https:" + imagem

        # =================================
        # FOTO
        # =================================

        if imagem:

            try:

                response = requests.get(
                    imagem,
                    timeout=15
                )

                if response.status_code == 200:

                    await telegram_app.bot.send_photo(
                        chat_id=CHAT_ID,
                        photo=response.content,
                        caption=legenda,
                        reply_markup=keyboard
                    )

                    return True

            except Exception as e:
                print("ERRO FOTO:", e, flush=True)

        # =================================
        # FALLBACK TEXTO
        # =================================

        await telegram_app.bot.send_message(
            chat_id=CHAT_ID,
            text=legenda,
            reply_markup=keyboard
        )

        return True

    except Exception as e:

        print("ERRO ENVIO:", repr(e), flush=True)

        return False

# =========================================
# LOOP
# =========================================

async def bot_loop():

    print("BOT INICIADO", flush=True)

    while True:

        try:

            produtos = pegar_produtos()

            print(
                "PRODUTOS:",
                len(produtos),
                flush=True
            )

            enviados = 0

            for produto in produtos:

                if enviados >= MAX_ENVIOS:
                    break

                if ja_enviado(produto["link"]):
                    continue

                enviado = await enviar_produto(produto)

                if enviado:

                    salvar(produto["link"])

                    enviados += 1

                    print(
                        "ENVIADO:",
                        produto["titulo"],
                        flush=True
                    )

                    # anti-ban inteligente
                    delay = random.randint(
                        DELAY_MIN,
                        DELAY_MAX
                    )

                    await asyncio.sleep(delay)

            print("AGUARDANDO...", flush=True)

            await asyncio.sleep(TEMPO_LOOP)

        except Exception as e:

            print(
                "ERRO LOOP:",
                repr(e),
                flush=True
            )

            await asyncio.sleep(60)

# =========================================
# MAIN
# =========================================

async def main():

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    await bot_loop()

if __name__ == "__main__":

    print("INICIANDO SISTEMA...", flush=True)

    asyncio.run(main())