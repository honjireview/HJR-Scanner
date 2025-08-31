# app/database/queries.py
import os
import psycopg2
import psycopg2.extras
import logging
import json
from datetime import datetime
from sshtunnel import SSHTunnelForwarder
from paramiko import RSAKey # <<< ДОБАВЛЯЕМ НОВЫЙ ИМПОРТ
import io # <<< ДОБАВЛЯЕМ НОВЫЙ ИМПОРТ

log = logging.getLogger(__name__)

# --- Глобальная переменная для хранения нашего туннеля ---
tunnel_server = None

def start_ssh_tunnel():
    """Инициализирует и запускает SSH-туннель с использованием ключа, защищенного паролем."""
    global tunnel_server
    try:
        if tunnel_server and tunnel_server.is_active:
            log.info("SSH-туннель уже активен.")
            return

        log.info("Запуск SSH-туннеля с использованием зашифрованного ключа...")

        ssh_host = os.getenv("SSH_HOST")
        ssh_user = os.getenv("SSH_USER")
        ssh_key_string = os.getenv("SSH_PRIVATE_KEY")
        ssh_key_password = os.getenv("SSH_KEY_PASSWORD") # <<< ПОЛУЧАЕМ ПАРОЛЬ ОТ КЛЮЧА

        db_host_remote = '127.0.0.1'
        db_port_remote = 5432

        if not all([ssh_host, ssh_user, ssh_key_string, ssh_key_password]):
            log.critical("КРИТИЧЕСКАЯ ОШИБКА: SSH-переменные (SSH_HOST, SSH_USER, SSH_PRIVATE_KEY, SSH_KEY_PASSWORD) не заданы!")
            return

        pkey_file = io.StringIO(ssh_key_string)
        # <<< ПЕРЕДАЕМ ПАРОЛЬ ДЛЯ РАСШИФРОВКИ КЛЮЧА
        private_key = RSAKey.from_private_key(pkey_file, password=ssh_key_password)
        log.info("SSH-ключ успешно расшифрован и подготовлен.")

        tunnel_server = SSHTunnelForwarder(
            (ssh_host, 22),
            ssh_username=ssh_user,
            ssh_pkey=private_key,
            remote_bind_address=(db_host_remote, db_port_remote)
        )

        tunnel_server.start()
        log.info(f"SSH-туннель успешно запущен. Локальный порт: {tunnel_server.local_bind_port}")

    except Exception as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось запустить SSH-туннель. {e}", exc_info=True)
        tunnel_server = None

def get_db_connection():
    """Устанавливает и возвращает соединение с БД через SSH-туннель."""
    global tunnel_server

    if not (tunnel_server and tunnel_server.is_active):
        start_ssh_tunnel() # Попытаемся перезапустить туннель, если он неактивен
        if not (tunnel_server and tunnel_server.is_active):
            log.error("Соединение с БД невозможно: SSH-туннель не активен.")
            return None

    try:
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_name = os.getenv("DB_NAME")

        if not all([db_user, db_password, db_name]):
            log.critical("КРИТИЧЕСКАЯ ОШИБКА: Переменные БД (DB_USER, DB_PASSWORD, DB_NAME) не заданы!")
            return None

        conn = psycopg2.connect(
            host='127.0.0.1',
            port=tunnel_server.local_bind_port,
            user=db_user,
            password=db_password,
            dbname=db_name
        )
        log.debug("Подключение к БД через туннель установлено")
        return conn
    except psycopg2.OperationalError as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к базе данных через туннель. {e}")
        return None

# --- Остальные функции (log_new_message, init_db и т.д.) остаются без изменений ---
def init_db():
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


def log_new_message(message):
    conn = get_db_connection()
    if not conn:
        log.error("log_new_message: нет соединения с БД")
        return

    try:
        with conn.cursor() as cur:
            topic_id = None
            topic_name = None
            if hasattr(message, 'is_topic_message') and message.is_topic_message:
                topic_id = message.message_thread_id
                if (message.reply_to_message and
                        hasattr(message.reply_to_message, 'forum_topic_created') and
                        message.reply_to_message.forum_topic_created):
                    topic_name = message.reply_to_message.forum_topic_created.name
                else:
                    topic_name = "General"

            fwd_chat_id, fwd_msg_id = (message.forward_from_chat.id, message.forward_from_message_id) if message.forward_from_chat else (None, None)

            file_id = None
            if message.content_type in ['photo', 'video', 'document', 'audio', 'voice', 'sticker']:
                media = getattr(message, message.content_type)
                if isinstance(media, list):
                    file_id = media[-1].file_id
                elif hasattr(media, 'file_id'):
                    file_id = media.file_id

            initial_history = json.dumps([{
                "timestamp": message.date,
                "text": message.text or message.caption
            }])

            author = message.from_user
            author_id = author.id if author else None
            author_username = author.username if author else None
            author_first_name = author.first_name if author else (message.author_signature if hasattr(message, 'author_signature') else None)
            author_is_bot = author.is_bot if author else None

            cur.execute(
                """
                INSERT INTO message_log (
                    message_id, chat_id, chat_type, chat_title, topic_id, topic_name,
                    author_user_id, author_username, author_first_name, author_is_bot,
                    text, content_type, file_id, reply_to_message_id,
                    forward_from_chat_id, forward_from_message_id,
                    created_at, last_edited_at, edit_history, logged_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chat_id, message_id) DO NOTHING;
                """,
                (
                    message.message_id, message.chat.id, message.chat.type, message.chat.title, topic_id, topic_name,
                    author_id, author_username, author_first_name, author_is_bot,
                    message.text or message.caption, message.content_type, file_id,
                    message.reply_to_message.message_id if message.reply_to_message else None,
                    fwd_chat_id, fwd_msg_id,
                    datetime.fromtimestamp(message.date), None, initial_history, datetime.utcnow()
                )
            )
            conn.commit()
            log.info(f"Сообщение/пост {message.message_id} из чата {message.chat.id} успешно залогировано.")
    except Exception as e:
        log.error(f"Ошибка при логировании нового сообщения {message.message_id}: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

def log_edited_message(message):
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
            log.info(f"Изменение сообщения/поста {message.message_id} из чата {message.chat.id} успешно залогировано.")
    except Exception as e:
        log.error(f"Ошибка при логировании изменения сообщения {message.message_id}: {e}", exc_info=True)
    finally:
        if conn: conn.close()

def log_chat_member_update(update):
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