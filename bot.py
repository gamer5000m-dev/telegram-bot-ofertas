import time
import threading
import requests
import psycopg2
from flask import Flask

# =========================
# CONFIG (ENV VARS NO RENDER)
# =========================
DATABASE_URL = "SUA_DATABASE_URL"
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

# =========================
# FLASK APP (WEB HEALTHCHECK)
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "BOT OFERTAS ONLINE OK"

@app.route("/health")
def health():
    return {"status": "ok"}

# =========================
# DATABASE
# =========================
def conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    c = conn()
    cur = c.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sent_products (
        id TEXT PRIMARY KEY
    )
    """)

    c.commit()
    c.close()

def is_sent(product_id):
    c = conn()
    cur = c.cursor()

    cur.execute("SELECT 1 FROM sent_products WHERE id=%s", (product_id,))
    r = cur.fetchone()

    c.close()
    return r is not None

def mark_sent(product_id):
    c = conn()
    cur = c.cursor()

    cur.execute(
        "INSERT INTO sent_products (id) VALUES (%s) ON CONFLICT DO NOTHING",
        (product_id,)
    )

    c.commit()
    c.close()

# =========================
# PROVIDERS (SIMULADO)
# =========================
def get_products():
    return [
        {"id": "1", "title": "Fone Bluetooth Gamer", "price": 79.90, "link": "https://amazon.com"},
        {"id": "2", "title": "Mouse Gamer RGB", "price": 59.90, "link": "https://mercadolivre.com"},
        {"id": "3", "title": "Teclado Mecânico", "price": 99.90, "link": "https://shopee.com"}
    ]

# =========================
# TELEGRAM
# =========================
def send_offer(product):
    text = f"""
🔥 OFERTA DO DIA 🔥

{product['title']}
💰 R$ {product['price']}

👉 {product['link']}
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    })

# =========================
# WORKER (LOOP SEGURO)
# =========================
def worker():
    init_db()
    print("WORKER ONLINE")

    while True:
        try:
            products = get_products()

            for p in products:
                if is_sent(p["id"]):
                    continue

                send_offer(p)
                mark_sent(p["id"])

                print("SENT:", p["title"])

            print("CYCLE OK")

        except Exception as e:
            print("ERROR:", e)

        time.sleep(60)

# =========================
# START WORKER THREAD
# =========================
threading.Thread(target=worker, daemon=True).start()

# =========================
# START WEB SERVER
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)