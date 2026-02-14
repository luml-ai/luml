from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Group:
    id: str
    name: str
    description: str | None
    created_at: datetime


@dataclass
class Model:
    id: str
    name: str
    created_at: datetime
    tags: list[str] = field(default_factory=list)
    path: str | None = None
    experiment_id: str | None = None


@dataclass
class Experiment:
    id: str
    name: str
    status: str
    group_id: str
    created_at: datetime
    tags: list[str] = field(default_factory=list)
    static_params: dict[str, Any] = field(default_factory=dict)
    dynamic_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentMetaData:
    name: str
    created_at: datetime
    status: str
    group_id: str
    tags: list[str] = field(default_factory=list)


@dataclass
class ExperimentData:
    experiment_id: str
    metadata: ExperimentMetaData
    static_params: dict[str, Any] = field(default_factory=dict)
    dynamic_metrics: dict[str, Any] = field(default_factory=dict)
    attachments: dict[str, Any] = field(default_factory=dict)
