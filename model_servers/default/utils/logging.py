import logging
from collections.abc import Callable
from functools import wraps

logger = logging.getLogger(__name__)


def log_success[**P, R](
    message: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            result = func(*args, **kwargs)
            log_message = (
                message
                or f"{getattr(func, '__name__', type(func).__name__)} completed successfully"
            )
            logger.info(log_message)
            return result

        return wrapper

    return decorator
