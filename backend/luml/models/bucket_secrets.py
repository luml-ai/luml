import uuid

from sqlalchemy import UUID, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from luml.infra.encryption import decrypt, encrypt
from luml.models.base import Base, TimestampMixin
from luml.schemas.bucket_secrets import (
    BucketSecret,
    BucketSecretCreate,
    S3BucketSecret,
    S3BucketSecretCreate,
    validate_bucket_secret,
)


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
    type: Mapped[str] = mapped_column(String, nullable=False)

    organization: Mapped[OrganizationOrm] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrganizationOrm", back_populates="bucket_secrets", lazy="selectin"
    )
    orbits: Mapped[list[OrbitOrm]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrbitOrm",
        back_populates="bucket_secret",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"BucketSecret(id={self.id!r}, type={self.type}, "
            f"endpoint={self.endpoint!r})"
        )

    def to_bucket_secret(self) -> BucketSecret:
        secret = validate_bucket_secret(self)
        if isinstance(secret, S3BucketSecret):
            if secret.access_key:
                secret.access_key = decrypt(secret.access_key)
            if secret.secret_key:
                secret.secret_key = decrypt(secret.secret_key)
            if secret.session_token:
                secret.session_token = decrypt(secret.session_token)
        return secret

    @classmethod
    def from_bucket_secret(cls, secret: BucketSecretCreate) -> BucketSecretOrm:
        data = secret.model_dump()
        if isinstance(secret, S3BucketSecretCreate):
            if secret.access_key:
                data["access_key"] = encrypt(secret.access_key)
            if secret.secret_key:
                data["secret_key"] = encrypt(secret.secret_key)
            if secret.session_token:
                data["session_token"] = encrypt(secret.session_token)
        return cls(**data)
