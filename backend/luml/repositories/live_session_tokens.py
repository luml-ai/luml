import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from luml.models import LiveSessionOrm, LiveSessionTokenOrm
from luml.repositories.base import RepositoryBase
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionToken,
    LiveSessionTokenCreate,
    TunnelTokenKind,
)
from luml.settings import config


def hash_tunnel_token(token: str) -> str:
    return hmac.new(
        config.AUTH_SECRET_KEY.encode(), token.encode(), hashlib.sha256
    ).hexdigest()


async def _delete_expired_tokens(session: AsyncSession) -> None:
    await session.execute(
        delete(LiveSessionTokenOrm).where(
            LiveSessionTokenOrm.expires_at < datetime.now(UTC)
        )
    )


class LiveSessionTokenRepository(RepositoryBase):
    async def issue_token(self, data: LiveSessionTokenCreate) -> str:
        """Store a new token and return its plaintext, which exists nowhere else."""
        token = secrets.token_urlsafe(32)
        async with self._get_session() as session:
            await _delete_expired_tokens(session)
            session.add(
                LiveSessionTokenOrm(
                    token_hash=hash_tunnel_token(token), **data.model_dump()
                )
            )
            await session.commit()
        return token

    async def get_token_with_session(
        self, token: str
    ) -> tuple[LiveSessionToken, LiveSession] | None:
        return await self._get_with_session(
            LiveSessionTokenOrm.token_hash == hash_tunnel_token(token)
        )

    async def get_grant_with_session(
        self, grant_id: UUID
    ) -> tuple[LiveSessionToken, LiveSession] | None:
        return await self._get_with_session(LiveSessionTokenOrm.id == grant_id)

    async def _get_with_session(
        self, condition: ColumnElement[bool]
    ) -> tuple[LiveSessionToken, LiveSession] | None:
        async with self._get_session() as session:
            row = (
                await session.execute(
                    select(LiveSessionTokenOrm, LiveSessionOrm)
                    .join(
                        LiveSessionOrm,
                        LiveSessionOrm.id == LiveSessionTokenOrm.session_id,
                    )
                    .where(condition)
                )
            ).one_or_none()
            if row is None:
                return None
            token, live_session = row
            return token.to_live_session_token(), live_session.to_live_session()

    async def launch_view_token(
        self, token_id: UUID, grant_expires_at: datetime
    ) -> LiveSessionToken | None:
        """Turn an unlaunched, unexpired `view` token into a viewer grant.

        One conditional update, so of two concurrent launches exactly one wins.
        """
        now = datetime.now(UTC)
        async with self._get_session() as session:
            launched = await session.scalar(
                update(LiveSessionTokenOrm)
                .where(
                    LiveSessionTokenOrm.id == token_id,
                    LiveSessionTokenOrm.kind == TunnelTokenKind.VIEW,
                    LiveSessionTokenOrm.launched_at.is_(None),
                    LiveSessionTokenOrm.expires_at > now,
                )
                .values(launched_at=now, expires_at=grant_expires_at)
                .returning(LiveSessionTokenOrm)
            )
            grant = launched.to_live_session_token() if launched else None
            await _delete_expired_tokens(session)
            await session.commit()
        return grant
