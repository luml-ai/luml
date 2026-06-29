"""Single chokepoint for "luml can't represent this MLflow concept" situations.

Governed by ``LUML_MLFLOW_ON_UNSUPPORTED`` (``warn`` default → log + return the
caller's default; ``raise`` → raise ``MlflowException``). Used by the tracking
store for unimplemented ``AbstractStore`` methods, by the tag mapper when a
caller writes a reserved ``luml.*`` key, and by the tracing layer when a span
arrives without an owning run — so the strictness is controlled in one place.
"""

import logging
from typing import Any

from mlflow.exceptions import MlflowException

from luml_mlflow.config import get_settings

logger = logging.getLogger(__name__)


def unsupported(
    message: str,
    *,
    default: Any = None,  # noqa: ANN401
    exception_factory: type[Exception] = MlflowException,
) -> Any:  # noqa: ANN401
    """Honor ``LUML_MLFLOW_ON_UNSUPPORTED``.

    ``warn`` → log + return ``default``. ``raise`` → raise
    ``exception_factory(message)``.
    """
    mode = get_settings().LUML_MLFLOW_ON_UNSUPPORTED
    if mode == "raise":
        raise exception_factory(message)
    logger.warning("[luml-mlflow] unsupported: %s", message)
    return default
