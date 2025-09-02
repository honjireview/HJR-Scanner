# app/database/schema.py

DB_SCHEMA = """
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

            CREATE TABLE IF NOT EXISTS chat_member_log (
                                                           log_id BIGSERIAL PRIMARY KEY,
                                                           event_timestamp TIMESTAMPTZ NOT NULL,
                                                           chat_id BIGINT NOT NULL,
                                                           chat_title TEXT,
                                                           user_id BIGINT NOT NULL,
                                                           user_first_name TEXT,
                                                           user_username TEXT,
                                                           event_type TEXT NOT NULL,
                                                           actor_user_id BIGINT
            ); \
            """