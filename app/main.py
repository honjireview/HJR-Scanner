# app/main.py
# Этот файл отвечает ТОЛЬКО за запуск. Gunicorn будет использовать его.
from .bot import app, bot, TOKEN # Импортируем 'app' для Gunicorn
from app.setup import initialize_database_schema # <<< ДОБАВЛЯЕМ НОВЫЙ ИМПОРТ
import os

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ПРИ СТАРТЕ ---
initialize_database_schema() # <<< ДОБАВЛЯЕМ ВЫЗОВ ФУНКЦИИ
# ---------------------------------------------

# Этот блок нужен только для локального запуска, на Railway он не используется
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)