# app/handlers/logging.py
# Обработчики, отвечающие за логирование сообщений.
import logging
from ..database import queries
from .security import is_chat_allowed # Импортируем проверку из соседнего модуля

log = logging.getLogger(__name__)

def register_logging_handlers(bot):
    """Регистрирует обработчики для логирования."""

    # --- ОБРАБОТЧИКИ ДЛЯ ГРУПП ---
    @bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'sticker', 'voice', 'audio', 'location', 'contact'])
    def handle_new_message(message):
        if not is_chat_allowed(message.chat.id):
            return
        queries.log_new_message(message)

    @bot.edited_message_handler(func=lambda message: True)
    def handle_edited_message(message):
        if not is_chat_allowed(message.chat.id):
            return
        queries.log_edited_message(message)

    # --- (НОВОЕ) ОБРАБОТЧИКИ ДЛЯ КАНАЛОВ ---
    @bot.channel_post_handler(content_types=['text', 'photo', 'video', 'document', 'sticker', 'voice', 'audio', 'location', 'contact'])
    def handle_new_channel_post(message):
        log.info(f"Получен новый пост в канале: {message.chat.id}")
        if not is_chat_allowed(message.chat.id):
            return
        # Используем ту же функцию, что и для обычных сообщений
        queries.log_new_message(message)

    @bot.edited_channel_post_handler(func=lambda message: True)
    def handle_edited_channel_post(message):
        log.info(f"Получен измененный пост в канале: {message.chat.id}")
        if not is_chat_allowed(message.chat.id):
            return
        # Используем ту же функцию, что и для обычных сообщений
        queries.log_edited_message(message)