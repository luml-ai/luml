import asyncio
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import jwt

from luml_tunnel.signing import ALGORITHM, KIND_CLAIM, SESSION_CLAIM
from luml_tunnel.tokens import TokenKind, TokenRejectedError, TunnelClaims

logger = logging.getLogger(__name__)

_REQUIRED_CLAIMS = ["iss", "aud", "sub", "exp", "jti", SESSION_CLAIM, KIND_CLAIM]


class IssuerKeys:
    """The issuer's public keys, read from an http(s) address or a local JWKS file.

    Keys are cached. An unknown key identifier triggers a new read, at most once per
    `min_refresh_interval`, because key identifiers come from untrusted tokens.
    """

    def __init__(
        self,
        location: str,
        http_client: httpx.AsyncClient | None = None,
        min_refresh_interval: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._location = location
        self._http_client = http_client
        self._min_refresh_interval = min_refresh_interval
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._loaded_at: float | None = None
        self._lock = asyncio.Lock()

    async def get(self, key_id: str) -> jwt.PyJWK | None:
        if key_id in self._keys:
            return self._keys[key_id]
        async with self._lock:
            if key_id not in self._keys and self._may_refresh():
                await self._refresh()
        return self._keys.get(key_id)

    def _may_refresh(self) -> bool:
        if self._loaded_at is None:
            return True
        return self._clock() - self._loaded_at >= self._min_refresh_interval

    async def _refresh(self) -> None:
        self._loaded_at = self._clock()
        try:
            document = await self._read()
        except (OSError, ValueError, httpx.HTTPError) as error:
            logger.warning("Could not read issuer keys from %s: %s", self._location, error)
            return
        self._keys = _parse_key_set(document)

    async def _read(self) -> Any:  # noqa: ANN401
        if not self._location.startswith(("http://", "https://")):
            return json.loads(Path(self._location).read_text())
        if self._http_client is not None:
            response = await self._http_client.get(self._location)
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._location)
        response.raise_for_status()
        return response.json()


def _parse_key_set(document: Any) -> dict[str, jwt.PyJWK]:  # noqa: ANN401
    keys: dict[str, jwt.PyJWK] = {}
    entries = document.get("keys", []) if isinstance(document, dict) else []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("kid"), str):
            continue
        try:
            keys[entry["kid"]] = jwt.PyJWK(entry, algorithm=ALGORITHM)
        except jwt.PyJWTError as error:
            logger.warning("Skipping issuer key %s: %s", entry["kid"], error)
    return keys


class JwksTokenVerifier:
    def __init__(self, keys: IssuerKeys, issuer: str, relay: str) -> None:
        self._keys = keys
        self._issuer = issuer
        self._relay = relay

    async def verify(self, token: str, kind: TokenKind, session: str | None = None) -> TunnelClaims:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise TokenRejectedError("malformed token") from error
        key_id = header.get("kid")
        if not isinstance(key_id, str):
            raise TokenRejectedError("token has no key identifier")
        key = await self._keys.get(key_id)
        if key is None:
            raise TokenRejectedError("token is signed by an unknown key")
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[ALGORITHM],
                issuer=self._issuer,
                audience=self._relay,
                options={"require": _REQUIRED_CLAIMS, "strict_aud": True},
            )
        except jwt.PyJWTError as error:
            raise TokenRejectedError(str(error)) from error

        if payload[KIND_CLAIM] != kind:
            raise TokenRejectedError(f"expected a {kind} token")
        if session is not None and payload[SESSION_CLAIM] != session:
            raise TokenRejectedError("token is for another session")
        if not all(isinstance(payload[claim], str) for claim in ("sub", "jti", SESSION_CLAIM)):
            raise TokenRejectedError("token claims have the wrong type")
        return TunnelClaims(
            issuer=payload["iss"],
            relay=self._relay,
            session=payload[SESSION_CLAIM],
            kind=kind,
            user=payload["sub"],
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
            token_id=payload["jti"],
        )
