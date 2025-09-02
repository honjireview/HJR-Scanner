# app/database/queries.py (Полная версия)
import os
import requests
import logging
import json
from datetime import datetime

log = logging.getLogger(__name__)

# URL, который вы указали. Он будет браться из переменных окружения.
API_BASE_URL = os.getenv("AHOST_API_URL")
API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN")

if not API_BASE_URL or not API_SECRET_TOKEN:
    log.critical("КРИТИЧЕСКАЯ ОШИБКА: Переменные API (AHOST_API_URL, API_SECRET_TOKEN) не заданы!")

HEADERS = {
    'Authorization': f'Bearer {API_SECRET_TOKEN}',
    'Content-Type': 'application/json'
}

# --- Вспомогательные функции для преобразования объектов в словари ---
def serialize_user(user_obj):
    if not user_obj:
        return None
    return {
        'id': user_obj.id,
        'is_bot': user_obj.is_bot,
        'first_name': user_obj.first_name,
        'username': user_obj.username
    }

def serialize_chat(chat_obj):
    if not chat_obj:
        return None
    return {
        'id': chat_obj.id,
        'type': chat_obj.type,
        'title': chat_obj.title
    }

# --- Основные функции, переписанные для работы с API ---

def init_db():
    log.info("Инициализация БД через API не требуется. Схема должна быть создана на сервере вручную.")
    pass

def log_new_message(message):
    if not API_BASE_URL: return
    endpoint = f"{API_BASE_URL}/log_new_message"

    # --- Сохраняем всю вашу оригинальную логику обработки сообщения ---
    topic_id, topic_name = (None, None)
    if hasattr(message, 'is_topic_message') and message.is_topic_message:
        topic_id = message.message_thread_id
        if (message.reply_to_message and hasattr(message.reply_to_message, 'forum_topic_created') and
                message.reply_to_message.forum_topic_created):
            topic_name = message.reply_to_message.forum_topic_created.name
        else:
            topic_name = "General"

    fwd_chat_id, fwd_msg_id = (message.forward_from_chat.id, message.forward_from_message_id) if message.forward_from_chat else (None, None)

    file_id = None
    if message.content_type in ['photo', 'video', 'document', 'audio', 'voice', 'sticker']:
        media = getattr(message, message.content_type)
        if isinstance(media, list):
            file_id = media[-1].file_id if media else None
        elif hasattr(media, 'file_id'):
            file_id = media.file_id

    author = message.from_user
    author_data = serialize_user(author) or {
        'id': None, 'username': None,
        'first_name': getattr(message, 'author_signature', None),
        'is_bot': None
    }

    # --- Формируем ПОЛНЫЙ payload для отправки на API ---
    payload = {
        'message_id': message.message_id,
        'chat': serialize_chat(message.chat),
        'date': message.date,
        'text': message.text or message.caption,
        'content_type': message.content_type,
        'author': author_data,
        'topic_id': topic_id,
        'topic_name': topic_name,
        'file_id': file_id,
        'reply_to_message_id': message.reply_to_message.message_id if message.reply_to_message else None,
        'forward_from_chat_id': fwd_chat_id,
        'forward_from_message_id': fwd_msg_id
    }

    try:
        response = requests.post(endpoint, data=json.dumps(payload), headers=HEADERS, timeout=15)
        response.raise_for_status() # Вызовет ошибку, если API вернет 4xx или 5xx
        log.info(f"Сообщение {message.message_id} успешно отправлено на API.")
    except requests.exceptions.RequestException as e:
        log.error(f"Ошибка при отправке нового сообщения ({message.message_id}) на API: {e}")

def log_edited_message(message):
    if not API_BASE_URL: return
    endpoint = f"{API_BASE_URL}/log_edited_message"

    payload = {
        'message_id': message.message_id,
        'chat_id': message.chat.id,
        'edit_date': message.edit_date,
        'text': message.text or message.caption
    }
    try:
        response = requests.post(endpoint, data=json.dumps(payload), headers=HEADERS, timeout=15)
        response.raise_for_status()
        log.info(f"Изменение сообщения {message.message_id} успешно отправлено на API.")
    except requests.exceptions.RequestException as e:
        log.error(f"Ошибка при отправке изменения сообщения ({message.message_id}) на API: {e}")

def log_chat_member_update(update):
    if not API_BASE_URL: return
    endpoint = f"{API_BASE_URL}/log_chat_member_update"

    # --- Сохраняем вашу оригинальную логику определения события ---
    old_status, new_status = update.old_chat_member.status, update.new_chat_member.status
    event_type = "unknown"
    if old_status in ['left', 'kicked'] and new_status in ['member', 'administrator', 'creator']:
        event_type = "joined"
    elif old_status in ['member', 'administrator', 'creator'] and new_status in ['left', 'kicked']:
        event_type = "left"

    if event_type == "unknown":
        return

    payload = {
        'date': update.date,
        'chat': serialize_chat(update.chat),
        'user': serialize_user(update.new_chat_member.user),
        'event_type': event_type,
        'actor_user_id': update.from_user.id
    }
    try:
        response = requests.post(endpoint, data=json.dumps(payload), headers=HEADERS, timeout=15)
        response.raise_for_status()
        log.info(f"Событие с участником чата {update.new_chat_member.user.id} отправлено на API.")
    except requests.exceptions.RequestException as e:
        log.error(f"Ошибка при отправке события с участником чата на API: {e}")