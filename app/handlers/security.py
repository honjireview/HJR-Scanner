# app/handlers/security.py
# Обработчики, отвечающие за безопасность и управление участниками.
import os
import time
import logging
from ..database import queries

log = logging.getLogger(__name__)

# --- 1. Загружаем переменные окружения ---
EDITORS_CHAT_ID = os.getenv("EDITORS_GROUP_ID")
OTHER_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "").split(',')

if EDITORS_CHAT_ID:
    FULL_WHITELIST = [chat_id for chat_id in OTHER_CHAT_IDS if chat_id] + [EDITORS_CHAT_ID]
else:
    FULL_WHITELIST = [chat_id for chat_id in OTHER_CHAT_IDS if chat_id]
    log.warning("Переменная EDITORS_GROUP_ID не задана! Функция автокика не будет работать.")

log.info(f"Загружен ID редакторского чата: {EDITORS_CHAT_ID}")
log.info(f"Загружен список остальных чатов/каналов: {OTHER_CHAT_IDS}")
log.info(f"Полный белый список для сканирования: {FULL_WHITELIST}")


def is_chat_allowed(chat_id):
    """Проверяет, находится ли ID чата в полном белом списке."""
    return str(chat_id) in FULL_WHITELIST

def handle_editor_exit(bot, update):
    """Логика, запускающаяся при выходе редактора из главного чата."""
    user_who_left = update.new_chat_member.user
    log.info(f"Зафиксирован выход редактора {user_who_left.id} из редакторского чата. ЗАПУСКАЮ ПРОЦЕДУРУ ИСКЛЮЧЕНИЯ.")

    kicked_from, failed_to_kick = [], []
    for chat_id_str in OTHER_CHAT_IDS:
        if not chat_id_str: continue
        try:
            bot.ban_chat_member(chat_id_str, user_who_left.id)
            bot.unban_chat_member(chat_id_str, user_who_left.id, only_if_banned=True)
            chat_info = bot.get_chat(chat_id_str)
            kicked_from.append(chat_info.title or chat_id_str)
            time.sleep(1)
        except Exception as e:
            log.error(f"Не удалось исключить пользователя {user_who_left.id} из {chat_id_str}. Ошибка: {e}")
            failed_to_kick.append(chat_id_str)

    report_message = f"**СИСТЕМА БЕЗОПАСНОСТИ**\n\nПользователь **{user_who_left.first_name}** (@{user_who_left.username or 'N/A'}, ID: `{user_who_left.id}`) покинул редакторский чат.\n\nОн был автоматически исключен из всех пространств проекта."
    if kicked_from: report_message += "\n\n**Успешно исключен из:**\n- " + "\n- ".join(kicked_from)
    if failed_to_kick: report_message += f"\n\n**Не удалось исключить из (проверьте права бота):**\n- " + "\n- ".join(failed_to_kick)

    try:
        bot.send_message(EDITORS_CHAT_ID, report_message, parse_mode="Markdown")
    except Exception as e:
        log.error(f"Не удалось отправить отчет о безопасности. Ошибка: {e}")


def register_security_handlers(bot):
    """Регистрирует обработчики для безопасности."""

    @bot.chat_member_handler()
    def handle_chat_member_updates(update):
        if not is_chat_allowed(update.chat.id):
            return

        queries.log_chat_member_update(update)

        if EDITORS_CHAT_ID:
            is_exit_event = update.new_chat_member.status in ['left', 'kicked']
            is_editors_chat = str(update.chat.id) == EDITORS_CHAT_ID
            if is_exit_event and is_editors_chat:
                handle_editor_exit(bot, update)