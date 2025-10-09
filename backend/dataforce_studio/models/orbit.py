import uuid
from collections.abc import Sequence

import uuid6
from sqlalchemy import UUID, ForeignKey, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.models.bucket_secrets import BucketSecretOrm
from dataforce_studio.models.collection import CollectionOrm
from dataforce_studio.models.orbit_secret import OrbitSecretOrm
from dataforce_studio.models.organization import OrganizationOrm
from dataforce_studio.models.satellite import SatelliteOrm
from dataforce_studio.models.user import UserOrm
from dataforce_studio.schemas.orbit import Orbit, OrbitDetails, OrbitMember


class OrbitMembersOrm(TimestampMixin, Base):
    __tablename__ = "orbit_members"
    __table_args__ = (UniqueConstraint("orbit_id", "user_id", name="orbit_member"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    orbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orbits.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    user: Mapped["UserOrm"] = relationship(
        "UserOrm", back_populates="orbit_memberships", lazy="selectin"
    )
    orbit: Mapped["OrbitOrm"] = relationship(
        "OrbitOrm", back_populates="members", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"OrbitMember(id={self.id!r}, user_id={self.user_id!r})"

    def to_orbit_member(self) -> OrbitMember:
        return OrbitMember.model_validate(self)

    @classmethod
    def to_orbit_members_list(
        cls, members: Sequence["OrbitMembersOrm"]
    ) -> list[OrbitMember]:
        return [OrbitMember.model_validate(member) for member in members]


class OrbitOrm(TimestampMixin, Base):
    __tablename__ = "orbits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    bucket_secret_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bucket_secrets.id", ondelete="CASCADE"),
        nullable=False,
    )

    members: Mapped[list["OrbitMembersOrm"]] = relationship(
        back_populates="orbit", cascade="all, delete, delete-orphan"
    )

    collections: Mapped[list["CollectionOrm"]] = relationship(  # noqa: F821
        back_populates="orbit", cascade="all, delete, delete-orphan"
    )

    satellites: Mapped[list["SatelliteOrm"]] = relationship(
        back_populates="orbit", cascade="all, delete, delete-orphan"
    )

    deployments: Mapped[list["DeploymentOrm"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="orbit", cascade="all, delete, delete-orphan"
    )

    secrets: Mapped[list["OrbitSecretOrm"]] = relationship(
        back_populates="orbit", cascade="all, delete, delete-orphan"
    )

    bucket_secret: Mapped["BucketSecretOrm"] = relationship(
        "BucketSecretOrm",
        back_populates="orbits",
        lazy="selectin",
    )

    organization: Mapped["OrganizationOrm"] = relationship(
        "OrganizationOrm",
        back_populates="orbits",
        lazy="selectin",
    )

    total_members = column_property(
        select(func.count(OrbitMembersOrm.id))
        .where(OrbitMembersOrm.orbit_id == id)
        .correlate_except(OrbitMembersOrm)
        .scalar_subquery()
    )

    total_collections = column_property(
        select(func.count(CollectionOrm.id))
        .where(CollectionOrm.orbit_id == id)
        .correlate_except(CollectionOrm)
        .scalar_subquery()
    )

    def __repr__(self) -> str:
        return f"Orbit(id={self.id!r})"

    def to_orbit(self) -> Orbit:
        return Orbit.model_validate(self)

    def to_orbit_details(self) -> OrbitDetails:
        return OrbitDetails.model_validate(self)

    @classmethod
    def to_orbits_list(cls, orbits: Sequence["OrbitOrm"]) -> list[Orbit]:
        return [Orbit.model_validate(orbit) for orbit in orbits]
