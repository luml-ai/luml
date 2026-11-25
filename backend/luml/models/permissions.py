from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from luml.models.base import Base, TimestampMixin
from luml.schemas.orbit import OrbitRole
from luml.schemas.permissions import Action, Resource


class OrganizationRolePermissionsOrm(TimestampMixin, Base):
    __tablename__ = "organization_role_permissions"
    __table_args__ = (
        UniqueConstraint("role", "resource", "action", name="uq_org_perm"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[OrbitRole] = mapped_column(String, nullable=False)
    resource: Mapped[Resource] = mapped_column(String, nullable=False)
    action: Mapped[Action] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return (
            f"OrganizationRolePermissionsOrm("
            f"role={self.role!r}, resource={self.resource!r}, "
            f"action={self.action!r})"
        )


class OrbitRolePermissionsOrm(TimestampMixin, Base):
    __tablename__ = "orbit_role_permissions"
    __table_args__ = (
        UniqueConstraint("role", "resource", "action", name="uq_orbit_perm"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[OrbitRole] = mapped_column(String, nullable=False)
    resource: Mapped[Resource] = mapped_column(String, nullable=False)
    action: Mapped[Action] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return (
            f"OrbitRolePermissionsOrm("
            f"role={self.role!r}, resource={self.resource!r}, "
            f"action={self.action!r})"
        )
