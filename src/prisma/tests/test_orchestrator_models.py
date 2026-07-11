import pytest

from luml_prisma.database import Database
from luml_prisma.services.orchestrator.models import NodeStatus, NodeType, RunStatus


@pytest.fixture
def db() -> Database:
    d = Database()
    d.add_repository("test-repo", "/tmp/test-repo")
    d.add_repository("test-repo-2", "/tmp/test-repo-2")
    return d


class TestRunCRUD:
    def test_add_and_get_run(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="test-run", objective="do stuff")
        assert run.id is not None
        assert run.status == "pending"

        fetched = db.get_run(run.id)
        assert fetched is not None
        assert fetched.name == "test-run"
        assert fetched.objective == "do stuff"

    def test_get_run_not_found(self, db: Database) -> None:
        assert db.get_run("nonexistent") is None

    def test_list_runs(self, db: Database) -> None:
        repos = db.list_repositories()
        p1, p2 = repos[0].id, repos[1].id

        db.add_run(repository_id=p1, name="a", objective="")
        db.add_run(repository_id=p1, name="b", objective="")
        db.add_run(repository_id=p2, name="c", objective="")

        all_runs = db.list_runs()
        assert len(all_runs) == 3

        p1_runs = db.list_runs(repository_id=p1)
        assert len(p1_runs) == 2

    def test_update_run_status(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        db.update_run_status(run.id, RunStatus.RUNNING)
        updated = db.get_run(run.id)
        assert updated is not None
        assert updated.status == RunStatus.RUNNING

    def test_remove_run_cascades(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        node = db.add_run_node(run.id, None, NodeType.IMPLEMENT, depth=0)
        db.add_run_edge(run.id, node.id, node.id, "auto")
        db.add_run_event(run.id, node.id, "test_event")
        db.add_node_session(node.id, "sess-123")

        db.remove_run(run.id)

        assert db.get_run(run.id) is None
        assert db.list_run_nodes(run.id) == []
        assert db.list_run_edges(run.id) == []
        assert db.list_run_events(run.id) == []
        assert db.get_node_sessions(node.id) == []


class TestRunNodeCRUD:
    def test_add_and_get_node(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        node = db.add_run_node(
            run.id, None, NodeType.IMPLEMENT, depth=0,
            payload_json='{"prompt": "hello"}',
        )
        assert node.id is not None
        assert node.status == NodeStatus.QUEUED
        assert node.depth == 0
        assert node.parent_node_id is None

        fetched = db.get_run_node(node.id)
        assert fetched is not None
        assert fetched.payload_json == '{"prompt": "hello"}'

    def test_list_run_nodes(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        db.add_run_node(run.id, None, NodeType.IMPLEMENT, depth=0)
        db.add_run_node(run.id, None, NodeType.RUN, depth=1)
        nodes = db.list_run_nodes(run.id)
        assert len(nodes) == 2

    def test_parent_child_relationship(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        parent = db.add_run_node(run.id, None, NodeType.IMPLEMENT, depth=0)
        child = db.add_run_node(run.id, parent.id, NodeType.RUN, depth=1)
        assert child.parent_node_id == parent.id

    def test_update_node_status(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        node = db.add_run_node(run.id, None, NodeType.RUN, depth=0)
        db.update_node_status(node.id, NodeStatus.RUNNING)
        updated = db.get_run_node(node.id)
        assert updated is not None
        assert updated.status == NodeStatus.RUNNING

    def test_update_node_result(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        node = db.add_run_node(run.id, None, NodeType.RUN, depth=0)
        db.update_node_result(node.id, '{"exit_code": 0}')
        updated = db.get_run_node(node.id)
        assert updated is not None
        assert updated.result_json == '{"exit_code": 0}'

    def test_update_node_worktree(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        node = db.add_run_node(run.id, None, NodeType.IMPLEMENT, depth=0)
        db.update_node_worktree(node.id, "/tmp/wt", "agent/test-abc")
        updated = db.get_run_node(node.id)
        assert updated is not None
        assert updated.worktree_path == "/tmp/wt"
        assert updated.branch == "agent/test-abc"

    def test_increment_debug_retries(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        node = db.add_run_node(run.id, None, NodeType.IMPLEMENT, depth=0)
        assert node.debug_retries == 0
        count = db.increment_node_debug_retries(node.id)
        assert count == 1
        count = db.increment_node_debug_retries(node.id)
        assert count == 2

    def test_get_node_not_found(self, db: Database) -> None:
        assert db.get_run_node("nonexistent") is None


class TestRunEdgeCRUD:
    def test_add_and_list_edges(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        n1 = db.add_run_node(run.id, None, NodeType.IMPLEMENT, depth=0)
        n2 = db.add_run_node(run.id, n1.id, NodeType.RUN, depth=1)
        edge = db.add_run_edge(run.id, n1.id, n2.id, "auto")

        assert edge.id is not None
        assert edge.from_node_id == n1.id
        assert edge.to_node_id == n2.id
        assert edge.reason == "auto"

        edges = db.list_run_edges(run.id)
        assert len(edges) == 1


class TestRunEventCRUD:
    def test_event_seq_auto_increment(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        e1 = db.add_run_event(run.id, None, "run_created")
        e2 = db.add_run_event(run.id, None, "node_created")
        e3 = db.add_run_event(run.id, None, "node_status_changed")

        assert e1.seq == 1
        assert e2.seq == 2
        assert e3.seq == 3

    def test_event_seq_independent_per_run(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        r1 = db.add_run(repository_id=pid, name="r1", objective="")
        r2 = db.add_run(repository_id=pid, name="r2", objective="")

        e1 = db.add_run_event(r1.id, None, "created")
        e2 = db.add_run_event(r2.id, None, "created")

        assert e1.seq == 1
        assert e2.seq == 1

    def test_list_events_after_seq(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        db.add_run_event(run.id, None, "e1")
        db.add_run_event(run.id, None, "e2")
        db.add_run_event(run.id, None, "e3")

        all_events = db.list_run_events(run.id)
        assert len(all_events) == 3

        after_1 = db.list_run_events(run.id, after_seq=1)
        assert len(after_1) == 2
        assert after_1[0].seq == 2

        after_2 = db.list_run_events(run.id, after_seq=2)
        assert len(after_2) == 1
        assert after_2[0].event_type == "e3"

    def test_event_with_node_id(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        node = db.add_run_node(run.id, None, NodeType.IMPLEMENT, depth=0)
        event = db.add_run_event(
            run.id, node.id, "node_status_changed",
            '{"status": "running"}',
        )
        assert event.node_id == node.id
        assert event.data_json == '{"status": "running"}'

    def test_get_next_event_seq(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        assert db.get_next_event_seq(run.id) == 1
        db.add_run_event(run.id, None, "e1")
        assert db.get_next_event_seq(run.id) == 2


class TestNodeSessionCRUD:
    def test_add_and_get_sessions(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        node = db.add_run_node(run.id, None, NodeType.IMPLEMENT, depth=0)
        sess = db.add_node_session(node.id, "abc-123")

        assert sess.node_id == node.id
        assert sess.session_id == "abc-123"

        sessions = db.get_node_sessions(node.id)
        assert len(sessions) == 1
        assert sessions[0].session_id == "abc-123"

    def test_get_node_by_session(self, db: Database) -> None:
        pid = db.list_repositories()[0].id
        run = db.add_run(repository_id=pid, name="r", objective="")
        node = db.add_run_node(run.id, None, NodeType.IMPLEMENT, depth=0)
        db.add_node_session(node.id, "sess-456")

        found = db.get_node_by_session("sess-456")
        assert found is not None
        assert found.id == node.id

    def test_get_node_by_session_not_found(self, db: Database) -> None:
        assert db.get_node_by_session("nonexistent") is None
