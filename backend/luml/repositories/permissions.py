from collections.abc import Sequence

from luml.models.permissions import (
    OrbitRolePermissionsOrm,
    OrganizationRolePermissionsOrm,
)
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.organization import OrgRole
from luml.schemas.permissions import OrbitPermission, OrgPermission


class PermissionsRepository(RepositoryBase, CrudMixin):
    async def get_organization_permissions_by_role(
        self, role: OrgRole
    ) -> Sequence[OrganizationRolePermissionsOrm]:
        async with self._get_session() as session:
            return await self.get_models_where(
                session,
                OrganizationRolePermissionsOrm,
                OrganizationRolePermissionsOrm.role == role,
            )

    async def get_organization_permission(
        self, permission: OrgPermission
    ) -> OrganizationRolePermissionsOrm | None:
        async with self._get_session() as session:
            return await self.get_model_where(
                session,
                OrganizationRolePermissionsOrm,
                OrganizationRolePermissionsOrm.role == permission.role,
                OrganizationRolePermissionsOrm.action == permission.action,
                OrganizationRolePermissionsOrm.resource == permission.resource,
            )

    async def get_orbit_permission(
        self, permission: OrbitPermission
    ) -> OrbitRolePermissionsOrm | None:
        async with self._get_session() as session:
            return await self.get_model_where(
                session,
                OrbitRolePermissionsOrm,
                OrbitRolePermissionsOrm.role == permission.role,
                OrbitRolePermissionsOrm.action == permission.action,
                OrbitRolePermissionsOrm.resource == permission.resource,
            )
