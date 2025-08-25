# handlers.py
import logging
import database
import os
import time

log = logging.getLogger(__name__)

# --- 1. Загружаем переменные окружения ---
EDITORS_CHAT_ID = os.getenv("EDITORS_GROUP_ID")
OTHER_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "").split(',')

# Создаем полный белый список для общей проверки доступа
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
    allowed = str(chat_id) in FULL_WHITELIST
    log.debug(f"Проверка белого списка для chat_id '{chat_id}': {'РАЗРЕШЕНО' if allowed else 'ЗАПРЕЩЕНО'}")
    return allowed

def handle_editor_exit(bot, update):
    """
    Основная логика, запускающаяся при выходе редактора из главного чата.
    Исключает пользователя из всех остальных чатов проекта.
    """
    user_who_left = update.new_chat_member.user
    log.info(f"Зафиксирован выход редактора {user_who_left.id} (@{user_who_left.username}) из редакторского чата. ЗАПУСКАЮ ПРОЦЕДУРУ ИСКЛЮЧЕНИЯ.")

    kicked_from = []
    failed_to_kick = []

    # Проходим по списку остальных чатов и каналов
    for chat_id_str in OTHER_CHAT_IDS:
        if not chat_id_str: continue

        try:
            log.debug(f"Попытка исключить {user_who_left.id} из чата/канала {chat_id_str}...")
            # ban_chat_member - это универсальный API-метод и для кика из групп, и для бана в каналах
            bot.ban_chat_member(chat_id_str, user_who_left.id)
            # Сразу разбаниваем, чтобы он мог вернуться, если его снова добавят в редакторы
            bot.unban_chat_member(chat_id_str, user_who_left.id, only_if_banned=True)

            chat_info = bot.get_chat(chat_id_str)
            kicked_from.append(chat_info.title or chat_id_str)
            log.info(f"Пользователь {user_who_left.id} успешно исключен из '{chat_info.title}'.")
            time.sleep(1) # Небольшая задержка, чтобы не превышать лимиты API
        except Exception as e:
            log.error(f"Не удалось исключить пользователя {user_who_left.id} из {chat_id_str}. Ошибка: {e}")
            failed_to_kick.append(chat_id_str)

    # Формируем и отправляем отчет в редакторский чат
    report_message = (
        f"**СИСТЕМА БЕЗОПАСНОСТИ**\n\n"
        f"Пользователь **{user_who_left.first_name}** (@{user_who_left.username or 'N/A'}, ID: `{user_who_left.id}`) покинул редакторский чат.\n\n"
        f"В целях безопасности он был автоматически исключен из всех пространств проекта Honji Review."
    )
    if kicked_from:
        report_message += "\n\n**Успешно исключен из:**\n- " + "\n- ".join(kicked_from)
    if failed_to_kick:
        report_message += f"\n\n**Не удалось исключить из (проверьте права бота):**\n- " + "\n- ".join(failed_to_kick)

    try:
        bot.send_message(EDITORS_CHAT_ID, report_message, parse_mode="Markdown")
        log.info("Отчет о безопасности отправлен в редакторский чат.")
    except Exception as e:
        log.error(f"Не удалось отправить отчет о безопасности в редакторский чат. Ошибка: {e}")


def register_handlers(bot):
    """
    Регистрирует все обработчики сообщений для бота.
    """
    @bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'sticker', 'voice', 'audio', 'location', 'contact'])
    def handle_new_message(message):
        log.debug(f"Сработал handle_new_message для сообщения {message.message_id} в чате {message.chat.id}")
        if not is_chat_allowed(message.chat.id):
            return
        database.log_new_message(message)

    @bot.edited_message_handler(func=lambda message: True)
    def handle_edited_message(message):
        log.debug(f"Сработал handle_edited_message для сообщения {message.message_id} в чате {message.chat.id}")
        if not is_chat_allowed(message.chat.id):
            return
        database.log_edited_message(message)

    @bot.chat_member_handler()
    def handle_chat_member_updates(update):
        log.debug(f"Сработал handle_chat_member_updates для чата {update.chat.id} (событие от @{update.from_user.username})")
        if not is_chat_allowed(update.chat.id):
            return

        # Шаг 1: Логируем абсолютно любое событие входа/выхода из разрешенного чата
        database.log_chat_member_update(update)

        # Шаг 2: Проверяем, является ли это событие выходом из КЛЮЧЕВОГО редакторского чата
        if EDITORS_CHAT_ID:
            is_exit_event = update.new_chat_member.status in ['left', 'kicked']
            is_editors_chat = str(update.chat.id) == EDITORS_CHAT_ID

            if is_exit_event and is_editors_chat:
                # Если да, запускаем протокол безопасности
                handle_editor_exit(bot, update)

    log.info("Обработчики сообщений и участников успешно зарегистрированы.")