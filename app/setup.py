# app/setup.py
import os
import requests
import logging
import json
from .database.schema import DB_SCHEMA

log = logging.getLogger(__name__)

def initialize_database_schema():
    API_BASE_URL = os.getenv("AHOST_API_URL")
    API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN")

    if not API_BASE_URL or not API_SECRET_TOKEN:
        raise ValueError("Переменные API (AHOST_API_URL, API_SECRET_TOKEN) не заданы!")

    # --- ИЗМЕНЕНИЕ: URL теперь собирается безопасно, убирая лишние слэши ---
    endpoint = API_BASE_URL.rstrip('/') + "/execute_schema"

    headers = {'Authorization': f'Bearer {API_SECRET_TOKEN}', 'Content-Type': 'application/json'}
    payload = {'sql': DB_SCHEMA}

    log.info(f"Отправляю команду на создание/проверку таблиц на {endpoint}...")

    try:
        response = requests.post(endpoint, data=json.dumps(payload), headers=headers, timeout=30)

        if response.status_code == 200:
            log.info("УСПЕХ: Сервер API подтвердил, что база данных готова.")
        else:
            # --- ИЗМЕНЕНИЕ: Вызываем исключение, которое будет поймано в main.py ---
            raise RuntimeError(f"API ответил с ошибкой {response.status_code}. Ответ: {response.text}")

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Не удалось отправить команду на API. Ошибка: {e}")