from collections.abc import Sequence
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from dataforce_studio.models import Base
from dataforce_studio.schemas.base import ShortUUID

TOrm = TypeVar("TOrm", bound=Base)
TPydantic = TypeVar("TPydantic", bound=BaseModel)


class RepositoryBase:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def _get_session(self) -> AsyncSession:
        return AsyncSession(self._engine, expire_on_commit=True)


class CrudMixin:
    @staticmethod
    def _convert_shortuuid_value(value: Any) -> Any:  # noqa: ANN401
        if type(value) is ShortUUID:
            return value.to_uuid()
        if isinstance(value, str) and ShortUUID._is_valid_short_uuid(value):
            return ShortUUID(value).to_uuid()
        return value

    def _convert_ids(self, model_data: TPydantic) -> dict[str, Any]:  # noqa: ANN401
        data_dict = model_data.model_dump(mode="python")
        for key, value in data_dict.items():
            data_dict[key] = self._convert_shortuuid_value(value)
        return data_dict

    def _convert_ids_list(
        self, orm_class: type[TOrm], data_list: list[TPydantic]
    ) -> list[TOrm]:  # noqa: ANN401
        db_objects = []
        for item in data_list:
            model_data = self._convert_ids(item)
            db_objects.append(orm_class(**model_data))
        return db_objects

    async def create_model(
        self, session: AsyncSession, orm_class: type[TOrm], data: TPydantic
    ) -> TOrm:
        model_data = self._convert_ids(data)
        db_obj = orm_class(**model_data)
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def create_models(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        data_list: list[TPydantic],
    ) -> list[TOrm]:
        db_objects = self._convert_ids_list(orm_class, data_list)

        session.add_all(db_objects)
        await session.flush()
        await session.commit()
        for obj in db_objects:
            await session.refresh(obj)
        return db_objects

    async def update_model_where(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        data: TPydantic,
        *where_conditions: Any,  # noqa: ANN401
    ) -> TOrm | None:
        result = await session.execute(select(orm_class).where(*where_conditions))
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return None

        fields_to_update = data.model_dump(
            exclude_unset=True, exclude={"id"}, mode="python"
        )
        if not fields_to_update:
            return db_obj

        for field, value in fields_to_update.items():
            setattr(db_obj, field, self._convert_shortuuid_value(value))

        await session.commit()
        await session.refresh(db_obj)

        return db_obj

    async def update_model(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        data: TPydantic,
    ) -> TOrm | None:
        data_id = data.id  # type: ignore[attr-defined]

        return await self.update_model_where(
            session,
            orm_class,
            data,
            orm_class.id == self._convert_shortuuid_value(data_id),  # type: ignore[attr-defined]
        )

    async def delete_model(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        obj_id: ShortUUID,
    ) -> None:
        result = await session.execute(
            select(orm_class).where(
                orm_class.id == self._convert_shortuuid_value(obj_id)  # type: ignore[attr-defined]
            )
        )
        db_obj = result.scalar_one_or_none()

        if db_obj:
            await session.delete(db_obj)
            await session.commit()

    @staticmethod
    async def delete_model_where(
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions: Any,  # noqa: ANN401
    ) -> None:
        result = await session.execute(select(orm_class).where(*where_conditions))
        obj = result.scalar_one_or_none()

        if obj:
            await session.delete(obj)
            await session.commit()

    @staticmethod
    async def delete_models_where(
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions: Any,  # noqa: ANN401
    ) -> None:
        await session.execute(delete(orm_class).where(*where_conditions))
        await session.commit()

    @staticmethod
    async def get_model_where(
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions: Any,  # noqa: ANN401
        options: list[Any] | None = None,  # noqa: ANN401
    ) -> TOrm | None:
        result = await session.execute(
            select(orm_class).where(*where_conditions).options(*(options or []))
        )

        return result.scalar_one_or_none()

    async def get_model(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        obj_id: ShortUUID,
        options: list[Any] | None = None,  # noqa: ANN401
        use_unique: bool = False,
    ) -> TOrm | None:
        result = await session.execute(
            select(orm_class)
            .where(orm_class.id == self._convert_shortuuid_value(obj_id))  # type: ignore[attr-defined]
            .options(*(options or []))
        )

        if use_unique:
            return result.unique().scalar_one_or_none()
        return result.scalar_one_or_none()

    @staticmethod
    async def get_models_where(
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions: Any,  # noqa: ANN401
        options: list[Any] | None = None,  # noqa: ANN401
        order_by: list[Any] | None = None,  # noqa: ANN401
        join_condition: tuple[Any, ...] | None = None,  # noqa: ANN401
        select_fields: list[Any] | None = None,  # noqa: ANN401
        use_unique: bool = False,
    ) -> Sequence[Any]:  # noqa: ANN401
        stmt = select(*(select_fields or [orm_class]))

        if join_condition:
            stmt = stmt.join(*join_condition)

        stmt = (
            stmt.where(*where_conditions)
            .options(*(options or []))
            .order_by(*(order_by or []))
        )

        result = await session.execute(stmt)

        if use_unique:
            return result.unique().all()
        return result.scalars().all()

    @staticmethod
    async def get_model_count(
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions: Any,  # noqa: ANN401
    ) -> int:
        result = await session.execute(
            select(func.count()).select_from(orm_class).where(*where_conditions)
        )
        return result.scalar() or 0
