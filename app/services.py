# app/services.py
import os
import logging
import requests
import json

log = logging.getLogger(__name__)

def sync_editors_list(bot):
    log.info("--- [SYNC_EDITORS] Начало процесса синхронизации ---")
    from .handlers.security import EDITORS_CHAT_ID
    API_BASE_URL = os.getenv("AHOST_API_URL")
    API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN")

    if not all([API_BASE_URL, API_SECRET_TOKEN, EDITORS_CHAT_ID]):
        return 0, "Ключевые переменные окружения не заданы."

    try:
        admins = bot.get_chat_administrators(EDITORS_CHAT_ID)
        editors = [{"user": {"id": a.user.id, "username": a.user.username, "first_name": a.user.first_name}, "role": 'executor' if a.custom_title and 'исполнитель' in a.custom_title.lower() else 'editor'} for a in admins if not a.user.is_bot]

        endpoint = API_BASE_URL.rstrip('/') + "/update_editors"
        headers = {'Authorization': f'Bearer {API_SECRET_TOKEN}', 'Content-Type': 'application/json'}
        payload = {'editors': editors}
        response = requests.post(endpoint, data=json.dumps(payload), headers=headers, timeout=20)

        if response.status_code != 200:
            raise RuntimeError(f"API ответил с ошибкой {response.status_code}: {response.text}")

        return len(editors), None
    except Exception as e:
        log.error(f"Критическая ошибка при синхронизации: {e}", exc_info=True)
        return 0, str(e)