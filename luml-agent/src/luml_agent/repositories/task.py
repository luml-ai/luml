from luml_agent.orm import TaskOrm
from luml_agent.repositories.base import RepositoryBase


class TaskRepository(RepositoryBase):
    def add(
        self,
        repository_id: str,
        name: str,
        branch: str,
        worktree_path: str,
        agent_id: str,
        prompt: str = "",
        tmux_session: str = "",
        status: str = "running",
        base_branch: str = "main",
    ) -> TaskOrm:
        now = self._now()
        with self._session_factory() as session:
            task = TaskOrm(
                repository_id=repository_id,
                name=name,
                branch=branch,
                worktree_path=worktree_path,
                agent_id=agent_id,
                status=status,
                prompt=prompt,
                tmux_session=tmux_session,
                base_branch=base_branch,
                created_at=now,
                updated_at=now,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            return task

    def get(self, task_id: str) -> TaskOrm | None:
        with self._session_factory() as session:
            return session.get(TaskOrm, task_id)

    def list_all(
        self, repository_id: str | None = None,
    ) -> list[TaskOrm]:
        with self._session_factory() as session:
            q = session.query(TaskOrm)
            if repository_id is not None:
                q = q.filter(TaskOrm.repository_id == repository_id)
            return list(
                q.order_by(
                    TaskOrm.position.is_(None),
                    TaskOrm.position.asc(),
                    TaskOrm.updated_at.desc(),
                ).all()
            )

    def update_status(self, task_id: str, status: str) -> None:
        with self._session_factory() as session:
            session.query(TaskOrm).filter(
                TaskOrm.id == task_id,
            ).update({"status": status, "updated_at": self._now()})
            session.commit()

    def update_tmux_session(
        self, task_id: str, tmux_session: str,
    ) -> None:
        with self._session_factory() as session:
            session.query(TaskOrm).filter(
                TaskOrm.id == task_id,
            ).update({"tmux_session": tmux_session, "updated_at": self._now()})
            session.commit()

    def update_positions(
        self, items: list[tuple[str, int]],
    ) -> None:
        with self._session_factory() as session:
            for task_id, position in items:
                session.query(TaskOrm).filter(
                    TaskOrm.id == task_id,
                ).update({"position": position})
            session.commit()

    def remove(self, task_id: str) -> None:
        with self._session_factory() as session:
            session.query(TaskOrm).filter(
                TaskOrm.id == task_id,
            ).delete()
            session.commit()
