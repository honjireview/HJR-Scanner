# main.py
import telebot
import logging
import database
from handlers import register_handlers
import os
import time
from flask import Flask, request, abort
from telebot import types

# Устанавливаем уровень логирования на DEBUG
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# --- 1. Читаем переменные окружения ---
TOKEN = os.getenv("HJRSCANNER_TELEGRAM_TOKEN")
BASE_WEBHOOK_URL = os.getenv("WEBHOOK_URL")
SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")

if not TOKEN:
    log.critical("КРИТИЧЕСКАЯ ОШИБКА: HJRSCANNER_TELEGRAM_TOKEN не задан.")
    exit()

# --- 2. Инициализация ---
database.init_db()
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)
register_handlers(bot)

# --- 3. Создаем маршруты ---

# Маршрут для приема вебхуков от Telegram
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    log.debug("!!! Webhook endpoint вызван! Входящий запрос получен.")
    try:
        if request.headers.get('content-type') == 'application/json':
            if SECRET:
                header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
                if header_secret != SECRET:
                    log.warning(f"Отклонён запрос: неверный Secret Token. Ожидали: {SECRET}, получили: {header_secret}")
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

# --- 4. Устанавливаем вебхук при старте ---
log.info("Запуск HJR-Scanner в режиме Webhook (production)...")
if not BASE_WEBHOOK_URL:
    log.critical("КРИТИЧЕСКАЯ ОШИБКА: WEBHOOK_URL не задан.")
else:
    full_webhook_url = f"{BASE_WEBHOOK_URL.strip('/')}/{TOKEN}"
    try:
        log.info("Удаляем старый вебхук...")
        bot.remove_webhook()
        time.sleep(0.5)
        log.info(f"Устанавливаем новый вебхук на: {full_webhook_url}")
        success = bot.set_webhook(url=full_webhook_url, secret_token=SECRET)
        if not success:
            log.error("API Telegram ответил 'False' на установку вебхука.")
        else:
            log.info("Вебхук успешно установлен.")

        webhook_info = bot.get_webhook_info()
        log.info(f"Информация о вебхуке от Telegram: {webhook_info}")

    except Exception as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось установить вебхук. {e}", exc_info=True)