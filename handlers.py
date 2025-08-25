# handlers.py
import logging
import database

log = logging.getLogger(__name__)

def register_handlers(bot):
    """
    Регистрирует все обработчики сообщений для бота.
    """

    @bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'sticker', 'voice', 'audio', 'location', 'contact'])
    def handle_new_message(message):
        """
        Срабатывает на любое новое сообщение и отправляет его на логирование.
        """
        log.debug(f"Получено новое сообщение {message.message_id} от @{message.from_user.username}")
        database.log_new_message(message)

    @bot.edited_message_handler(func=lambda message: True)
    def handle_edited_message(message):
        """
        Срабатывает на любое измененное сообщение и отправляет его на логирование.
        """
        log.debug(f"Получено изменение сообщения {message.message_id} от @{message.from_user.username}")
        database.log_edited_message(message)

    log.info("Обработчики сообщений успешно зарегистрированы.")