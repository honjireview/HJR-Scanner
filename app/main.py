# app/main.py
from .bot import app
from .database.queries import init_db
import os

# Инициализируем БД при старте приложения
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)