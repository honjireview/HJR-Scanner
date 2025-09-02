# app/setup.py
import os
import requests
import logging
import json
from .database.schema import DB_SCHEMA # Берем схему из соседнего файла

log = logging.getLogger(__name__)

def initialize_database_schema():
    """
    Отправляет SQL-схему на API для выполнения.
    Запускается один раз при старте приложения.
    """
    API_BASE_URL = os.getenv("AHOST_API_URL")
    API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN")

    if not API_BASE_URL or not API_SECRET_TOKEN:
        log.critical("Переменные API не заданы! Пропускаю настройку схемы БД.")
        # В рабочей среде это должно останавливать запуск
        raise ValueError("API_URL and API_SECRET_TOKEN must be set")

    endpoint = f"{API_BASE_URL}/execute_schema"
    headers = {
        'Authorization': f'Bearer {API_SECRET_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {'sql': DB_SCHEMA}

    log.info(f"Отправляю команду на создание/проверку таблиц на {endpoint}...")

    try:
        response = requests.post(endpoint, data=json.dumps(payload), headers=headers, timeout=30)

        if response.status_code == 200:
            log.info("УСПЕХ: Сервер API подтвердил, что база данных готова.")
        else:
            log.error(f"ОШИБКА: API-сервер не смог выполнить команду. Статус: {response.status_code}. Ответ: {response.text}")
            raise RuntimeError("Failed to initialize database schema via API")

    except requests.exceptions.RequestException as e:
        log.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось отправить команду на API. Ошибка: {e}")
        raise RuntimeError("Could not connect to API to initialize schema")