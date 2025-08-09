# web_runner.py
import os
from threading import Thread
from flask import Flask

# === import fungsi main() dari bot.py ===
from bot import main as run_bot

app = Flask(__name__)

@app.get("/")
def health():
    return "OK - telegram bot alive"

def start_bot():
    # Jalankan bot polling di thread lain (blocking kalau di main thread)
    run_bot()

if __name__ == "__main__":
    # Mulai bot
    Thread(target=start_bot, daemon=True).start()

    # Jalankan HTTP server agar Render melihat ada port yang dibuka
    port = int(os.getenv("PORT", "10000"))  # Render akan set PORT otomatis
    app.run(host="0.0.0.0", port=port)