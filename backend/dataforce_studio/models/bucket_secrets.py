import uuid

from sqlalchemy import UUID, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.infra.encryption import decrypt, encrypt
from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.bucket_secrets import BucketSecret, BucketSecretCreate


class BucketSecretOrm(TimestampMixin, Base):
    __tablename__ = "bucket_secrets"
    __table_args__ = (
        UniqueConstraint(
            "endpoint", "bucket_name", "organization_id", name="uq_bucket_endpoint"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    bucket_name: Mapped[str] = mapped_column(String, nullable=False)
    access_key: Mapped[str | None] = mapped_column(String, nullable=True)
    secret_key: Mapped[str | None] = mapped_column(String, nullable=True)
    session_token: Mapped[str | None] = mapped_column(String, nullable=True)
    secure: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    cert_check: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    organization: Mapped[OrganizationOrm] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrganizationOrm", back_populates="bucket_secrets", lazy="selectin"
    )
    orbits: Mapped[list[OrbitOrm]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrbitOrm",
        back_populates="bucket_secret",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"BucketSecret(id={self.id!r}, endpoint={self.endpoint!r})"

    def to_bucket_secret(self) -> BucketSecret:
        data = BucketSecret.model_validate(self)
        if data.access_key:
            data.access_key = decrypt(data.access_key)
        if data.secret_key:
            data.secret_key = decrypt(data.secret_key)
        if data.session_token:
            data.session_token = decrypt(data.session_token)
        return data

    @classmethod
    def from_bucket_secret(cls, secret: BucketSecretCreate) -> BucketSecretOrm:
        data = secret.model_dump()
        if secret.access_key:
            data["access_key"] = encrypt(secret.access_key)
        if secret.secret_key:
            data["secret_key"] = encrypt(secret.secret_key)
        if secret.session_token:
            data["session_token"] = encrypt(secret.session_token)
        return cls(**data)
