import threading
import time
from flask import Flask

# ================= FLASK =================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot rodando OK"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# ================= BOT =================

def bot():
    print("BOT INICIADO")

    while True:
        print("BOT RODANDO...")
        time.sleep(60)

# ================= START =================

if __name__ == "__main__":
    print("INICIANDO SISTEMA...")

    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=bot, daemon=True).start()

    while True:
        time.sleep(999999)