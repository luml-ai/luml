from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class TokenKind(StrEnum):
    EXPOSE = "expose"
    VIEW = "view"


@dataclass(frozen=True)
class TunnelClaims:
    issuer: str
    relay: str
    session: str
    kind: TokenKind
    user: str
    expires_at: datetime
    token_id: str


class TokenRejectedError(Exception):
    pass


class TokenVerifier(Protocol):
    async def verify(self, token: str, kind: TokenKind, session: str | None = None) -> TunnelClaims:
        """Return the claims of a token that fits, or raise TokenRejectedError.

        `session` is None when the session is taken from the token itself, as when an
        agent connects to the relay's base domain.
        """
        ...
