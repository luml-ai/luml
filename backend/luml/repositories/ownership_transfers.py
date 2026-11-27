from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import select, update

from luml.infra.exceptions import (
    ApplicationError,
    InsufficientPermissionsError,
    OrganizationMemberNotFoundError,
)
from luml.models import OrganizationMemberOrm, OrganizationOrm, OwnershipTransferOrm
from luml.repositories.base import RepositoryBase
from luml.schemas.organization import OrgRole, OwnershipTransfer


class OwnershipTransferRepository(RepositoryBase):
    async def create(
        self, organization_id: UUID, sender_id: UUID, member_id: UUID
    ) -> OwnershipTransfer:
        async with self._get_session() as session, session.begin():
            organization = await session.scalar(
                select(OrganizationOrm)
                .where(OrganizationOrm.id == organization_id)
                .with_for_update()
            )
            sender = await session.scalar(
                select(OrganizationMemberOrm).where(
                    OrganizationMemberOrm.organization_id == organization_id,
                    OrganizationMemberOrm.user_id == sender_id,
                )
            )
            if organization is None or sender is None or sender.role != OrgRole.OWNER:
                raise InsufficientPermissionsError(
                    "Only Organization Owner can transfer ownership."
                )
            recipient = await session.scalar(
                select(OrganizationMemberOrm).where(
                    OrganizationMemberOrm.organization_id == organization_id,
                    OrganizationMemberOrm.id == member_id,
                )
            )
            if recipient is None:
                raise OrganizationMemberNotFoundError()
            if recipient.user_id == sender_id or recipient.role == OrgRole.OWNER:
                raise ApplicationError("Choose another member as the new owner.")
            now = datetime.now(UTC)
            await session.execute(
                update(OwnershipTransferOrm)
                .where(
                    OwnershipTransferOrm.organization_id == organization_id,
                    OwnershipTransferOrm.status == "pending",
                    OwnershipTransferOrm.expires_at <= now,
                )
                .values(status="expired")
            )
            pending = await session.scalar(
                select(OwnershipTransferOrm.id).where(
                    OwnershipTransferOrm.organization_id == organization_id,
                    OwnershipTransferOrm.status == "pending",
                )
            )
            if pending:
                raise ApplicationError(
                    "A transfer is already pending. Please cancel it first.", 409
                )
            request = OwnershipTransferOrm(
                organization_id=organization_id,
                sender_id=sender_id,
                recipient_member_id=member_id,
                recipient_id=recipient.user_id,
                organization_name=organization.name,
                sender_email=sender.user.email,
                recipient_email=recipient.user.email,
                created_at=now,
                expires_at=now + timedelta(days=7),
            )
            session.add(request)
            await session.flush()
            return OwnershipTransfer.model_validate(request)

    async def pending(
        self, organization_id: UUID, user_id: UUID
    ) -> OwnershipTransfer | None:
        async with self._get_session() as session:
            role = await session.scalar(
                select(OrganizationMemberOrm.role).where(
                    OrganizationMemberOrm.organization_id == organization_id,
                    OrganizationMemberOrm.user_id == user_id,
                )
            )
            if role != OrgRole.OWNER:
                raise InsufficientPermissionsError()
            request = await session.scalar(
                select(OwnershipTransferOrm).where(
                    OwnershipTransferOrm.organization_id == organization_id,
                    OwnershipTransferOrm.status == "pending",
                    OwnershipTransferOrm.expires_at > datetime.now(UTC),
                )
            )
            return OwnershipTransfer.model_validate(request) if request else None

    async def list_received(self, user_id: UUID) -> list[OwnershipTransfer]:
        async with self._get_session() as session:
            requests = await session.scalars(
                select(OwnershipTransferOrm)
                .where(
                    OwnershipTransferOrm.recipient_id == user_id,
                    OwnershipTransferOrm.status == "pending",
                    OwnershipTransferOrm.expires_at > datetime.now(UTC),
                )
                .order_by(OwnershipTransferOrm.created_at)
            )
            return [OwnershipTransfer.model_validate(request) for request in requests]

    async def resolve(
        self,
        organization_id: UUID,
        request_id: UUID,
        user_id: UUID,
        action: Literal["accepted", "declined", "cancelled"],
    ) -> OwnershipTransfer:
        outcome = None
        async with self._get_session() as session, session.begin():
            await session.scalar(
                select(OrganizationOrm.id)
                .where(OrganizationOrm.id == organization_id)
                .with_for_update()
            )
            request = await session.scalar(
                select(OwnershipTransferOrm)
                .where(
                    OwnershipTransferOrm.id == request_id,
                    OwnershipTransferOrm.organization_id == organization_id,
                )
                .with_for_update()
            )
            if request is not None and request.status == "pending":
                actor = (
                    request.sender_id if action == "cancelled" else request.recipient_id
                )
                if user_id != actor:
                    raise InsufficientPermissionsError()
                sender = await session.scalar(
                    select(OrganizationMemberOrm)
                    .where(
                        OrganizationMemberOrm.organization_id == organization_id,
                        OrganizationMemberOrm.user_id == request.sender_id,
                    )
                    .with_for_update()
                )
                recipient = await session.scalar(
                    select(OrganizationMemberOrm)
                    .where(OrganizationMemberOrm.id == request.recipient_member_id)
                    .with_for_update()
                )
                if request.expires_at <= datetime.now(UTC):
                    request.status = "expired"
                elif (
                    sender is None
                    or sender.role != OrgRole.OWNER
                    or recipient is None
                    or recipient.role == OrgRole.OWNER
                ):
                    request.status = "cancelled"
                else:
                    if action == "accepted":
                        sender.role = OrgRole.ADMIN
                        recipient.role = OrgRole.OWNER
                    request.status = action
                    outcome = OwnershipTransfer.model_validate(request)
        if outcome is None:
            raise ApplicationError(
                "Ownership transfer request is no longer pending.", 409
            )
        return outcome

    async def consume_notices(
        self, organization_id: UUID, user_id: UUID
    ) -> list[OwnershipTransfer]:
        async with self._get_session() as session, session.begin():
            requests = await session.scalars(
                update(OwnershipTransferOrm)
                .where(
                    OwnershipTransferOrm.organization_id == organization_id,
                    OwnershipTransferOrm.sender_id == user_id,
                    OwnershipTransferOrm.status.in_(["accepted", "declined"]),
                    OwnershipTransferOrm.notice_read.is_(False),
                )
                .values(notice_read=True)
                .returning(OwnershipTransferOrm)
            )
            return [OwnershipTransfer.model_validate(request) for request in requests]
