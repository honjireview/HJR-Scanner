# app/database/schema.py
DB_SCHEMA = """
            CREATE TABLE IF NOT EXISTS message_log (...); -- Ваш существующий код
            CREATE TABLE IF NOT EXISTS chat_member_log (...); -- Ваш существующий код
            CREATE TABLE IF NOT EXISTS editors (
                                                   user_id BIGINT PRIMARY KEY,
                                                   username TEXT,
                                                   first_name TEXT,
                                                   role TEXT NOT NULL DEFAULT 'editor',
                                                   is_inactive BOOLEAN DEFAULT FALSE,
                                                   added_at TIMESTAMPTZ DEFAULT NOW()
                ); \
            """