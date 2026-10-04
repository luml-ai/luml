from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

from sqlalchemy.ext.asyncio import AsyncSession

COLLABORATOR_PACKAGES = ("luml.repositories.", "luml.handlers.")


class CollaboratorMocks[H](SimpleNamespace):
    handler: H
    session: AsyncSession
    transaction_errors: list[BaseException]


def _is_collaborator(value: object) -> bool:
    return type(value).__module__.startswith(COLLABORATOR_PACKAGES)


def _collaborators(handler_class: type) -> dict[str, object]:
    collaborators: dict[str, object] = {}
    for owner in reversed(handler_class.__mro__):
        prefix = f"_{owner.__name__}__"
        for attribute, value in vars(owner).items():
            if attribute.startswith(prefix) and _is_collaborator(value):
                collaborators[attribute] = value
    return collaborators


def _silence(mock: Mock, collaborator_class: type) -> None:
    for name in dir(collaborator_class):
        if name.startswith("__") or not callable(getattr(collaborator_class, name)):
            continue
        getattr(mock, name).return_value = None


def mock_collaborators[H](handler: H) -> CollaboratorMocks[H]:
    session = cast(AsyncSession, Mock(spec=AsyncSession))
    transaction_errors: list[BaseException] = []

    @asynccontextmanager
    async def transaction() -> AsyncIterator[AsyncSession]:
        try:
            yield session
        except BaseException as error:
            transaction_errors.append(error)
            raise

    mocks: CollaboratorMocks[H] = CollaboratorMocks(
        handler=handler, session=session, transaction_errors=transaction_errors
    )
    for attribute, value in _collaborators(type(handler)).items():
        collaborator_class = type(value)
        mock = Mock(spec=collaborator_class)
        if collaborator_class.__module__.startswith("luml.handlers."):
            _silence(mock, collaborator_class)
        if callable(getattr(collaborator_class, "transaction", None)):
            mock.transaction = Mock(side_effect=transaction)
        setattr(handler, attribute, mock)
        setattr(mocks, attribute.split("__", 1)[1], mock)
    return mocks
