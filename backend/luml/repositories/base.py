from collections.abc import Sequence
from operator import gt, lt
from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import asc, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from luml.models import Base
from luml.schemas.general import SortOrder

TOrm = TypeVar("TOrm", bound=Base)
TPydantic = TypeVar("TPydantic", bound=BaseModel)


class RepositoryBase:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def _get_session(self) -> AsyncSession:
        return AsyncSession(self._engine, expire_on_commit=True)


class CrudMixin:
    @staticmethod
    async def create_model(
        session: AsyncSession, orm_class: type[TOrm], data: TPydantic
    ) -> TOrm:
        db_obj = orm_class(**data.model_dump())
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    @staticmethod
    async def create_models(
        session: AsyncSession,
        orm_class: type[TOrm],
        data_list: list[TPydantic],
    ) -> list[TOrm]:
        db_objects = [orm_class(**item.model_dump()) for item in data_list]
        session.add_all(db_objects)
        await session.flush()
        await session.commit()
        for obj in db_objects:
            await session.refresh(obj)
        return db_objects

    @staticmethod
    async def update_model_where(
        session: AsyncSession,
        orm_class: type[TOrm],
        data: TPydantic,
        *where_conditions: Any,  # noqa: ANN401
    ) -> TOrm | None:
        result = await session.execute(select(orm_class).where(*where_conditions))
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return None

        fields_to_update = data.model_dump(exclude_unset=True, exclude={"id"})
        if not fields_to_update:
            return db_obj

        for field, value in fields_to_update.items():
            setattr(db_obj, field, value)

        await session.commit()
        await session.refresh(db_obj)

        return db_obj

    async def update_model(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        data: TPydantic,
    ) -> TOrm | None:
        return await self.update_model_where(
            session,
            orm_class,
            data,
            orm_class.id == data.id,  # type: ignore[attr-defined]
        )

    @staticmethod
    async def delete_model(
        session: AsyncSession,
        orm_class: type[TOrm],
        obj_id: UUID,
    ) -> None:
        result = await session.execute(select(orm_class).where(orm_class.id == obj_id))  # type: ignore[attr-defined]
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

    @staticmethod
    async def get_model(
        session: AsyncSession,
        orm_class: type[TOrm],
        obj_id: UUID,
        options: list[Any] | None = None,  # noqa: ANN401
        use_unique: bool = False,
    ) -> TOrm | None:
        result = await session.execute(
            select(orm_class)
            .where(orm_class.id == obj_id)  # type: ignore[attr-defined]
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
    def _get_sort_col(
        orm_class: type[TOrm],
        sort_by: str | None = None,
    ) -> Any:  # noqa: ANN401
        if sort_by is None:
            return orm_class.created_at  # type: ignore[attr-defined]
        return getattr(orm_class, sort_by, orm_class.created_at)  # type: ignore[attr-defined]

    async def get_models_with_pagination(
        self,
        session: AsyncSession,
        orm_class: type[TOrm],
        *where_conditions: Any,  # noqa: ANN401
        cursor_id: UUID | None = None,
        cursor_value: Any | None = None,  # noqa: ANN401
        sort_by: str | None = None,
        order: SortOrder,
        limit: int = 100,
        options: list[Any] | None = None,  # noqa: ANN401
        join_condition: tuple[Any, ...] | None = None,  # noqa: ANN401
        select_fields: list[Any] | None = None,  # noqa: ANN401
        use_unique: bool = False,
    ) -> Sequence[Any]:  # noqa: ANN401
        stmt = select(*(select_fields or [orm_class]))

        if join_condition:
            stmt = stmt.join(*join_condition)

        if where_conditions:
            stmt = stmt.where(*where_conditions)

        sort_column = self._get_sort_col(orm_class, sort_by)

        if cursor_id and cursor_value:
            op = lt if order == SortOrder.DESC else gt
            stmt = stmt.where(
                op(sort_column, cursor_value)
                | ((sort_column == cursor_value) & op(orm_class.id, cursor_id))  # type: ignore[attr-defined]
            )

        sort_func = desc if order == SortOrder.DESC else asc
        stmt = stmt.order_by(
            sort_func(sort_column),
            sort_func(orm_class.id),  # type: ignore[attr-defined]
        )

        stmt = stmt.options(*(options or [])).limit(limit + 1)
        result = await session.execute(stmt)

        if use_unique:
            return result.unique().scalars().all()
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

    @staticmethod
    def collect_unique_values_from_array_column(
        query_result: Sequence[Any],  # noqa: ANN401
    ) -> list[str]:
        unique_values = set()
        for row in query_result:
            value_list = row[0]
            if value_list:
                unique_values.update(value_list)
        return sorted(unique_values)
