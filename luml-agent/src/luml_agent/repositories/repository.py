from sqlalchemy.exc import IntegrityError

from luml_agent.infra.exceptions import InvalidOperationError
from luml_agent.models import RepositoryOrm, TaskOrm
from luml_agent.repositories.base import RepositoryBase


class RepositoryRepository(RepositoryBase):
    def add(
        self,
        name: str,
        path: str,
    ) -> RepositoryOrm:
        with self._session_factory() as session:
            repo = RepositoryOrm(name=name, path=path)
            session.add(repo)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise InvalidOperationError(
                    "A repository with this path already exists"
                ) from exc
            session.refresh(repo)
            return repo

    def get(self, repository_id: str) -> RepositoryOrm | None:
        with self._session_factory() as session:
            return session.get(RepositoryOrm, repository_id)

    def list_all(self) -> list[RepositoryOrm]:
        with self._session_factory() as session:
            return list(
                session.query(RepositoryOrm).order_by(RepositoryOrm.name).all()
            )

    def remove(self, repository_id: str) -> None:
        with self._session_factory() as session:
            session.query(TaskOrm).filter(
                TaskOrm.repository_id == repository_id,
            ).delete()
            session.query(RepositoryOrm).filter(
                RepositoryOrm.id == repository_id,
            ).delete()
            session.commit()
