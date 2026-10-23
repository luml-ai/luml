import hashlib
import hmac

import jwt
from fastapi import HTTPException, Request
from jwt.exceptions import InvalidTokenError

from luml.infra.db import engine
from luml.repositories.auth_rate_limits import AuthRateLimitRepository
from luml.settings import config

repository = AuthRateLimitRepository(engine)


async def limit_auth_attempts(
    request: Request, email: str | None = None, *, reset_token: str | None = None
) -> None:
    if reset_token is not None:
        try:
            payload = jwt.decode(
                reset_token, config.AUTH_SECRET_KEY, algorithms=["HS256"]
            )
        except InvalidTokenError:
            payload = {}
        if payload.get("type") == "password_reset" and isinstance(
            payload.get("sub"), str
        ):
            email = payload["sub"]

    # proxy headers are accepted only by the server's trusted proxy configuration
    ip = request.client.host if request.client else "unknown"
    scopes = {f"ip:{ip}": 20}
    if email is not None:
        scopes[f"email:{email.strip().casefold()}"] = 5
    limits = {
        hmac.new(
            config.AUTH_SECRET_KEY.encode(),
            f"{request.url.path}:{scope}".encode(),
            hashlib.sha256,
        ).hexdigest(): limit
        for scope, limit in scopes.items()
    }
    retry_after = await repository.consume(limits)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Too many authentication attempts",
            headers={"Retry-After": str(retry_after)},
        )
