from typing import Literal
from uuid import UUID

from luml.handlers.emails import EmailHandler
from luml.infra.db import engine
from luml.repositories.ownership_transfers import OwnershipTransferRepository
from luml.schemas.organization import OwnershipTransfer


class OwnershipTransferHandler:
    repository = OwnershipTransferRepository(engine)
    email_handler = EmailHandler()

    async def create(
        self, organization_id: UUID, user_id: UUID, member_id: UUID
    ) -> OwnershipTransfer:
        request = await self.repository.create(organization_id, user_id, member_id)
        try:
            await self.email_handler.send_ownership_transfer_email(
                request, result=False
            )
        except Exception:
            request.email_delivery_failed = True
        return request

    async def resolve(
        self,
        organization_id: UUID,
        request_id: UUID,
        user_id: UUID,
        action: Literal["accepted", "declined", "cancelled"],
    ) -> OwnershipTransfer:
        request = await self.repository.resolve(
            organization_id, request_id, user_id, action
        )
        if action != "cancelled":
            try:
                await self.email_handler.send_ownership_transfer_email(
                    request, result=True
                )
            except Exception:
                request.email_delivery_failed = True
        return request
