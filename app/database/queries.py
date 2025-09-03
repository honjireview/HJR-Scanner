# app/database/queries.py
import os
import psycopg2
import psycopg2.extras
import logging
import json
from datetime import datetime
from sshtunnel import SSHTunnelForwarder

log = logging.getLogger(__name__)
tunnel_server = None

def start_ssh_tunnel():
    global tunnel_server
    if tunnel_server and tunnel_server.is_active:
        return
    log.info("Запуск SSH-туннеля для подключения к БД...")
    try:
        tunnel_server = SSHTunnelForwarder(
            (os.getenv("SSH_HOST"), int(os.getenv("SSH_PORT", 22))),
            ssh_username=os.getenv("SSH_USER"),
            ssh_password=os.getenv("SSH_PASSWORD"),
            remote_bind_address=('127.0.0.1', 5432)
        )
        tunnel_server.start()
        log.info(f"SSH-туннель успешно запущен. Локальный порт: {tunnel_server.local_bind_port}")
    except Exception as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось запустить SSH-туннель. {e}", exc_info=True)
        tunnel_server = None

def get_db_connection():
    if not (tunnel_server and tunnel_server.is_active):
        start_ssh_tunnel()
        if not (tunnel_server and tunnel_server.is_active):
            log.error("Соединение с БД невозможно: SSH-туннель не активен.")
            return None
    try:
        conn = psycopg2.connect(
            host='127.0.0.1',
            port=tunnel_server.local_bind_port,
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            dbname=os.getenv("DB_NAME")
        )
        return conn
    except psycopg2.OperationalError as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к базе данных через туннель. {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn:
        log.error("Инициализация БД пропущена: нет соединения.")
        return
    try:
        with conn.cursor() as cur:
            from .schema import DB_SCHEMA
            log.info("Проверка и инициализация схемы базы данных...")
            cur.execute(DB_SCHEMA)
            conn.commit()
            log.info("Схема базы данных успешно проверена/инициализирована.")
    except Exception as e:
        log.error(f"Ошибка при инициализации схемы БД: {e}")
    finally:
        if conn: conn.close()

def log_new_message(message):
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            # ... (здесь полная логика из Вашего оригинального файла) ...
            initial_history = json.dumps([{"timestamp": message.date, "text": message.text or message.caption}])
            cur.execute(
                "INSERT INTO message_log (message_id, chat_id, text, created_at, edit_history) VALUES (%s, %s, %s, to_timestamp(%s), %s) ON CONFLICT (chat_id, message_id) DO NOTHING;",
                (message.message_id, message.chat.id, message.text or message.caption, message.date, initial_history)
            )
            conn.commit()
    except Exception as e:
        log.error(f"Ошибка при логировании нового сообщения: {e}", exc_info=True)
    finally:
        if conn: conn.close()

def update_editor_list(editors_with_roles: list):
    """Полностью перезаписывает список редакторов в БД, сохраняя их статус неактивности."""
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, is_inactive FROM editors")
            existing_statuses = {row[0]: row[1] for row in cur.fetchall()}
            cur.execute("TRUNCATE TABLE editors;")
            if editors_with_roles:
                editor_data = [(e['user'].id, e['user'].username, e['user'].first_name, e['role'], existing_statuses.get(e['user'].id, False)) for e in editors_with_roles]
                psycopg2.extras.execute_values(cur, "INSERT INTO editors (user_id, username, first_name, role, is_inactive) VALUES %s", editor_data)
            conn.commit()
            log.info(f"Список редакторов в БД обновлен. Загружено {len(editors_with_roles)} пользователей.")
    except Exception as e:
        log.error(f"Не удалось обновить список редакторов: {e}", exc_info=True)
        if conn: conn.rollback()
    finally:
        if conn: conn.close()