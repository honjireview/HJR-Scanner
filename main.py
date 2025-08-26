# main.py
import telebot
import logging
import database
from handlers import register_handlers
import os
from flask import Flask, request, abort
from telebot import types

# Устанавливаем уровень логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# --- 1. Читаем переменные окружения ---
# Токен теперь берется из переменной HJRSCANNER_TELEGRAM_TOKEN
TOKEN = os.getenv("HJRSCANNER_TELEGRAM_TOKEN")
SECRET = os.getenv("WEBHOOK_SECRET") # Секретный токен для дополнительной безопасности (опционально)

if not TOKEN:
    log.critical("КРИТИЧЕСКАЯ ОШИБКА: HJRSCANNER_TELEGRAM_TOKEN не задан.")
    exit()

# --- 2. Инициализация ---
database.init_db()
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
register_handlers(bot)

# --- 3. Создаем маршруты ---

# Маршрут для приема вебхуков от Telegram, который соответствует пути в Cloudflare Worker
# Теперь он не содержит токена в URL
@app.route('/telegram/hjr-scanner', methods=['POST'])
def webhook():
    log.debug("!!! Webhook endpoint '/telegram/hjr-scanner' вызван!")
    try:
        if request.headers.get('content-type') == 'application/json':
            if SECRET:
                header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
                if header_secret != SECRET:
                    log.warning(f"Отклонён запрос: неверный Secret Token.")
                    abort(403)

            json_string = request.get_data().decode('utf-8')
            log.debug(f"Request Body (raw): {json_string}")

            update = types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return '', 200
        else:
            log.error(f"Отклонён запрос: неверный Content-Type: {request.headers.get('content-type')}")
            abort(403)
    except Exception as e:
        log.error(f"КРИТИЧЕСКАЯ ОШИБКА внутри обработчика webhook: {e}", exc_info=True)
        return "Error", 500

# Маршрут для проверки работоспособности сервера
@app.route('/health', methods=['GET'])
def health_check():
    log.debug("Health check endpoint вызван.")
    return "OK", 200

# --- 4. Запуск сервера ---
# Логика автоматической установки вебхука УДАЛЕНА.
# Вебхук теперь устанавливается один раз вручную, как указано в плане.
# Flask-приложение будет запущено gunicorn'ом, как указано в Procfile.
log.info("Запуск HJR-Scanner в режиме Webhook (production)...")
log.info("Сервер готов принимать запросы от Cloudflare Worker.")