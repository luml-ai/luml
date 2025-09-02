from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.infra.encryption import decrypt, encrypt
from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.orbit_secret import (
    OrbitSecret,
    OrbitSecretCreate,
)


class OrbitSecretOrm(TimestampMixin, Base):
    __tablename__ = "orbit_secrets"
    __table_args__ = (UniqueConstraint("orbit_id", "name", name="orbit_secret_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    orbit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orbits.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)

    orbit: Mapped["OrbitOrm"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrbitOrm", back_populates="secrets", lazy="selectin"
    )

    def to_orbit_secret(self) -> OrbitSecret:
        data = OrbitSecret.model_validate(self)
        data.value = decrypt(data.value)
        return data

    @classmethod
    def from_orbit_secret(cls, secret: OrbitSecretCreate) -> "OrbitSecretOrm":
        data = secret.model_dump()
        data["value"] = encrypt(secret.value)
        return cls(**data)
