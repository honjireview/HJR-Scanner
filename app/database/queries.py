# app/database/queries.py (Полная версия с расширенным логированием)
import os
import requests
import logging
import json
from datetime import datetime

# --- Настройка ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - [BOT-CLIENT] %(message)s')
log = logging.getLogger(__name__)

API_BASE_URL = os.getenv("AHOST_API_URL")
API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN")

if not API_BASE_URL or not API_SECRET_TOKEN:
    log.critical("КРИТИЧЕСКАЯ ОШИБКА: Переменные API (AHOST_API_URL, API_SECRET_TOKEN) не заданы!")

HEADERS = {
    'Authorization': f'Bearer {API_SECRET_TOKEN}',
    'Content-Type': 'application/json'
}

# --- Вспомогательные функции ---
def serialize_user(user_obj):
    if not user_obj: return None
    return {'id': user_obj.id, 'is_bot': user_obj.is_bot, 'first_name': user_obj.first_name, 'username': user_obj.username}

def serialize_chat(chat_obj):
    if not chat_obj: return None
    return {'id': chat_obj.id, 'type': chat_obj.type, 'title': chat_obj.title}

def _send_request(endpoint, payload, message_ref):
    """Внутренняя функция для отправки и детального логирования запросов."""
    if not API_BASE_URL: return

    full_url = f"{API_BASE_URL}/{endpoint}"

    log.info(f"--- НАЧАЛО ОТПРАВКИ ЗАПРОСА ДЛЯ {message_ref} ---")
    log.info(f"ДЕБАГ: Целевой URL: {full_url}")
    log.info(f"ДЕБАГ: Отправляемые заголовки: {HEADERS}")
    log.info(f"ДЕБАГ: Отправляемые данные (payload): {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(full_url, data=json.dumps(payload), headers=HEADERS, timeout=20)
        log.info(f"ДЕБАГ: Ответ от сервера получен. Статус-код: {response.status_code}")
        log.info(f"ДЕБАГ: Тело ответа от сервера: {response.text}")
        response.raise_for_status()
        log.info(f"УСПЕХ: Запрос для {message_ref} успешно обработан сервером.")
    except requests.exceptions.RequestException as e:
        log.error(f"КРИТИЧЕСКАЯ ОШИБКА: Запрос для {message_ref} провалился. Ошибка: {e}", exc_info=True)
    finally:
        log.info(f"--- КОНЕЦ ОБРАБОТКИ ЗАПРОСА ДЛЯ {message_ref} ---")

# --- Основные функции ---
def init_db():
    log.info("Инициализация БД через API не требуется.")
    pass

def log_new_message(message):
    topic_id, topic_name = (None, None)
    if hasattr(message, 'is_topic_message') and message.is_topic_message:
        topic_id = message.message_thread_id
        topic_name = "General"
        if (message.reply_to_message and hasattr(message.reply_to_message, 'forum_topic_created') and message.reply_to_message.forum_topic_created):
            topic_name = message.reply_to_message.forum_topic_created.name

    fwd_chat_id, fwd_msg_id = (message.forward_from_chat.id, message.forward_from_message_id) if message.forward_from_chat else (None, None)
    file_id = None
    if message.content_type in ['photo', 'video', 'document', 'audio', 'voice', 'sticker']:
        media = getattr(message, message.content_type)
        if isinstance(media, list): file_id = media[-1].file_id if media else None
        elif hasattr(media, 'file_id'): file_id = media.file_id

    author_data = serialize_user(message.from_user) or {'id': None, 'username': None, 'first_name': getattr(message, 'author_signature', None), 'is_bot': None}

    payload = {
        'message_id': message.message_id, 'chat': serialize_chat(message.chat), 'date': message.date,
        'text': message.text or message.caption, 'content_type': message.content_type, 'author': author_data,
        'topic_id': topic_id, 'topic_name': topic_name, 'file_id': file_id,
        'reply_to_message_id': message.reply_to_message.message_id if message.reply_to_message else None,
        'forward_from_chat_id': fwd_chat_id, 'forward_from_message_id': fwd_msg_id
    }
    _send_request("log_new_message", payload, f"message_id {message.message_id}")

def log_edited_message(message):
    payload = {
        'message_id': message.message_id, 'chat_id': message.chat.id,
        'edit_date': message.edit_date, 'text': message.text or message.caption
    }
    _send_request("log_edited_message", payload, f"edited_message_id {message.message_id}")

def log_chat_member_update(update):
    old_status, new_status = update.old_chat_member.status, update.new_chat_member.status
    event_type = "unknown"
    if old_status in ['left', 'kicked'] and new_status in ['member', 'administrator', 'creator']: event_type = "joined"
    elif old_status in ['member', 'administrator', 'creator'] and new_status in ['left', 'kicked']: event_type = "left"
    if event_type == "unknown": return

    payload = {
        'date': update.date, 'chat': serialize_chat(update.chat),
        'user': serialize_user(update.new_chat_member.user), 'event_type': event_type,
        'actor_user_id': update.from_user.id
    }
    _send_request("log_chat_member_update", payload, f"chat_member_update for user {update.new_chat_member.user.id}")