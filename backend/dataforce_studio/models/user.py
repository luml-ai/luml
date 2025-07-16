from pydantic import EmailStr, HttpUrl
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.user import CreateUser, User, UserOut


class UserOrm(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[EmailStr] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_method: Mapped[str] = mapped_column(String, nullable=False)
    photo: Mapped[HttpUrl | None] = mapped_column(String, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)

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

    api_keys: Mapped["APIKeyOrm"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "APIKeyOrm",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
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
