from luml_agent.orm import (
    NodeSessionOrm,
    RunEdgeOrm,
    RunEventOrm,
    RunNodeOrm,
    RunOrm,
)
from luml_agent.repositories.base import RepositoryBase


class RunRepository(RepositoryBase):
    def add(
        self,
        repository_id: str,
        name: str,
        objective: str,
        config_json: str = "{}",
        status: str = "pending",
        base_branch: str = "main",
    ) -> RunOrm:
        now = self._now()
        with self._session_factory() as session:
            run = RunOrm(
                repository_id=repository_id,
                name=name,
                objective=objective,
                status=status,
                config_json=config_json,
                base_branch=base_branch,
                created_at=now,
                updated_at=now,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def get(self, run_id: str) -> RunOrm | None:
        with self._session_factory() as session:
            return session.get(RunOrm, run_id)

    def list_all(
        self, repository_id: str | None = None,
    ) -> list[RunOrm]:
        with self._session_factory() as session:
            q = session.query(RunOrm)
            if repository_id is not None:
                q = q.filter(RunOrm.repository_id == repository_id)
            return list(
                q.order_by(
                    RunOrm.position.is_(None),
                    RunOrm.position.asc(),
                    RunOrm.updated_at.desc(),
                ).all()
            )

    def update_status(
        self, run_id: str, status: str,
    ) -> None:
        with self._session_factory() as session:
            session.query(RunOrm).filter(
                RunOrm.id == run_id,
            ).update({"status": status, "updated_at": self._now()})
            session.commit()

    def update_positions(
        self, items: list[tuple[str, int]],
    ) -> None:
        with self._session_factory() as session:
            for run_id, position in items:
                session.query(RunOrm).filter(
                    RunOrm.id == run_id,
                ).update({"position": position})
            session.commit()

    def remove(self, run_id: str) -> None:
        with self._session_factory() as session:
            node_ids = [
                r[0] for r in
                session.query(RunNodeOrm.id).filter(RunNodeOrm.run_id == run_id).all()
            ]
            if node_ids:
                session.query(NodeSessionOrm).filter(
                    NodeSessionOrm.node_id.in_(node_ids),
                ).delete(synchronize_session=False)
            session.query(RunEventOrm).filter(
                RunEventOrm.run_id == run_id,
            ).delete(synchronize_session=False)
            session.query(RunEdgeOrm).filter(
                RunEdgeOrm.run_id == run_id,
            ).delete(synchronize_session=False)
            session.query(RunNodeOrm).filter(
                RunNodeOrm.run_id == run_id,
            ).delete(synchronize_session=False)
            session.query(RunOrm).filter(
                RunOrm.id == run_id,
            ).delete(synchronize_session=False)
            session.commit()

    def reset_data(self, run_id: str) -> None:
        with self._session_factory() as session:
            node_ids = [
                r[0] for r in
                session.query(RunNodeOrm.id).filter(RunNodeOrm.run_id == run_id).all()
            ]
            if node_ids:
                session.query(NodeSessionOrm).filter(
                    NodeSessionOrm.node_id.in_(node_ids),
                ).delete(synchronize_session=False)
            session.query(RunEventOrm).filter(
                RunEventOrm.run_id == run_id,
            ).delete(synchronize_session=False)
            session.query(RunEdgeOrm).filter(
                RunEdgeOrm.run_id == run_id,
            ).delete(synchronize_session=False)
            session.query(RunNodeOrm).filter(
                RunNodeOrm.run_id == run_id,
            ).delete(synchronize_session=False)
            session.commit()
