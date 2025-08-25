# handlers.py
import logging
import database
import os
import time

log = logging.getLogger(__name__)

# Загружаем белый список и ID редакторской из переменных окружения
ALLOWED_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "").split(',')
EDITORS_CHAT_ID = "-1002063604198" # Константа для ключевого чата
log.info(f"Загружен белый список чатов: {ALLOWED_CHAT_IDS}")
log.info(f"Редакторский чат определен как: {EDITORS_CHAT_ID}")

def is_chat_allowed(chat_id):
    """Проверяет, находится ли ID чата в белом списке."""
    return str(chat_id) in ALLOWED_CHAT_IDS

def handle_editor_exit(bot, update):
    """
    Основная логика, запускающаяся при выходе редактора из главного чата.
    Исключает пользователя из всех чатов в белом списке.
    """
    user_who_left = update.new_chat_member.user
    log.info(f"Зафиксирован выход редактора {user_who_left.id} (@{user_who_left.username}) из редакторского чата. Запускаю процедуру исключения.")

    kicked_from_chats = []
    failed_to_kick_chats = []

    # Проходим по всем разрешенным чатам
    for chat_id_str in ALLOWED_CHAT_IDS:
        if chat_id_str == EDITORS_CHAT_ID:
            continue # Пропускаем сам редакторский чат

        try:
            # Используем ban_chat_member, так как это API-метод для кика
            bot.ban_chat_member(chat_id_str, user_who_left.id)
            # Сразу разбаниваем, чтобы он мог вернуться, если его снова добавят в редакторы
            bot.unban_chat_member(chat_id_str, user_who_left.id)

            # Получаем название чата для отчета
            chat_info = bot.get_chat(chat_id_str)
            kicked_from_chats.append(chat_info.title or chat_id_str)
            log.info(f"Пользователь {user_who_left.id} успешно исключен из чата {chat_id_str}.")
            time.sleep(1) # Небольшая задержка, чтобы не превышать лимиты API
        except Exception as e:
            log.error(f"Не удалось исключить пользователя {user_who_left.id} из чата {chat_id_str}. Ошибка: {e}")
            failed_to_kick_chats.append(chat_id_str)

    # Формируем и отправляем отчет в редакторский чат
    report_message = (
        f"**СИСТЕМА БЕЗОПАСНОСТИ**\n\n"
        f"Пользователь **{user_who_left.first_name}** (@{user_who_left.username or 'N/A'}, ID: `{user_who_left.id}`) покинул редакторский чат.\n\n"
        f"В целях безопасности он был автоматически исключен из всех пространств проекта Honji Review."
    )
    if kicked_from_chats:
        report_message += "\n\n**Успешно исключен из:**\n- " + "\n- ".join(kicked_from_chats)
    if failed_to_kick_chats:
        report_message += f"\n\n**Не удалось исключить из (проверьте права бота):**\n- " + "\n- ".join(failed_to_kick_chats)

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
        if not is_chat_allowed(message.chat.id):
            log.warning(f"Получено сообщение из незарегистрированного чата: {message.chat.id}. Игнорируется.")
            return
        log.debug(f"Получено новое сообщение {message.message_id} от @{message.from_user.username}")
        database.log_new_message(message)

    @bot.edited_message_handler(func=lambda message: True)
    def handle_edited_message(message):
        if not is_chat_allowed(message.chat.id):
            log.warning(f"Получено изменение сообщения из незарегистрированного чата: {message.chat.id}. Игнорируется.")
            return
        log.debug(f"Получено изменение сообщения {message.message_id} от @{message.from_user.username}")
        database.log_edited_message(message)

    @bot.chat_member_handler()
    def handle_chat_member_updates(update):
        if not is_chat_allowed(update.chat.id):
            log.warning(f"Получено событие от участника из незарегистрированного чата: {update.chat.id}. Игнорируется.")
            return

        # Сначала логируем любое событие входа/выхода
        database.log_chat_member_update(update)

        # Затем проверяем, является ли это событие выходом из редакторского чата
        is_exit_event = update.new_chat_member.status in ['left', 'kicked']
        is_editors_chat = str(update.chat.id) == EDITORS_CHAT_ID

        if is_exit_event and is_editors_chat:
            # Если да, запускаем процедуру автокика
            handle_editor_exit(bot, update)

    log.info("Обработчики сообщений и участников успешно зарегистрированы.")