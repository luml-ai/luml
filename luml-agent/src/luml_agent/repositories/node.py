from sqlalchemy import func

from luml_agent.models import (
    NodeSessionOrm,
    RunEdgeOrm,
    RunEventOrm,
    RunNodeOrm,
)
from luml_agent.repositories.base import RepositoryBase


class RunNodeRepository(RepositoryBase):
    def add_node(
        self,
        run_id: str,
        parent_node_id: str | None,
        node_type: str,
        depth: int,
        payload_json: str = "{}",
        worktree_path: str = "",
        branch: str = "",
    ) -> RunNodeOrm:
        now = self._now()
        with self._session_factory() as session:
            node = RunNodeOrm(
                run_id=run_id,
                parent_node_id=parent_node_id,
                node_type=node_type,
                status="queued",
                depth=depth,
                payload_json=payload_json,
                result_json="{}",
                worktree_path=worktree_path,
                branch=branch,
                debug_retries=0,
                created_at=now,
                updated_at=now,
            )
            session.add(node)
            session.commit()
            session.refresh(node)
            return node

    def get_node(self, node_id: str) -> RunNodeOrm | None:
        with self._session_factory() as session:
            return session.get(RunNodeOrm, node_id)

    def list_nodes(self, run_id: str) -> list[RunNodeOrm]:
        with self._session_factory() as session:
            return list(
                session.query(RunNodeOrm)
                .filter(RunNodeOrm.run_id == run_id)
                .order_by(RunNodeOrm.created_at)
                .all()
            )

    def update_node_status(
        self, node_id: str, status: str,
    ) -> None:
        with self._session_factory() as session:
            session.query(RunNodeOrm).filter(
                RunNodeOrm.id == node_id,
            ).update({"status": status, "updated_at": self._now()})
            session.commit()

    def update_node_result(
        self, node_id: str, result_json: str,
    ) -> None:
        with self._session_factory() as session:
            session.query(RunNodeOrm).filter(
                RunNodeOrm.id == node_id,
            ).update({"result_json": result_json, "updated_at": self._now()})
            session.commit()

    def update_node_worktree(
        self,
        node_id: str,
        worktree_path: str,
        branch: str,
    ) -> None:
        with self._session_factory() as session:
            session.query(RunNodeOrm).filter(
                RunNodeOrm.id == node_id,
            ).update({
                "worktree_path": worktree_path,
                "branch": branch,
                "updated_at": self._now(),
            })
            session.commit()

    def increment_debug_retries(self, node_id: str) -> int:
        with self._session_factory() as session:
            session.query(RunNodeOrm).filter(
                RunNodeOrm.id == node_id,
            ).update({
                "debug_retries": RunNodeOrm.debug_retries + 1,
                "updated_at": self._now(),
            })
            session.commit()
            node = session.get(RunNodeOrm, node_id)
            return node.debug_retries if node else 0

    def add_edge(
        self,
        run_id: str,
        from_node_id: str,
        to_node_id: str,
        reason: str = "auto",
    ) -> RunEdgeOrm:
        with self._session_factory() as session:
            edge = RunEdgeOrm(
                run_id=run_id,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
                reason=reason,
            )
            session.add(edge)
            session.commit()
            session.refresh(edge)
            return edge

    def list_edges(self, run_id: str) -> list[RunEdgeOrm]:
        with self._session_factory() as session:
            return list(
                session.query(RunEdgeOrm)
                .filter(RunEdgeOrm.run_id == run_id)
                .order_by(RunEdgeOrm.id)
                .all()
            )

    def add_event(
        self,
        run_id: str,
        node_id: str | None,
        event_type: str,
        data_json: str = "{}",
    ) -> RunEventOrm:
        now = self._now()
        with self._session_factory() as session:
            next_seq = (
                session.query(
                    func.coalesce(func.max(RunEventOrm.seq), 0) + 1,
                )
                .filter(RunEventOrm.run_id == run_id)
                .scalar()
            )
            event = RunEventOrm(
                run_id=run_id,
                node_id=node_id,
                seq=next_seq,
                event_type=event_type,
                data_json=data_json,
                created_at=now,
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            return event

    def list_events(
        self, run_id: str, after_seq: int = 0,
    ) -> list[RunEventOrm]:
        with self._session_factory() as session:
            return list(
                session.query(RunEventOrm)
                .filter(
                    RunEventOrm.run_id == run_id,
                    RunEventOrm.seq > after_seq,
                )
                .order_by(RunEventOrm.seq)
                .all()
            )

    def get_next_event_seq(self, run_id: str) -> int:
        with self._session_factory() as session:
            return (  # type: ignore[return-value]
                session.query(
                    func.coalesce(func.max(RunEventOrm.seq), 0) + 1,
                )
                .filter(RunEventOrm.run_id == run_id)
                .scalar()
            )

    def add_session(
        self, node_id: str, session_id: str,
    ) -> NodeSessionOrm:
        now = self._now()
        with self._session_factory() as session:
            ns = NodeSessionOrm(
                node_id=node_id,
                session_id=session_id,
                created_at=now,
            )
            session.add(ns)
            session.commit()
            session.refresh(ns)
            return ns

    def get_sessions(
        self, node_id: str,
    ) -> list[NodeSessionOrm]:
        with self._session_factory() as session:
            return list(
                session.query(NodeSessionOrm)
                .filter(NodeSessionOrm.node_id == node_id)
                .order_by(NodeSessionOrm.id)
                .all()
            )

    def has_waiting_input_nodes(self, run_id: str) -> bool:
        with self._session_factory() as session:
            return (
                session.query(RunNodeOrm)
                .filter(
                    RunNodeOrm.run_id == run_id,
                    RunNodeOrm.status == "waiting_input",
                )
                .first()
            ) is not None

    def get_node_by_session(
        self, session_id: str,
    ) -> RunNodeOrm | None:
        with self._session_factory() as session:
            ns = (
                session.query(NodeSessionOrm)
                .filter(NodeSessionOrm.session_id == session_id)
                .first()
            )
            if ns is None:
                return None
            return session.get(RunNodeOrm, ns.node_id)
