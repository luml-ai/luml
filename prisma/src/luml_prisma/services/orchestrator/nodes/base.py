from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from luml_prisma.config import AppConfig
from luml_prisma.database import Database
from luml_prisma.services.pty_manager import PtyManager

if TYPE_CHECKING:
    from luml_prisma.services.orchestrator.engine import OrchestratorEngine


@dataclass
class NodeServices:
    db: Database
    pty: PtyManager
    engine: "OrchestratorEngine"
    config: AppConfig


@dataclass
class NodeExecutionContext:
    node_id: str
    run_id: str
    repository_path: str
    base_branch: str
    node_type: str
    depth: int
    payload: dict[str, Any]
    parent_result: dict[str, Any] | None
    parent_worktree_path: str | None
    parent_branch: str | None
    run_config: dict[str, Any]
    services: NodeServices


@dataclass
class NodeSpawnSpec:
    node_type: str
    payload: dict[str, Any]
    reason: str = "auto"


@dataclass
class NodeResult:
    success: bool
    artifacts: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    spawn_next: list[NodeSpawnSpec] = field(default_factory=list)


class NodeHandler(Protocol):
    def type_id(self) -> str: ...
    def validate_payload(self, payload: dict[str, Any]) -> None: ...
    async def execute(self, ctx: NodeExecutionContext) -> NodeResult: ...
    def can_fork(self, result: NodeResult) -> bool: ...
    def default_next_nodes(self, result: NodeResult) -> list[NodeSpawnSpec]: ...
