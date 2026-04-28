from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from luml_prisma.models.base import Base, _uuid_pk


class RepositoryOrm(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid_pk)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
