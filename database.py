# database.py
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
        return conn
    except psycopg2.OperationalError as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к базе данных. {e}")
        return None

def init_db():
    """
    Проверяет и создает таблицу message_log, если она не существует.
    Это делает бота самодостаточным.
    """
    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            log.info("Проверка и инициализация схемы базы данных...")
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS message_log (
                                                                   internal_id BIGSERIAL PRIMARY KEY,
                                                                   message_id BIGINT NOT NULL,
                                                                   chat_id BIGINT NOT NULL,
                                                                   chat_type TEXT,
                                                                   chat_title TEXT,
                                                                   topic_id BIGINT,
                                                                   topic_name TEXT,
                                                                   author_user_id BIGINT,
                                                                   author_username TEXT,
                                                                   author_first_name TEXT,
                                                                   author_is_bot BOOLEAN,
                                                                   text TEXT,
                                                                   content_type TEXT,
                                                                   file_id TEXT,
                                                                   reply_to_message_id BIGINT,
                                                                   forward_from_chat_id BIGINT,
                                                                   forward_from_message_id BIGINT,
                                                                   created_at TIMESTAMPTZ,
                                                                   last_edited_at TIMESTAMPTZ,
                                                                   edit_history JSONB,
                                                                   logged_at TIMESTAMPTZ,
                                                                   UNIQUE (chat_id, message_id)
                            );
                        """)
            conn.commit()
            log.info("Схема базы данных успешно проверена/инициализирована.")
    except Exception as e:
        log.error(f"Ошибка при инициализации схемы БД: {e}")
    finally:
        conn.close()

def log_new_message(message):
    """
    Извлекает всю возможную информацию из нового сообщения и сохраняет ее в БД.
    """
    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            # Извлечение данных о топике
            topic_id, topic_name = (message.message_thread_id, "General") if message.is_topic_message else (None, None)
            if message.reply_to_message and message.reply_to_message.forum_topic_created:
                topic_name = message.reply_to_message.forum_topic_created.name

            # Извлечение данных о пересылке
            fwd_chat_id, fwd_msg_id = (message.forward_from_chat.id, message.forward_from_message_id) if message.forward_from_chat else (None, None)

            # История изменений
            initial_history = json.dumps([{
                "timestamp": message.date,
                "text": message.text or message.caption
            }])

            cur.execute(
                """
                INSERT INTO message_log (
                    message_id, chat_id, chat_type, chat_title, topic_id, topic_name,
                    author_user_id, author_username, author_first_name, author_is_bot,
                    text, content_type, file_id, reply_to_message_id,
                    forward_from_chat_id, forward_from_message_id,
                    created_at, last_edited_at, edit_history, logged_at
                ) VALUES (
                             %s, %s, %s, %s, %s, %s,
                             %s, %s, %s, %s,
                             %s, %s, %s, %s,
                             %s, %s,
                             %s, %s, %s, %s
                         )
                    ON CONFLICT (chat_id, message_id) DO NOTHING;
                """,
                (
                    message.message_id, message.chat.id, message.chat.type, message.chat.title, topic_id, topic_name,
                    message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.is_bot,
                    message.text or message.caption, message.content_type, getattr(message, message.content_type, [{}])[0].get('file_id') if hasattr(message, message.content_type) and isinstance(getattr(message, message.content_type), list) and getattr(message, message.content_type) else None,
                    message.reply_to_message.message_id if message.reply_to_message else None,
                    fwd_chat_id, fwd_msg_id,
                    datetime.fromtimestamp(message.date), None, initial_history, datetime.utcnow()
                )
            )
            conn.commit()
            log.info(f"Сообщение {message.message_id} из чата {message.chat.id} успешно залогировано.")
    except Exception as e:
        log.error(f"Ошибка при логировании нового сообщения {message.message_id}: {e}")
    finally:
        conn.close()

def log_edited_message(message):
    """
    Находит существующую запись о сообщении и добавляет новую версию в историю изменений.
    """
    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            new_edit_entry = json.dumps({
                "timestamp": message.edit_date,
                "text": message.text or message.caption
            })

            # jsonb_append в PostgreSQL 14+
            cur.execute(
                """
                UPDATE message_log
                SET
                    text = %s,
                    last_edited_at = %s,
                    edit_history = edit_history || %s::jsonb
                WHERE
                    chat_id = %s AND message_id = %s;
                """,
                (
                    message.text or message.caption,
                    datetime.fromtimestamp(message.edit_date),
                    new_edit_entry,
                    message.chat.id, message.message_id
                )
            )
            conn.commit()
            log.info(f"Изменение сообщения {message.message_id} из чата {message.chat.id} успешно залогировано.")
    except Exception as e:
        log.error(f"Ошибка при логировании изменения сообщения {message.message_id}: {e}")
    finally:
        conn.close()