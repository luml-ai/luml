import uuid

from sqlalchemy import UUID, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from luml.infra.encryption import decrypt, encrypt
from luml.models.base import Base, TimestampMixin
from luml.schemas.orbit_secret import OrbitSecret, OrbitSecretCreate


class OrbitSecretOrm(TimestampMixin, Base):
    __tablename__ = "orbit_secrets"
    __table_args__ = (UniqueConstraint("orbit_id", "name", name="orbit_secret_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    orbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orbits.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)

    orbit: Mapped[OrbitOrm] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrbitOrm", back_populates="secrets", lazy="selectin"
    )

    def to_orbit_secret(self) -> OrbitSecret:
        data = OrbitSecret.model_validate(self)
        data.value = decrypt(data.value)
        return data

    @classmethod
    def from_orbit_secret(cls, secret: OrbitSecretCreate) -> OrbitSecretOrm:
        data = secret.model_dump()
        data["value"] = encrypt(secret.value)
        return cls(**data)
