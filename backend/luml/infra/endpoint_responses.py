from typing import Any

endpoint_responses: dict[int | str, dict[str, Any]] = {
    401: {
        "description": "Authentication error",
        "content": {
            "application/json": {"example": {"detail": "Authentication error"}}
        },
    },
    403: {
        "description": "Not enough rights for performing action for the resource",
        "content": {"application/json": {"example": {"detail": "Not enough rights"}}},
    },
}
