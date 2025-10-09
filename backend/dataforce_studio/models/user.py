import uuid

import uuid6
from pydantic import EmailStr, HttpUrl
from sqlalchemy import UUID, Boolean, String, case
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.user import CreateUser, User, UserOut


class UserOrm(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid6.uuid7
    )
    email: Mapped[EmailStr] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_method: Mapped[str] = mapped_column(String, nullable=False)
    photo: Mapped[HttpUrl | None] = mapped_column(String, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
    hashed_api_key: Mapped[str] = mapped_column(String, nullable=True)

    memberships: Mapped[list["OrganizationMemberOrm"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrganizationMemberOrm",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    orbit_memberships: Mapped[list["OrbitMemberOrm"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OrbitMembersOrm",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    has_api_key = column_property(
        case((hashed_api_key.is_not(None), True), else_=False)
    )

    def __repr__(self) -> str:
        return f"User(email={self.email!r}, full_name={self.full_name!r})"

    def to_user(self) -> User:
        return User.model_validate(self)

    def to_public_user(self) -> UserOut:
        return UserOut.model_validate(self)

    @classmethod
    def from_user(cls, user: CreateUser) -> "UserOrm":
        return UserOrm(
            **user.model_dump(),
        )
