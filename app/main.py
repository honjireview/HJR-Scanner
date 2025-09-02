# app/main.py
from .bot import app
from app.setup import initialize_database_schema
import os
import logging

log = logging.getLogger(__name__)

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ПРИ СТАРТЕ ---
try:
    initialize_database_schema()
except Exception as e:
    # --- ИЗМЕНЕНИЕ: Бот больше не падает, а выводит критическую ошибку и продолжает работу ---
    log.critical(f"!!! ВНИМАНИЕ: НЕ УДАЛОСЬ ИНИЦИАЛИЗИРОВАТЬ СХЕМУ БД !!!")
    log.critical(f"Бот будет работать, но запись в базу данных НЕВОЗМОЖНА до устранения проблемы.")
    log.critical(f"Ошибка: {e}")
# ---------------------------------------------

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)