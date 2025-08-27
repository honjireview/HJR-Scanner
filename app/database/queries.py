# app/database/queries.py
# Весь код из старого database.py перенесен сюда без изменений.
import os
import psycopg2
import psycopg2.extras
import logging
import json
from datetime import datetime

log = logging.getLogger(__name__)

def get_db_connection():
    """Устанавливает и возвращает соединение с базой данных."""
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        log.debug("Подключение к БД установлено")
        return conn
    except psycopg2.OperationalError as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к базе данных. {e}")
        return None

def init_db():
    """
    Проверяет и создает все необходимые таблицы, если они не существуют.
    """
    conn = get_db_connection()
    if not conn:
        log.error("Инициализация БД пропущена: нет соединения")
        return

    try:
        with conn.cursor() as cur:
            log.info("Проверка и инициализация схемы базы данных...")
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS message_log (
                                                                   internal_id BIGSERIAL PRIMARY KEY, message_id BIGINT NOT NULL, chat_id BIGINT NOT NULL,
                                                                   chat_type TEXT, chat_title TEXT, topic_id BIGINT, topic_name TEXT, author_user_id BIGINT,
                                                                   author_username TEXT, author_first_name TEXT, author_is_bot BOOLEAN, text TEXT,
                                                                   content_type TEXT, file_id TEXT, reply_to_message_id BIGINT, forward_from_chat_id BIGINT,
                                                                   forward_from_message_id BIGINT, created_at TIMESTAMPTZ, last_edited_at TIMESTAMPTZ,
                                                                   edit_history JSONB, logged_at TIMESTAMPTZ, UNIQUE (chat_id, message_id)
                            );
                        """)
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS chat_member_log (
                                                                       log_id BIGSERIAL PRIMARY KEY, event_timestamp TIMESTAMPTZ NOT NULL, chat_id BIGINT NOT NULL,
                                                                       chat_title TEXT, user_id BIGINT NOT NULL, user_first_name TEXT, user_username TEXT,
                                                                       event_type TEXT NOT NULL, actor_user_id BIGINT
                        );
                        """)
            conn.commit()
            log.info("Схема базы данных успешно проверена/инициализирована.")
    except Exception as e:
        log.error(f"Ошибка при инициализации схемы БД: {e}")
    finally:
        if conn:
            conn.close()
            log.debug("Соединение с БД закрыто после init_db()")

# ... (остальные функции из вашего database.py: log_chat_member_update, log_new_message, log_edited_message) ...
# Я их здесь сократил для краткости, но вы должны перенести их полностью.

def log_chat_member_update(update):
    """Логирует событие входа, выхода или изменения статуса участника чата."""
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            chat, user, actor_id = update.chat, update.new_chat_member.user, update.from_user.id
            old_status, new_status = update.old_chat_member.status, update.new_chat_member.status
            event_type = "unknown"
            if old_status in ['left', 'kicked'] and new_status in ['member', 'administrator', 'creator']: event_type = "joined"
            elif old_status in ['member', 'administrator', 'creator'] and new_status in ['left', 'kicked']: event_type = "left"
            if event_type not in ["joined", "left"]: return
            cur.execute(
                "INSERT INTO chat_member_log (event_timestamp, chat_id, chat_title, user_id, user_first_name, user_username, event_type, actor_user_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);",
                (datetime.fromtimestamp(update.date), chat.id, chat.title, user.id, user.first_name, user.username, event_type, actor_id)
            )
            conn.commit()
    except Exception as e:
        log.error(f"Ошибка при логировании события с участником чата: {e}")
    finally:
        if conn: conn.close()

def log_new_message(message):
    """Извлекает всю возможную информацию из нового сообщения и сохраняет ее в БД."""
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            topic_id, topic_name = (message.message_thread_id, "General") if message.is_topic_message else (None, None)
            if hasattr(message, 'reply_to_message') and message.reply_to_message and hasattr(message.reply_to_message, 'forum_topic_created'):
                topic_name = message.reply_to_message.forum_topic_created.name
            fwd_chat_id, fwd_msg_id = (message.forward_from_chat.id, message.forward_from_message_id) if message.forward_from_chat else (None, None)
            file_id = None
            if message.content_type in ['photo', 'video', 'document', 'audio', 'voice', 'sticker']:
                media = getattr(message, message.content_type)
                file_id = media[-1].file_id if isinstance(media, list) else (media.file_id if hasattr(media, 'file_id') else None)
            initial_history = json.dumps([{"timestamp": message.date, "text": message.text or message.caption}])
            cur.execute(
                "INSERT INTO message_log (message_id, chat_id, chat_type, chat_title, topic_id, topic_name, author_user_id, author_username, author_first_name, author_is_bot, text, content_type, file_id, reply_to_message_id, forward_from_chat_id, forward_from_message_id, created_at, last_edited_at, edit_history, logged_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (chat_id, message_id) DO NOTHING;",
                (message.message_id, message.chat.id, message.chat.type, message.chat.title, topic_id, topic_name, message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.is_bot, message.text or message.caption, message.content_type, file_id, message.reply_to_message.message_id if message.reply_to_message else None, fwd_chat_id, fwd_msg_id, datetime.fromtimestamp(message.date), None, initial_history, datetime.utcnow())
            )
            conn.commit()
    except Exception as e:
        log.error(f"Ошибка при логировании нового сообщения {message.message_id}: {e}")
    finally:
        if conn: conn.close()

def log_edited_message(message):
    """Находит существующую запись о сообщении и добавляет новую версию в историю изменений."""
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            new_edit_entry = json.dumps({"timestamp": message.edit_date, "text": message.text or message.caption})
            cur.execute(
                "UPDATE message_log SET text = %s, last_edited_at = %s, edit_history = edit_history || %s::jsonb WHERE chat_id = %s AND message_id = %s;",
                (message.text or message.caption, datetime.fromtimestamp(message.edit_date), new_edit_entry, message.chat.id, message.message_id)
            )
            conn.commit()
    except Exception as e:
        log.error(f"Ошибка при логировании изменения сообщения {message.message_id}: {e}")
    finally:
        if conn: conn.close()