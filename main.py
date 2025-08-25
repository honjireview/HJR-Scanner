# main.py
import telebot
import logging
import config
import database
from handlers import register_handlers
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from telebot import types

# Настройка системного логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

def main():
    """
    Главная функция запуска бота.
    """
    log.info("Запуск HJR-Scanner (webhook mode)...")

    # 0. Читаем переменные окружения
    token = os.getenv("HJRSCANNER_TELEGRAM_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    port = int(os.getenv("PORT", "8080"))

    if not token:
        log.critical("КРИТИЧЕСКАЯ ОШИБКА: Переменная окружения HJRSCANNER_TELEGRAM_TOKEN не задана.")
        return
    if not webhook_url or not webhook_url.startswith("https://"):
        log.critical("КРИТИЧЕСКАЯ ОШИБКА: Переменная WEBHOOK_URL не задана или не https.")
        return

    # 1. Инициализация базы данных
    database.init_db()

    # 2. Создание и проверка экземпляра бота
    try:
        bot = telebot.TeleBot(token)
        bot_info = bot.get_me()
        log.info(f"Бот @{bot_info.username} успешно инициализирован.")
    except Exception as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Неверный токен или нет связи с API Telegram. {e}")
        return

    # 3. Регистрация обработчиков
    register_handlers(bot)

    # 4. Настройка вебхука
    try:
        bot.remove_webhook()
        if secret:
            bot.set_webhook(url=webhook_url, secret_token=secret)
            log.info("Webhook установлен с проверкой секретного токена.")
        else:
            bot.set_webhook(url=webhook_url)
            log.info("Webhook установлен без секретного токена.")
    except Exception as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось установить вебхук. {e}")
        return

    # 5. Встроенный HTTP-сервер для приёма апдейтов от Telegram
    class TelegramWebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            # Проверка секрета (если задан)
            if secret:
                header_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
                if header_secret != secret:
                    log.warning("Отклонён запрос: неверный X-Telegram-Bot-Api-Secret-Token")
                    self.send_response(403)
                    self.end_headers()
                    return
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length == 0:
                self.send_response(400)
                self.end_headers()
                return
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                update = types.Update.de_json(data)
                # Передаём апдейт боту
                bot.process_new_updates([update])
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
            except Exception as e:
                log.error(f"Ошибка обработки апдейта: {e}")
                self.send_response(500)
                self.end_headers()

        # Убираем лишний шум в логах HTTP-сервера
        def log_message(self, format, *args):
            return

    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, TelegramWebhookHandler)
    log.info(f"HTTP сервер запущен и слушает порт {port}. Ожидаем апдейты от Telegram...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        log.info("HTTP сервер остановлен.")

if __name__ == '__main__':
    main()