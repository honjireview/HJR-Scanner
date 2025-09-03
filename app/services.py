# app/services.py
import logging
from .database import queries
log = logging.getLogger(__name__)

def sync_editors_list(bot):
    from .handlers.security import EDITORS_CHAT_ID
    if not EDITORS_CHAT_ID:
        return 0, "EDITORS_GROUP_ID не задан."
    try:
        admins = bot.get_chat_administrators(EDITORS_CHAT_ID)
        editors = [{"user": a.user, "role": 'executor' if a.custom_title and 'исполнитель' in a.custom_title.lower() else 'editor'} for a in admins if not a.user.is_bot]
        queries.update_editor_list(editors)
        return len(editors), None
    except Exception as e:
        return 0, str(e)