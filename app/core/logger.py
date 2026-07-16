import logging
import sys
from typing import Any

import structlog
from structlog.types import FilteringBoundLogger
from app.core.config import settings


def configure_logging(log_level: str = settings.LOG_LEVEL, json_logs: bool = False) -> None:
    """Настройка structlog: log_level, json_logs"""
    log_level_value = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level_value,
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    """Получить экземпляр логгера"""
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Привязать контекстные переменные ко всем последующим логам"""
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Удалить контекстные переменные"""
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Очистить все контекстные переменные"""
    structlog.contextvars.clear_contextvars()
