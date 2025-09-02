# app/handlers/__init__.py
from .logging import register_logging_handlers
from .security import register_security_handlers

def register_all_handlers(bot):
    """
    Главная функция для регистрации всех обработчиков в приложении.
    """
    register_logging_handlers(bot)
    register_security_handlers(bot)