import threading
import asyncio
import time
import os
import requests
import random
import sqlite3

from flask import Flask, request
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# ================= CONFIG =================

TOKEN = "8391542912:AAH1cduJ0E7naPhA0z6uezCgkbLn1BjyQDE"
CHAT_ID = -1003914285353

bot = Bot(token=TOKEN)

app = Flask(__name__)

# ================= PAINEL ADMIN =================

CONFIG = {
    "min_desconto": 20,
    "keywords": ["smartphone", "fone", "teclado"],
    "cooldown": 8
}

@app.route("/")
def home():
    return "BOT ONLINE"

@app.route("/config")
def config():
    return CONFIG

@app.route("/set_desconto")
def set_desconto():
    CONFIG["min_desconto"] = int(request.args.get("v", 20))
    return "OK"

# ================= BANCO =================

conn = sqlite3.connect("produtos.db", check_same_thread=False)
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
    cursor.execute("INSERT OR IGNORE INTO enviados VALUES(?)", (link,))
    conn.commit()

# ================= RATE LIMIT =================

async def rate_limit():
    await asyncio.sleep(random.uniform(6, 14))

# ================= MERCADO LIVRE =================

def ml_search(keyword):
    url = f"https://api.mercadolibre.com/sites/MLB/search?q={keyword}&limit=10"
    r = requests.get(url, timeout=10)
    data = r.json()

    produtos = []

    for item in data["results"]:
        produtos.append({
            "titulo": item["title"],
            "preco": float(item["price"]),
            "imagem": item["thumbnail"],
            "link": item["permalink"],
            "loja": "Mercado Livre",
            "desconto": 25  # placeholder (ML não traz desconto direto)
        })

    return produtos

# ================= SHOPEE =================

def shopee_search(keyword):
    url = f"https://shopee.com.br/api/v4/search/search_items?keyword={keyword}&limit=10"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers, timeout=10)
    data = r.json()

    produtos = []

    for item in data.get("items", []):
        p = item["item_basic"]

        produtos.append({
            "titulo": p["name"],
            "preco": p["price"] / 100000,
            "imagem": "https://cf.shopee.com.br/file/" + p["image"],
            "link": f"https://shopee.com.br/product/{p['shopid']}/{p['itemid']}",
            "loja": "Shopee",
            "desconto": 30
        })

    return produtos

# ================= COLETOR =================

def coletar_produtos():
    produtos = []

    for k in CONFIG["keywords"]:
        try:
            produtos += ml_search(k)
            produtos += shopee_search(k)
        except:
            continue

    return produtos

# ================= FILTRO =================

def filtrar(produtos):
    filtrados = []

    for p in produtos:

        if len(p["titulo"]) < 20:
            continue

        if p["preco"] <= 0:
            continue

        if p["desconto"] < CONFIG["min_desconto"]:
            continue

        filtrados.append(p)

    return filtrados

# ================= ENVIO TELEGRAM =================

async def enviar(p):

    msg = f"""🔥 OFERTA {p['loja']}

📦 {p['titulo']}

💰 R$ {p['preco']}
🔥 {p['desconto']}% OFF
"""

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🛒 Comprar", url=p["link"])
    ]])

    try:
        await bot.send_photo(
            chat_id=CHAT_ID,
            photo=p["imagem"],
            caption=msg[:1020],
            reply_markup=keyboard
        )
    except:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=msg + f"\n\n{p['link']}",
            reply_markup=keyboard
        )

# ================= LOOP PRINCIPAL =================

async def loop():

    print("BOT INICIADO", flush=True)

    enviados = set()

    while True:

        produtos = coletar_produtos()
        produtos = filtrar(produtos)

        print("PRODUTOS:", len(produtos), flush=True)

        for p in produtos:

            if p["link"] in enviados:
                continue

            try:
                await enviar(p)
                salvar(p["link"])
                enviados.add(p["link"])

                print("ENVIADO:", p["titulo"])

                await rate_limit()

            except Exception as e:
                print("ERRO:", repr(e))

        await asyncio.sleep(300)

# ================= FLASK THREAD =================

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ================= START =================

async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    await loop()

if __name__ == "__main__":
    print("INICIANDO SISTEMA...", flush=True)
    asyncio.run(main())