# utils/logging_config.py — улучшенное логирование с контекстом
import logging
import sys
from typing import Optional
from contextvars import ContextVar

# Context variable для хранения контекста запроса
_request_context: ContextVar[dict] = ContextVar("request_context", default={})


class ContextualFormatter(logging.Formatter):
    """Форматтер логов с добавлением контекста."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Добавляем контекст из context variable
        context = _request_context.get({})
        if context:
            record.user_id = context.get("user_id", "-")
            record.action = context.get("action", "-")
        else:
            record.user_id = "-"
            record.action = "-"
        
        return super().format(record)


def setup_logging(level: int = logging.INFO) -> None:
    """Настройка структурированного логирования."""
    formatter = ContextualFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - [user:%(user_id)s] [action:%(action)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)


def set_log_context(user_id: Optional[int] = None, action: Optional[str] = None) -> None:
    """Установить контекст для логирования."""
    context = {}
    if user_id is not None:
        context["user_id"] = user_id
    if action is not None:
        context["action"] = action
    _request_context.set(context)


def clear_log_context() -> None:
    """Очистить контекст логирования."""
    _request_context.set({})
