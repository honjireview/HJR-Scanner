# app/bot.py (Полная версия с максимальным логированием)
import os
import logging
from flask import Flask, request, abort
from telebot import TeleBot, types
from threading import Thread # <-- Добавьте этот импорт
from .services import sync_editors_list # <-- Добавьте этот импорт

# --- 1. Настройка логирования и чтение переменных окружения ---
logging.basicConfig(
    level=logging.DEBUG, # Устанавливаем уровень DEBUG, чтобы видеть все сообщения
    format='%(asctime)s - %(name)s - %(levelname)s - [BOT-WEBHOOK] %(message)s'
)
log = logging.getLogger(__name__)

TOKEN = os.getenv("HJRSCANNER_TELEGRAM_TOKEN")
SECRET = os.getenv("WEBHOOK_SECRET") # Секрет для проверки заголовка X-Telegram-Bot-Api-Secret-Token

if not TOKEN:
    log.critical("КРИТИЧЕСКАЯ ОШИБКА: HJRSCANNER_TELEGRAM_TOKEN не задан.")
    exit()
if not SECRET:
    log.warning("ВНИМАНИЕ: WEBHOOK_SECRET не задан. Проверка секрета будет отключена.")

# --- 2. Инициализация ---
bot = TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

def run_on_startup():
    """Задачи, которые выполняются один раз при запуске бота."""
    import time
    time.sleep(3) # Небольшая задержка, чтобы дать другим сервисам запуститься
    log.info("Запуск первоначальной синхронизации списка редакторов...")
    try:
        sync_editors_list(bot)
    except Exception as e:
        log.error(f"Первоначальная синхронизация редакторов провалилась: {e}", exc_info=True)

startup_thread = Thread(target=run_on_startup)
startup_thread.start()
# --- КОНЕЦ ИЗМЕНЕНИЙ ---

# --- 3. Регистрация обработчиков --- (теперь пункт 3)
from .handlers import register_all_handlers
register_all_handlers(bot)
log.info("Все обработчики успешно зарегистрированы.")

# --- 3. Регистрация обработчиков ---
from .handlers import register_all_handlers
register_all_handlers(bot)
log.info("Все обработчики успешно зарегистрированы.")

# --- 4. Маршрут для вебхука (ИЗМЕНЕН ДЛЯ ДЕТАЛЬНОГО ЛОГИРОВАНИЯ) ---
@app.route('/telegram/hjr-scanner', methods=['POST'])
def webhook():
    log.info("--- 1. ВЕБХУК ПОЛУЧИЛ ЗАПРОС ---")
    try:
        # --- ДЕТАЛЬНЫЙ ЛОГ ЗАПРОСА ---
        log.debug(f"Метод запроса: {request.method}")
        log.debug(f"URL запроса: {request.url}")
        log.debug("--- Заголовки запроса ---")
        for header, value in request.headers.items():
            log.debug(f"{header}: {value}")
        log.debug("--- Тело запроса (raw) ---")
        request_body = request.get_data(as_text=True)
        log.debug(request_body)
        log.debug("---------------------------")
        # --- КОНЕЦ ДЕТАЛЬНОГО ЛОГА ---

        if request.headers.get('content-type') == 'application/json':
            if SECRET:
                log.info("--- 2. ПРОВЕРЯЮ СЕКРЕТНЫЙ ТОКЕН ---")
                header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
                if header_secret != SECRET:
                    log.error(f"ОШИБКА: Неверный Secret Token. Ожидался: '{SECRET}', получен: '{header_secret}'.")
                    abort(403)
                log.info("Секретный токен верный.")
            else:
                log.warning("Проверка секретного токена пропущена, т.к. переменная WEBHOOK_SECRET не установлена.")

            log.info("--- 3. ПЕРЕДАЮ ДАННЫЕ В TELEBOT ---")
            update = types.Update.de_json(request_body)
            bot.process_new_updates([update])
            log.info("--- 4. ОБРАБОТКА TELEBOT ЗАВЕРШЕНА ---")
            return '', 200
        else:
            log.error(f"Отклонён запрос: неверный Content-Type: {request.headers.get('content-type')}")
            abort(403)
    except Exception as e:
        log.error(f"КРИТИЧЕСКАЯ ОШИБКА внутри обработчика webhook: {e}", exc_info=True)
        log.info("--- ОБРАБОТКА ВЕБХУКА ЗАВЕРШЕНА С ОШИБКОЙ ---")
        return "Error", 500

@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

log.info("Запуск HJR-Scanner в режиме Webhook (production)...")