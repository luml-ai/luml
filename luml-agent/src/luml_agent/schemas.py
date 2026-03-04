import json
from typing import Any

from pydantic import BaseModel, ConfigDict

from luml_agent.agents import AgentDef


class RepositoryCreateIn(BaseModel):
    name: str
    path: str


class TaskCreateIn(BaseModel):
    repository_id: str
    name: str
    agent_id: str
    prompt: str = ""
    base_branch: str = "main"


class TaskStatusUpdateIn(BaseModel):
    status: str


class RunCreateIn(BaseModel):
    repository_id: str
    name: str
    objective: str
    base_branch: str = "main"
    agent_id: str = "claude"
    run_command: str = "uv run main.py"
    max_depth: int = 5
    max_children_per_fork: int = 3
    max_debug_retries: int = 2
    max_concurrency: int = 2
    fork_auto_approve: bool = True
    auto_mode: bool = False
    auto_terminate_timeout: int = 30


class ReorderItem(BaseModel):
    id: str
    position: int


class ReorderIn(BaseModel):
    items: list[ReorderItem]


class NodeActionIn(BaseModel):
    action: str
    payload: dict[str, Any] = {}


class NodeInputIn(BaseModel):
    text: str


class RepositoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    path: str


class TaskOut(BaseModel):
    id: str
    repository_id: str
    name: str
    branch: str
    worktree_path: str
    agent_id: str
    status: str
    prompt: str
    base_branch: str
    position: int | None = None
    created_at: str
    updated_at: str
    is_alive: bool = False
    session_id: str | None = None


class RunOut(BaseModel):
    id: str
    repository_id: str
    name: str
    objective: str
    status: str
    config: dict[str, Any] = {}
    base_branch: str = "main"
    position: int | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_db(cls, r: Any) -> "RunOut":  # noqa: ANN401
        config = json.loads(r.config_json) if r.config_json else {}
        return cls(
            id=r.id,
            repository_id=r.repository_id,
            name=r.name,
            objective=r.objective,
            status=r.status,
            config=config,
            base_branch=r.base_branch,
            position=r.position,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )


class RunNodeOut(BaseModel):
    id: str
    run_id: str
    parent_node_id: str | None
    node_type: str
    status: str
    depth: int
    payload: dict[str, Any] = {}
    result: dict[str, Any] = {}
    worktree_path: str
    branch: str
    debug_retries: int
    created_at: str
    updated_at: str
    session_id: str | None = None
    is_alive: bool = False

    @classmethod
    def from_db(
        cls,
        n: Any,  # noqa: ANN401
        active_session_id: str | None = None,
    ) -> "RunNodeOut":
        return cls(
            id=n.id,
            run_id=n.run_id,
            parent_node_id=n.parent_node_id,
            node_type=n.node_type,
            status=n.status,
            depth=n.depth,
            payload=(
                json.loads(n.payload_json) if n.payload_json else {}
            ),
            result=(
                json.loads(n.result_json) if n.result_json else {}
            ),
            worktree_path=n.worktree_path,
            branch=n.branch,
            debug_retries=n.debug_retries,
            created_at=n.created_at,
            updated_at=n.updated_at,
            session_id=active_session_id,
            is_alive=active_session_id is not None,
        )


class RunEdgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    from_node_id: str
    to_node_id: str
    reason: str


class RunEventOut(BaseModel):
    id: str
    run_id: str
    node_id: str | None
    seq: int
    type: str
    data: dict[str, Any] = {}
    created_at: str

    @classmethod
    def from_db(cls, e: Any) -> "RunEventOut":  # noqa: ANN401
        return cls(
            id=e.id,
            run_id=e.run_id,
            node_id=e.node_id,
            seq=e.seq,
            type=e.event_type,
            data=(
                json.loads(e.data_json) if e.data_json else {}
            ),
            created_at=e.created_at,
        )


class AgentOut(BaseModel):
    id: str
    name: str
    cli: str
    prompt_flag: str
    auto_approve_flag: str
    resume_flag: str
    default_args: list[str]

    @classmethod
    def from_def(cls, a: AgentDef) -> "AgentOut":
        return cls(
            id=a.id,
            name=a.name,
            cli=a.cli,
            prompt_flag=a.prompt_flag,
            auto_approve_flag=a.auto_approve_flag,
            resume_flag=a.resume_flag,
            default_args=a.default_args,
        )


class BrowseEntryOut(BaseModel):
    name: str
    path: str
    is_git: bool


class BrowseResultOut(BaseModel):
    current: str
    parent: str | None
    dirs: list[BrowseEntryOut]
    is_git: bool


class BranchListOut(BaseModel):
    branches: list[str]
