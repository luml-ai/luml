import pytest

from luml_prisma.database import Database
from luml_prisma.services.orchestrator.models import NodeType, RunConfig
from luml_prisma.services.orchestrator.policy import (
    can_add_fork_child,
    count_children,
    should_allow_fork,
    should_spawn_debug,
)


@pytest.fixture
def db() -> Database:
    d = Database()
    d.add_repository("test", "/tmp/test-repo")
    return d


class TestShouldSpawnDebug:
    def test_within_budget(self) -> None:
        config = RunConfig(max_debug_retries=3)
        assert should_spawn_debug(0, config) is True
        assert should_spawn_debug(1, config) is True
        assert should_spawn_debug(2, config) is True

    def test_at_budget(self) -> None:
        config = RunConfig(max_debug_retries=2)
        assert should_spawn_debug(2, config) is False

    def test_over_budget(self) -> None:
        config = RunConfig(max_debug_retries=1)
        assert should_spawn_debug(5, config) is False

    def test_zero_budget(self) -> None:
        config = RunConfig(max_debug_retries=0)
        assert should_spawn_debug(0, config) is False


class TestShouldAllowFork:
    def test_within_depth(self) -> None:
        config = RunConfig(max_depth=5)
        assert should_allow_fork(0, config) is True
        assert should_allow_fork(4, config) is True

    def test_at_max_depth(self) -> None:
        config = RunConfig(max_depth=3)
        assert should_allow_fork(3, config) is False

    def test_over_max_depth(self) -> None:
        config = RunConfig(max_depth=2)
        assert should_allow_fork(5, config) is False


class TestCountChildren:
    def test_no_children(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(run.id, None, NodeType.IMPLEMENT, 0)
        assert count_children(db, node.id) == 0

    def test_with_children(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        parent = db.add_run_node(
            run.id, None, NodeType.IMPLEMENT, 0,
        )
        c1 = db.add_run_node(
            run.id, parent.id, NodeType.RUN, 1,
        )
        c2 = db.add_run_node(
            run.id, parent.id, NodeType.RUN, 1,
        )
        db.add_run_edge(
            run.id, parent.id, c1.id, "auto",
        )
        db.add_run_edge(
            run.id, parent.id, c2.id, "auto",
        )
        assert count_children(db, parent.id) == 2


class TestCanAddForkChild:
    def test_under_limit(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        node = db.add_run_node(run.id, None, NodeType.FORK, 0)
        config = RunConfig(max_children_per_fork=3)
        assert can_add_fork_child(db, node.id, config) is True

    def test_at_limit(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(pid, "r", "")
        parent = db.add_run_node(
            run.id, None, NodeType.FORK, 0,
        )
        config = RunConfig(max_children_per_fork=2)
        for _ in range(2):
            child = db.add_run_node(
                run.id, parent.id, NodeType.IMPLEMENT, 1,
            )
            db.add_run_edge(
                run.id, parent.id, child.id, "fork",
            )
        assert (
            can_add_fork_child(db, parent.id, config)
            is False
        )
