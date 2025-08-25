# main.py
import telebot
import logging
import database
from handlers import register_handlers
import os
import time
from flask import Flask, request, abort
from telebot import types

# Настройка системного логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# --- 1. Читаем переменные окружения ---
TOKEN = os.getenv("HJRSCANNER_TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")

if not TOKEN:
    log.critical("КРИТИЧЕСКАЯ ОШИБКА: Переменная окружения HJRSCANNER_TELEGRAM_TOKEN не задана.")
    exit()

# --- 2. Инициализация ---
database.init_db()
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
register_handlers(bot)

# --- 3. Создаем маршрут для вебхука ---
# Telegram будет отправлять обновления на этот URL
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        if SECRET:
            header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if header_secret != SECRET:
                log.warning("Отклонён запрос: неверный X-Telegram-Bot-Api-Secret-Token")
                abort(403)

        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

# --- 4. Устанавливаем вебхук при старте ---
# Этот блок выполняется автоматически при запуске Gunicorn
log.info("Запуск HJR-Scanner в режиме Webhook (production)...")
if not WEBHOOK_URL:
    log.critical("КРИТИЧЕСКАЯ ОШИБКА: WEBHOOK_URL не задан, вебхук не будет установлен.")
else:
    try:
        bot.remove_webhook()
        time.sleep(0.5)
        bot.set_webhook(url=WEBHOOK_URL, secret_token=SECRET)
        log.info(f"Вебхук успешно установлен на: {WEBHOOK_URL}")
    except Exception as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось установить вебхук. {e}")