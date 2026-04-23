from enum import StrEnum

from pydantic import BaseModel


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    MERGED = "merged"
    ARCHIVED = "archived"


class TaskCreateIn(BaseModel):
    repository_id: str
    name: str
    agent_id: str
    prompt: str = ""
    base_branch: str = "main"


class TaskStatusUpdateIn(BaseModel):
    status: str


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
    has_waiting_input: bool = False
