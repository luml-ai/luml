from typing import Any
from uuid import UUID

from pydantic import EmailStr

from luml.schemas.orbit import OrbitMemberCreate, OrbitMemberCreateSimple
from luml.schemas.organization import OrganizationInvite, OrgRole


def generate_organization_name(email: EmailStr, full_name: str | None = None) -> str:
    if full_name:
        return f"{full_name.strip().split(' ')[0]}'s organization"
    return f"{str(email).split('@')[0]}'s organization"


def get_members_roles_count(members: list[Any]) -> dict[str, int]:
    members_by_role = {
        str(OrgRole.OWNER): 0,
        str(OrgRole.ADMIN): 0,
        str(OrgRole.MEMBER): 0,
    }

    for member in members:
        if member.role in members_by_role:
            members_by_role[member.role] += 1

    return dict(members_by_role)


def convert_orbit_simple_members(
    orbit_id: UUID, members: list[OrbitMemberCreateSimple]
) -> list[OrbitMemberCreate]:
    return [
        OrbitMemberCreate(orbit_id=orbit_id, user_id=m.user_id, role=m.role)
        for m in members
    ]


def get_invited_by_name(invite: OrganizationInvite | None) -> str:
    if not invite or not (user := invite.invited_by_user):
        return ""
    return user.full_name or user.email or ""


def get_organization_email_name(invite: OrganizationInvite | None) -> str:
    if not invite or not (organization := invite.organization):
        return ""
    return organization.name if organization else ""
