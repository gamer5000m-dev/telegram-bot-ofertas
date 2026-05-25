from flask import Flask, request, jsonify
import psycopg2
import requests
import time
import threading

app = Flask(__name__)

# =========================
# CONFIG
# =========================
DATABASE_URL = "SUA_DATABASE_URL"
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

# =========================
# DB
# =========================
def conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    c = conn()
    cur = c.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bots (
        id SERIAL PRIMARY KEY,
        user_id INT,
        name TEXT,
        active BOOLEAN DEFAULT true
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sent_products (
        id TEXT,
        bot_id INT,
        PRIMARY KEY(id, bot_id)
    )
    """)

    c.commit()
    c.close()

# =========================
# PROVIDER (MOCK)
# =========================
def get_products():
    return [
        {"id": "1", "title": "Fone Gamer", "price": 79.90, "link": "https://amazon.com"},
        {"id": "2", "title": "Mouse RGB", "price": 59.90, "link": "https://ml.com"}
    ]

# =========================
# TELEGRAM
# =========================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    })

# =========================
# CHECK DUPLICATE
# =========================
def is_sent(bot_id, product_id):
    c = conn()
    cur = c.cursor()

    cur.execute(
        "SELECT 1 FROM sent_products WHERE id=%s AND bot_id=%s",
        (product_id, bot_id)
    )

    r = cur.fetchone()
    c.close()
    return r is not None

def mark_sent(bot_id, product_id):
    c = conn()
    cur = c.cursor()

    cur.execute(
        "INSERT INTO sent_products (id, bot_id) VALUES (%s, %s)",
        (product_id, bot_id)
    )

    c.commit()
    c.close()

# =========================
# BOT ENGINE
# =========================
def worker():
    init_db()

    while True:
        try:
            bots = get_bots()

            for bot in bots:
                products = get_products()

                for p in products:
                    if is_sent(bot["id"], p["id"]):
                        continue

                    msg = f"""
🔥 OFERTA

{p['title']}
💰 R$ {p['price']}
👉 {p['link']}
"""
                    send_telegram(msg)
                    mark_sent(bot["id"], p["id"])

            print("cycle_done")

        except Exception as e:
            print("ERROR:", e)

        time.sleep(60)

def get_bots():
    c = conn()
    cur = c.cursor()

    cur.execute("SELECT id FROM bots WHERE active=true")
    rows = cur.fetchall()

    c.close()

    return [{"id": r[0]} for r in rows]

# =========================
# API / SAAS
# =========================
@app.route("/")
def home():
    return "SAAS BOT ONLINE"

@app.route("/create_user", methods=["POST"])
def create_user():
    data = request.json

    c = conn()
    cur = c.cursor()

    cur.execute(
        "INSERT INTO users (email, password) VALUES (%s,%s)",
        (data["email"], data["password"])
    )

    c.commit()
    c.close()

    return {"status": "user_created"}

@app.route("/create_bot", methods=["POST"])
def create_bot():
    data = request.json

    c = conn()
    cur = c.cursor()

    cur.execute(
        "INSERT INTO bots (user_id, name) VALUES (%s,%s)",
        (data["user_id"], data["name"])
    )

    c.commit()
    c.close()

    return {"status": "bot_created"}

@app.route("/health")
def health():
    return {"status": "ok"}

# =========================
# START WORKER THREAD
# =========================
threading.Thread(target=worker, daemon=True).start()

# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)