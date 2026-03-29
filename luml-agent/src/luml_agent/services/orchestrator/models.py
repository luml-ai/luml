from dataclasses import dataclass
from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    MERGED = "merged"


class NodeStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class NodeType(StrEnum):
    IMPLEMENT = "implement"
    FORK = "fork"
    RUN = "run"
    DEBUG = "debug"


class EdgeReason(StrEnum):
    AUTO = "auto"
    FORK = "fork"
    DEBUG = "debug"
    MANUAL = "manual"


@dataclass
class RunConfig:
    max_depth: int = 5
    max_children_per_fork: int = 3
    max_debug_retries: int = 2
    max_concurrency: int = 2
    run_command_template: str = "uv run main.py"
    agent_id: str = "claude"
    fork_auto_approve: bool = True
    auto_mode: bool = False
    auto_terminate_timeout: int = 30
    implement_timeout: int = 1800
    run_timeout: int = 0
    debug_timeout: int = 1800
    fork_timeout: int = 900
    primary_metric: str = "metric"
    metric_direction: str = "max"
