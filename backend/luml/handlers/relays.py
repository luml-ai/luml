import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import status

from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    NotFoundError,
)
from luml.repositories.relays import RelayRepository
from luml.schemas.permissions import Action, Resource
from luml.schemas.relay import (
    Relay,
    RelayCreate,
    RelayCreateIn,
    RelayKind,
    RelayTokenOut,
    RelayUpdateIn,
)
from luml.settings import config

RELAY_TOKEN_PREFIX = "dfsrelay_"
_BASE_DOMAIN_TAKEN = "A relay with this base domain already exists"


class RelayHandler:
    __relay_repo = RelayRepository(engine)
    __permissions_handler = PermissionsHandler()

    def __init__(
        self,
        secret_key: str = config.AUTH_SECRET_KEY,
        algorithm: Any = hashlib.sha256,  # noqa: ANN401
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm

    @staticmethod
    def generate_token() -> str:
        return f"{RELAY_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"

    def hash_token(self, token: str) -> str:
        return hmac.new(
            self.secret_key.encode(), token.encode(), self.algorithm
        ).hexdigest()

    async def authenticate_token(self, token: str) -> Relay | None:
        return await self.__relay_repo.get_relay_by_token_hash(self.hash_token(token))

    async def list_relays(self, user_id: UUID, organization_id: UUID) -> list[Relay]:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.RELAY, Action.LIST
        )
        return await self.__relay_repo.list_usable_relays(organization_id)

    async def get_relay(
        self, user_id: UUID, organization_id: UUID, relay_id: UUID
    ) -> Relay:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.RELAY, Action.READ
        )
        return await self._get_usable_relay(organization_id, relay_id)

    async def create_relay(
        self, user_id: UUID, organization_id: UUID, relay: RelayCreateIn
    ) -> RelayTokenOut:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.RELAY, Action.CREATE
        )
        token = self.generate_token()
        try:
            created = await self.__relay_repo.create_relay(
                RelayCreate(
                    **relay.model_dump(),
                    organization_id=organization_id,
                    token_hash=self.hash_token(token),
                )
            )
        except DatabaseConstraintError as error:
            raise ApplicationError(
                _BASE_DOMAIN_TAKEN, status.HTTP_409_CONFLICT
            ) from error
        return RelayTokenOut(relay=created, token=token)

    async def update_relay(
        self,
        user_id: UUID,
        organization_id: UUID,
        relay_id: UUID,
        relay: RelayUpdateIn,
    ) -> Relay:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.RELAY, Action.UPDATE
        )
        await self._get_own_relay(organization_id, relay_id)
        try:
            updated = await self.__relay_repo.update_relay(relay_id, relay)
        except DatabaseConstraintError as error:
            raise ApplicationError(
                _BASE_DOMAIN_TAKEN, status.HTTP_409_CONFLICT
            ) from error
        if updated is None:
            raise NotFoundError("Relay not found")
        return updated

    async def rotate_token(
        self, user_id: UUID, organization_id: UUID, relay_id: UUID
    ) -> RelayTokenOut:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.RELAY, Action.UPDATE
        )
        await self._get_own_relay(organization_id, relay_id)
        token = self.generate_token()
        overlap = timedelta(seconds=config.LIVE_SESSION_RELAY_TOKEN_OVERLAP_SECONDS)
        rotated = await self.__relay_repo.rotate_token(
            relay_id, self.hash_token(token), datetime.now(UTC) + overlap
        )
        if rotated is None:
            raise NotFoundError("Relay not found")
        return RelayTokenOut(relay=rotated, token=token)

    async def delete_relay(
        self, user_id: UUID, organization_id: UUID, relay_id: UUID
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.RELAY, Action.DELETE
        )
        await self._get_own_relay(organization_id, relay_id)
        if not await self.__relay_repo.delete_relay(relay_id):
            raise NotFoundError("Relay not found")

    async def _get_usable_relay(self, organization_id: UUID, relay_id: UUID) -> Relay:
        relay = await self.__relay_repo.get_relay(relay_id, organization_id)
        if relay is None:
            raise NotFoundError("Relay not found")
        return relay

    async def _get_own_relay(self, organization_id: UUID, relay_id: UUID) -> Relay:
        relay = await self._get_usable_relay(organization_id, relay_id)
        if relay.kind == RelayKind.MANAGED:
            raise ApplicationError(
                "Managed relays are read-only", status.HTTP_403_FORBIDDEN
            )
        return relay
