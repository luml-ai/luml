"""The journal wire format: transactions, the op vocabulary, and `flow.yaml`.

A journal line is one transaction. Ops are a closed, discriminated vocabulary
so the SQLite index is a pure fold over the journal — every op carries the
facts its rows need, nothing is inferred from surrounding lines.
"""

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

#: Who a run nobody asked for is attributed to. A first-class actor beside
#: `user` and an agent's name, because the journal is read back as *who did
#: this* and answering `user` for a run the user never asked for is a lie the
#: timeline would then render. What it writes keeps a branch synced; it is
#: never a place the branch moved to.
AUTO_ACTOR = "auto"
CellNoteKind = Literal[
    "projection_completed",
    "refresh_failed",
    "experiment_unclosed",
]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class VersionFlag(_Frozen):
    """An accepted-but-broken state. Flags never reject a version."""

    code: FlagCode
    detail: str | None = None


class ConsumedRef(_Frozen):
    """A `consumes` entry after binding. `uid` is None when it did not resolve."""

    ref: str
    uid: str | None = None
    output: str | None = None


class OutputSpec(_Frozen):
    type: AssetType
    kind: str | None = None
    persist: bool = True


class CellManifest(_Frozen):
    """A note carries no compute: the class is a docstring, and it renders as one."""

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
    """Delete is per-branch: the cell leaves this branch's namespace only."""

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
    #: The parent's own step this branch copied — where the parent stood, which
    #: after a rewind is not its newest line. Absent on lines written before
    #: branches had a position; those derive it from the fork step.
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
    """Carries the restored state so the index never replays to fold this.

    Not a step of the branch: the line moves the branch's position to
    `to_step` and adds nothing to its history. The steps after it stay where
    they are, which is what makes moving forward again the same gesture.
    """

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
    """`files` carries the whole watched map, not just what moved: naming the
    changed file is what the staleness cause says in words, and a daemon that
    restarted has nothing to diff the next scan against otherwise."""

    op: Literal["workspace_code_changed"] = "workspace_code_changed"
    tree_hash: str
    previous_tree_hash: str | None = None
    changed_paths: list[str] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)


class EnvChanged(_Frozen):
    """`packages` carries the whole pinned map for the same reason the workspace
    tree carries its file list: a daemon that restarted has nothing to name the
    next transition against otherwise."""

    op: Literal["env_changed"] = "env_changed"
    lock_hash: str
    packages: dict[str, str] = Field(default_factory=dict)
    summary: str = ""


class FlagSet(_Frozen):
    """A version flag, or — with no `version_id` — a flag on the transaction."""

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
    """A step somebody marked on purpose, under the transaction's own intent.

    A marker, never a snapshot, and never a step of its own: every version the
    branch selected at `step` is already in the store, and the line carrying
    this op is not a position on the branch — the index folds it onto the step
    it names, the way a commit message rides on its commit. The words are the
    carrying transaction's intent, the one thing the journal cannot record
    without being told.
    """

    op: Literal["checkpointed"] = "checkpointed"
    branch_id: str
    #: The branch's own step the words attach to. Absent on lines written
    #: before marks folded; those ride the position the branch stood on then.
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
    """One journal line. `branch` is the branch id the batch was scoped to."""

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
    """`eager` names cells by uid: `flow.yaml` already indexes them, and a slug
    is a name that renames."""

    model_config = ConfigDict(extra="allow")

    eager_cost_threshold_s: float = 5.0
    reactivity: Reactivity = "auto"
    eager: list[str] = Field(default_factory=list)


class FlowManifest(BaseModel):
    """`flow.yaml` — daemon-written, committed, the slug↔uid cross-check."""

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
