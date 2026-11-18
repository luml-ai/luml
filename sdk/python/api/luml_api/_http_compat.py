from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module

import httpx2

from luml_api._exceptions import APIConnectionError


@contextmanager
def compatible_http_errors() -> Iterator[None]:
    try:
        yield
    except httpx2.HTTPError as error:
        error_type = type(error)
        bases: tuple[type[Exception], ...] = (error_type,)
        try:
            legacy = import_module("httpx")
        except ModuleNotFoundError as import_error:
            if import_error.name != "httpx":
                raise
        else:
            bases += (getattr(legacy, error_type.__name__),)
        if isinstance(error, httpx2.RequestError):
            bases += (APIConnectionError,)
        error_class: type[httpx2.HTTPError] = type(
            error_type.__name__, bases, {"__module__": __name__}
        )
        compatible = error_class.__new__(error_class)
        Exception.__init__(compatible, *error.args)
        compatible.__dict__.update(error.__dict__)
        if isinstance(compatible, APIConnectionError):
            compatible.message = str(error)
            compatible.body = None
        raise compatible from error
