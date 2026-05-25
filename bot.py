import time
import threading
import requests
import logging
from flask import Flask

# =========================
# CONFIG
# =========================
TELEGRAM_TOKEN = "SEU_TOKEN"
TELEGRAM_CHAT_ID = "SEU_CHAT_ID"

# =========================
# LOGS PROFISSIONAIS
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("bot")

# =========================
# FLASK APP
# =========================
app = Flask(__name__)

@app.route("/")
def home():
    return "BOT EMPRESA ONLINE"

@app.route("/health")
def health():
    return {"status": "ok"}

# =========================
# ANTI DUPLICAÇÃO (MEMÓRIA)
# =========================
sent_products = set()

def is_sent(product_id):
    return product_id in sent_products

def mark_sent(product_id):
    sent_products.add(product_id)

# =========================
# PROVIDERS (SIMULADOS)
# =========================
def amazon_products():
    return [
        {"id": "amz_001", "title": "Fone Bluetooth Gamer", "price": 79.90, "link": "https://amazon.com"}
    ]

def ml_products():
    return [
        {"id": "ml_001", "title": "Mouse Gamer RGB", "price": 59.90, "link": "https://mercadolivre.com"}
    ]

def shopee_products():
    return [
        {"id": "sh_001", "title": "Teclado Mecânico", "price": 99.90, "link": "https://shopee.com"}
    ]

SOURCES = [amazon_products, ml_products, shopee_products]

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

    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text
        })
    except Exception as e:
        logger.error(f"Telegram error: {e}")

# =========================
# WORKER LOOP
# =========================
def worker():
    logger.info("worker_started")

    while True:
        try:
            for source in SOURCES:
                products = source()

                for product in products:
                    if is_sent(product["id"]):
                        continue

                    send_offer(product)
                    mark_sent(product["id"])

                    logger.info(f"sent: {product['title']}")

            logger.info("cycle_completed")

        except Exception as e:
            logger.error("worker_error", exc_info=True)

        time.sleep(60)

# =========================
# START WORKER THREAD
# =========================
threading.Thread(target=worker, daemon=True).start()

# =========================
# START SERVER
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)