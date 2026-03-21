from luml_agent.database import Database
from luml_agent.services.orchestrator.models import RunConfig


def should_spawn_debug(debug_retries: int, config: RunConfig) -> bool:
    return debug_retries < config.max_debug_retries


def should_allow_fork(depth: int, config: RunConfig) -> bool:
    return depth < config.max_depth


def count_children(db: Database, node_id: str) -> int:
    node = db.get_run_node(node_id)
    if node is None:
        return 0
    edges = db.list_run_edges(node.run_id)
    return sum(1 for e in edges if e.from_node_id == node_id)


def can_add_fork_child(db: Database, node_id: str, config: RunConfig) -> bool:
    return count_children(db, node_id) < config.max_children_per_fork
