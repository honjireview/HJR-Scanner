# app/services.py
import logging
from .database import queries

log = logging.getLogger(__name__)

def sync_editors_list(bot):
    """
    Получает список администраторов из чата редакторов, определяет их роли и обновляет БД.
    Возвращает (количество, сообщение об ошибке или None).
    """
    log.info("--- [SYNC_EDITORS] Начало процесса синхронизации списка редакторов ---")

    # EDITORS_GROUP_ID берется из security.py, где он уже определен
    from .handlers.security import EDITORS_CHAT_ID

    if not EDITORS_CHAT_ID:
        error_msg = "EDITORS_GROUP_ID не задан в переменных окружения."
        log.error(f"[SYNC_EDITORS] ПРОВАЛ: {error_msg}")
        return 0, error_msg

    try:
        log.info(f"[SYNC_EDITORS] Шаг 1: Запрос администраторов для чата {EDITORS_CHAT_ID}...")
        admins = bot.get_chat_administrators(EDITORS_CHAT_ID)
        log.info(f"[SYNC_EDITORS] Шаг 2: Ответ от Telegram API получен. Найдено администраторов: {len(admins)}.")

        editors_with_roles = []
        for admin in admins:
            if admin.user.is_bot:
                continue

            # Определяем роль по кастомному титулу. По умолчанию 'editor'.
            role = 'editor'
            if admin.custom_title and 'исполнитель' in admin.custom_title.lower():
                role = 'executor'
                log.info(f"[SYNC_EDITORS] Обнаружен Исполнитель: {admin.user.first_name} (@{admin.user.username})")

            editors_with_roles.append({
                "user": admin.user,
                "role": role
            })

        log.info(f"[SYNC_EDITORS] Шаг 3: Отфильтрованы боты. Осталось редакторов для записи в БД: {len(editors_with_roles)}.")
        if not editors_with_roles:
            log.warning("[SYNC_EDITORS] В чате не найдено ни одного администратора-человека.")
            return 0, "В чате редакторов не найдено ни одного администратора."

        queries.update_editor_list(editors_with_roles)
        log.info("--- [SYNC_EDITORS] УСПЕХ: Синхронизация завершена. ---")
        return len(editors_with_roles), None

    except Exception as e:
        error_msg = f"Критическая ошибка при вызове Telegram API: {e}"
        log.error(f"[SYNC_EDITORS] КРИТИЧЕСКАЯ ОШИБКА: {error_msg}", exc_info=True)
        return 0, error_msg