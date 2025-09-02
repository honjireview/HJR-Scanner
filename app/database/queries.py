# app/database/queries.py (Полная отказоустойчивая версия)
import os
import requests
import logging
import json
from datetime import datetime

log = logging.getLogger(__name__)

# --- Настройка ---
API_BASE_URL = os.getenv("AHOST_API_URL")
API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN")
HEADERS = {'Authorization': f'Bearer {API_SECRET_TOKEN}', 'Content-Type': 'application/json'}

def _send_request(endpoint, payload, log_ref):
    """Внутренняя функция для отправки запросов с защитой от ошибок."""
    if not API_BASE_URL or not API_SECRET_TOKEN:
        log.error(f"Невозможно отправить лог для {log_ref}: переменные API не установлены.")
        return

    # Безопасное формирование URL (убирает лишний слэш)
    full_url = API_BASE_URL.rstrip('/') + f"/{endpoint}"

    try:
        response = requests.post(full_url, data=json.dumps(payload), headers=HEADERS, timeout=15)

        # Бот больше не падает. Он проверяет статус и логирует ошибку, продолжая работу.
        if response.status_code != 200:
            log.error(f"ОШИБКА API при логировании {log_ref}: Статус {response.status_code}. Ответ: {response.text}")
        else:
            log.info(f"Лог для {log_ref} успешно отправлен на API.")

    except requests.exceptions.RequestException as e:
        log.error(f"ОШИБКА СЕТИ при отправке лога для {log_ref}: {e}")

# --- Вспомогательные функции сериализации ---
def serialize_user(user_obj):
    if not user_obj: return None
    return {'id': user_obj.id, 'is_bot': user_obj.is_bot, 'first_name': user_obj.first_name, 'username': user_obj.username}

def serialize_chat(chat_obj):
    if not chat_obj: return None
    return {'id': chat_obj.id, 'type': chat_obj.type, 'title': chat_obj.title}

# --- Основные функции (полная версия) ---
def init_db():
    # Эта функция больше не нужна, так как инициализация происходит при старте,
    # но оставляем ее пустой для совместимости, если где-то есть ее вызовы.
    pass

def log_new_message(message):
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
        'message_id': message.message_id,
        'chat_id': message.chat.id,
        'edit_date': message.edit_date,
        'text': message.text or message.caption
    }
    _send_request("log_edited_message", payload, f"edited_message_id {message.message_id}")

def log_chat_member_update(update):
    old_status, new_status = update.old_chat_member.status, update.new_chat_member.status
    event_type = "unknown"
    if old_status in ['left', 'kicked'] and new_status in ['member', 'administrator', 'creator']:
        event_type = "joined"
    elif old_status in ['member', 'administrator', 'creator'] and new_status in ['left', 'kicked']:
        event_type = "left"
    if event_type == "unknown":
        return

    payload = {
        'date': update.date, 'chat': serialize_chat(update.chat),
        'user': serialize_user(update.new_chat_member.user), 'event_type': event_type,
        'actor_user_id': update.from_user.id
    }
    _send_request("log_chat_member_update", payload, f"chat_member_update for user {update.new_chat_member.user.id}")

def update_editor_list(editors_with_roles: list):
    """
    Полностью перезаписывает список редакторов в БД, сохраняя их статус неактивности.
    """
    conn = get_db_connection()
    if not conn:
        log.error("update_editor_list: нет соединения с БД")
        return

    try:
        with conn.cursor() as cur:
            # 1. Получаем существующих редакторов, чтобы сохранить их статус is_inactive
            cur.execute("SELECT user_id, is_inactive FROM editors")
            existing_statuses = {row[0]: row[1] for row in cur.fetchall()}

            # 2. Очищаем таблицу для полного обновления
            cur.execute("TRUNCATE TABLE editors;")

            if not editors_with_roles:
                log.warning("Список редакторов для обновления пуст. Таблица очищена.")
                conn.commit()
                return

            # 3. Готовим данные для вставки
            editor_data_to_insert = []
            for editor_info in editors_with_roles:
                user = editor_info['user']
                role = editor_info['role']
                user_id = user.id

                # Восстанавливаем старый статус неактивности, если он был
                is_inactive = existing_statuses.get(user_id, False)

                editor_data_to_insert.append((
                    user_id,
                    user.username,
                    user.first_name,
                    role,
                    is_inactive
                ))

            # 4. Вставляем всех редакторов одной командой
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO editors (user_id, username, first_name, role, is_inactive) VALUES %s",
                editor_data_to_insert
            )
            conn.commit()
            log.info(f"Список редакторов в БД обновлен. Загружено {len(editor_data_to_insert)} пользователей.")
    except Exception as e:
        log.error(f"Не удалось обновить список редакторов: {e}", exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()