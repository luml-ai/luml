from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lumlflow.flow.hashing import canonical_json

JOURNAL_SCHEMA_VERSION = 2

FlagCode = Literal[
    "dangling_ref",
    "ambiguous",
    "invalid",
    "incomplete",
    "divergent",
    "placeholder_slug",
    "hygiene",
]
AssetType = Literal["model", "dataset", "experiment", "asset"]
CellClassification = Literal["cell", "note"]
MaterializationState = Literal["running", "succeeded", "failed", "cancelled"]
KindSource = Literal["declared", "matcher", "fallback"]
Reactivity = Literal["lazy", "auto"]

AUTO_ACTOR = "auto"
CellNoteKind = Literal[
    "projection_completed",
    "refresh_failed",
    "experiment_unclosed",
]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class VersionFlag(_Frozen):
    code: FlagCode
    detail: str | None = None


class ConsumedRef(_Frozen):
    ref: str
    uid: str | None = None
    output: str | None = None


class OutputSpec(_Frozen):
    type: AssetType
    kind: str | None = None
    persist: bool = True


class CellManifest(_Frozen):
    classification: CellClassification = "cell"
    consumes: dict[str, ConsumedRef] = Field(default_factory=dict)
    produces: dict[str, OutputSpec] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    volatility: str | None = None
    env_sensitive: bool = False


class InputRef(_Frozen):
    uid: str
    output: str
    content_hash: str
    mat_id: str


class TrackerRef(_Frozen):
    experiment_id: str
    store: str
    group: str = ""
    tags: list[str] = Field(default_factory=list)


class OutputRecord(_Frozen):
    content_hash: str
    kind: str
    kind_source: KindSource
    size: int
    filename: str | None = None
    preview_ref: str | None = None
    value_ref: str | None = None
    persisted: bool = True
    tracker_ref: TrackerRef | None = None


class FlowInit(_Frozen):
    op: Literal["flow_init"] = "flow_init"
    flow_id: str
    name: str
    language: Literal["python"] = "python"
    schema_version: int = JOURNAL_SCHEMA_VERSION


class CellAccepted(_Frozen):
    op: Literal["cell_accepted"] = "cell_accepted"
    uid: str
    version_id: str
    slug: str
    definition_hash: str
    raw_source_ref: str
    bound_source_ref: str
    manifest: CellManifest
    parent_version_id: str | None = None
    copied_from: str | None = None
    author: str = "user"
    flags: list[VersionFlag] = Field(default_factory=list)


class CellRemoved(_Frozen):
    op: Literal["cell_removed"] = "cell_removed"
    uid: str
    branch_id: str


class CellNoted(_Frozen):
    op: Literal["cell_noted"] = "cell_noted"
    uid: str
    kind: CellNoteKind
    sentence: str
    version_id: str | None = None


class SelectionSet(_Frozen):
    op: Literal["selection_set"] = "selection_set"
    branch_id: str
    uid: str
    version_id: str
    pinned: bool = False


class BranchCreated(_Frozen):
    op: Literal["branch_created"] = "branch_created"
    branch_id: str
    name: str
    parent_branch_id: str | None = None
    fork_step: int = 0
    parent_step: int | None = None


class BranchArchived(_Frozen):
    op: Literal["branch_archived"] = "branch_archived"
    branch_id: str


class WorktreeBound(_Frozen):
    op: Literal["worktree_bound"] = "worktree_bound"
    flow_id: str
    branch_id: str
    actor: str | None = None


class Rewound(_Frozen):
    op: Literal["rewound"] = "rewound"
    branch_id: str
    to_step: int
    selections: dict[str, str] = Field(default_factory=dict)
    slugs: dict[str, str] = Field(default_factory=dict)
    baselines: dict[str, str] = Field(default_factory=dict)


class Adopted(_Frozen):
    op: Literal["adopted"] = "adopted"
    branch_id: str
    uid: str
    version_id: str
    from_branch_id: str


class Renamed(_Frozen):
    op: Literal["renamed"] = "renamed"
    uid: str
    branch_id: str
    old_slug: str
    new_slug: str


class RunRecorded(_Frozen):
    op: Literal["run_recorded"] = "run_recorded"
    mat_id: str
    uid: str
    version_id: str
    branch_id: str
    memo_key: str
    state: MaterializationState
    inputs: dict[str, InputRef] = Field(default_factory=dict)
    outputs: dict[str, OutputRecord] = Field(default_factory=dict)
    identity_dependent: bool = False
    external: bool = False
    env_lock_hash: str | None = None
    cost_seconds: float | None = None
    log_ref: str | None = None
    experiment_id: str | None = None
    experiment_store: str | None = None
    sdk_version_warning: str | None = None
    started_step: int = 0
    finished_step: int | None = None


class MemoHit(_Frozen):
    op: Literal["memo_hit"] = "memo_hit"
    branch_id: str
    uid: str
    version_id: str
    memo_key: str
    mat_id: str


class WorkspaceCodeChanged(_Frozen):
    op: Literal["workspace_code_changed"] = "workspace_code_changed"
    tree_hash: str
    previous_tree_hash: str | None = None
    changed_paths: list[str] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)


class EnvChanged(_Frozen):
    op: Literal["env_changed"] = "env_changed"
    lock_hash: str
    packages: dict[str, str] = Field(default_factory=dict)
    summary: str = ""


class FlagSet(_Frozen):
    op: Literal["flag_set"] = "flag_set"
    flag: str
    version_id: str | None = None
    detail: str | None = None


class AgentBegin(_Frozen):
    op: Literal["agent_begin"] = "agent_begin"
    actor: str
    label: str


class AgentEnd(_Frozen):
    op: Literal["agent_end"] = "agent_end"
    actor: str
    label: str | None = None


class Checkpointed(_Frozen):
    op: Literal["checkpointed"] = "checkpointed"
    branch_id: str
    step: int | None = None


Op = Annotated[
    FlowInit
    | CellAccepted
    | CellRemoved
    | CellNoted
    | SelectionSet
    | BranchCreated
    | BranchArchived
    | WorktreeBound
    | Rewound
    | Adopted
    | Renamed
    | RunRecorded
    | MemoHit
    | WorkspaceCodeChanged
    | EnvChanged
    | FlagSet
    | AgentBegin
    | AgentEnd
    | Checkpointed,
    Field(discriminator="op"),
]


class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    step: int
    ts: str
    actor: str
    intent: str
    offline: bool = False
    settled: bool = False
    branch: str | None = None
    ops: list[Op]

    @model_validator(mode="after")
    def require_cell_note_scope(self) -> Self:
        if not any(isinstance(op, CellNoted) for op in self.ops):
            return self
        if self.branch is None:
            raise ValueError("cell notes require a lane-scoped transaction")
        if self.actor != "system":
            raise ValueError("cell notes require the system actor")
        return self

    def to_line(self) -> bytes:
        return canonical_json(self.model_dump(mode="json")) + b"\n"

    @classmethod
    def from_line(cls, line: bytes) -> Self:
        return cls.model_validate_json(line)


class FlowSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    eager_cost_threshold_s: float = 5.0
    reactivity: Reactivity = "auto"
    eager: list[str] = Field(default_factory=list)


class FlowManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    flow_id: str
    name: str
    language: Literal["python"] = "python"
    cells: dict[str, str] = Field(default_factory=dict)
    order: dict[str, object] | None = None
    settings: FlowSettings = Field(default_factory=FlowSettings)

    @field_validator("order", mode="before")
    @classmethod
    def tolerate_a_malformed_order_map(cls, value: object) -> dict[str, object] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            return None
        return {str(uid): key for uid, key in value.items()}
