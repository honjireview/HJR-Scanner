# app/bot.py
# Инициализация ключевых объектов и настройка вебхука
import os
import logging
from flask import Flask, request, abort
from telebot import TeleBot, types

# --- 1. Настройка логирования и чтение переменных окружения ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

TOKEN = os.getenv("HJRSCANNER_TELEGRAM_TOKEN")
SECRET = os.getenv("WEBHOOK_SECRET")

if not TOKEN:
    log.critical("КРИТИЧЕСКАЯ ОШИБКА: HJRSCANNER_TELEGRAM_TOKEN не задан.")
    exit()

# --- 2. Инициализация ---
bot = TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# --- 3. Регистрация обработчиков ---
# Импортируем и вызываем регистратор из пакета handlers
from .handlers import register_all_handlers
register_all_handlers(bot)
log.info("Все обработчики успешно зарегистрированы.")

# --- 4. Маршрут для вебхука ---
@app.route('/telegram/hjr-scanner', methods=['POST'])
def webhook():
    log.info("--- START WEBHOOK PROCESSING ---")
    try:
        if request.headers.get('content-type') == 'application/json':
            if SECRET:
                header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
                if header_secret != SECRET:
                    log.warning(f"Отклонён запрос: неверный Secret Token.")
                    abort(403)

            json_string = request.get_data().decode('utf-8')
            update = types.Update.de_json(json_string)
            bot.process_new_updates([update])
            log.info("--- END WEBHOOK PROCESSING ---")
            return '', 200
        else:
            log.error(f"Отклонён запрос: неверный Content-Type: {request.headers.get('content-type')}")
            abort(403)
    except Exception as e:
        log.error(f"КРИТИЧЕСКАЯ ОШИБКА внутри обработчика webhook: {e}", exc_info=True)
        log.info("--- END WEBHOOK PROCESSING WITH ERROR ---")
        return "Error", 500

# Маршрут для проверки работоспособности
@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

log.info("Запуск HJR-Scanner в режиме Webhook (production)...")
log.info("Сервер готов принимать запросы от Cloudflare Worker.")