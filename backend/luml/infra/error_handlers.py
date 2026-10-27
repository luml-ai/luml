import math

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _json_safe_float(value: float) -> float | str:
    return value if math.isfinite(value) else str(value)


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Answer 422 even when the rejected input itself is not JSON encodable.

    ``NaN`` and ``Infinity`` pass the JSON parser; the validation error echoes
    the offending value in ``input``, and the default handler fails to encode
    it, turning a client error into a 500.
    """
    errors = exc.errors()
    if "bucket-secrets" in request.url.path.split("/"):
        errors = [
            {
                "loc": error["loc"],
                "type": error["type"],
                "msg": (
                    "Invalid bucket secret type"
                    if error["type"] == "union_tag_invalid"
                    else error["msg"]
                ),
            }
            for error in errors
        ]
    return JSONResponse(
        status_code=422,
        content={
            "detail": jsonable_encoder(errors, custom_encoder={float: _json_safe_float})
        },
    )
