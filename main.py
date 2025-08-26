# main.py
import telebot
import logging
import database
from handlers import register_handlers
import os
from flask import Flask, request, abort
from telebot import types
import json # Импортируем json для красивого вывода

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
    log.info("--- START WEBHOOK PROCESSING ---")
    log.debug("!!! Webhook endpoint '/telegram/hjr-scanner' вызван!")

    # Дебаг: Выводим все заголовки запроса, чтобы видеть, что присылает Cloudflare
    log.debug(f"Входящие заголовки: {dict(request.headers)}")

    try:
        if request.headers.get('content-type') == 'application/json':
            log.debug("Проверка Content-Type: Успешно (application/json).")

            # Дебаг: Проверка секретного токена
            if SECRET:
                header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
                log.debug(f"Проверка Secret Token. Ожидаемый: ***{SECRET[-4:]}, Полученный: {header_secret}")
                if header_secret != SECRET:
                    log.warning(f"Отклонён запрос: неверный Secret Token.")
                    abort(403)
                log.debug("Проверка Secret Token: Успешно.")

            json_string = request.get_data().decode('utf-8')
            # Дебаг: Выводим тело запроса в форматированном виде
            try:
                pretty_json = json.dumps(json.loads(json_string), indent=2, ensure_ascii=False)
                log.debug(f"Request Body (formatted):\n{pretty_json}")
            except json.JSONDecodeError:
                log.warning(f"Не удалось отформатировать JSON, показываю как есть: {json_string}")

            log.debug("Начинаю обработку update'а библиотекой pyTelegramBotAPI...")
            update = types.Update.de_json(json_string)
            bot.process_new_updates([update])
            log.info("Обработка update'а успешно завершена.")
            log.info("--- END WEBHOOK PROCESSING ---")
            return '', 200
        else:
            log.error(f"Отклонён запрос: неверный Content-Type: {request.headers.get('content-type')}")
            abort(403)
    except Exception as e:
        log.error(f"КРИТИЧЕСКАЯ ОШИБКА внутри обработчика webhook: {e}", exc_info=True)
        log.info("--- END WEBHOOK PROCESSING WITH ERROR ---")
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