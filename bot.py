import threading
import time
import os
from flask import Flask

# ================= FLASK =================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot rodando OK"

# ================= BOT =================

def bot():
    print("BOT INICIADO")

    while True:
        print("BOT RODANDO...")
        time.sleep(60)

# ================= START BOT =================

def start_bot():
    threading.Thread(target=bot, daemon=True).start()

# ================= MAIN =================

if __name__ == "__main__":
    print("INICIANDO SISTEMA...")

    # inicia bot em background
    start_bot()

    # 🔥 FLASK TEM QUE SER O PRINCIPAL (NÃO THREAD)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)