import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


def log_success(message: str | None = None) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:  # noqa ANN401
            result = func(*args, **kwargs)
            log_message = message or f"{func.__name__} completed successfully"
            logger.info(log_message)
            return result

        return wrapper

    return decorator
