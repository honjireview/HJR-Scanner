# Procfile
# Команда запуска Gunicorn теперь указывает на объект 'app' внутри 'app/main.py'
web: gunicorn --bind 0.0.0.0:${PORT} app.main:app --log-file -