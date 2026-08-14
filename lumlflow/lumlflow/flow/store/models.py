"""The journal wire format: transactions, the op vocabulary, and `flow.yaml`.

A journal line is one transaction. Ops are a closed, discriminated vocabulary
so the SQLite index is a pure fold over the journal — every op carries the
facts its rows need, nothing is inferred from surrounding lines.
"""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from lumlflow.flow.hashing import canonical_json

JOURNAL_SCHEMA_VERSION = 1

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
UploadState = Literal["queued", "uploading", "failed"]
KindSource = Literal["declared", "matcher", "fallback"]
Reactivity = Literal["lazy", "auto"]
EnvPolicy = Literal["ask", "auto", "never"]
# `auto` takes whatever profile the OS affords and reports what that came to;
# there is no setting for "and be sure", because no platform offers one.
SandboxSetting = Literal["auto", "off"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class LumlRef(_Frozen):
    collection: str
    artifact_id: str
    version: str
    digest: str


class OutputRecord(_Frozen):
    content_hash: str
    kind: str
    kind_source: KindSource
    size: int
    preview_ref: str | None = None
    value_ref: str | None = None
    luml_ref: LumlRef | None = None
    persisted: bool = True


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


class BranchArchived(_Frozen):
    op: Literal["branch_archived"] = "branch_archived"
    branch_id: str


class WorktreeBound(_Frozen):
    op: Literal["worktree_bound"] = "worktree_bound"
    path: str
    branch_id: str
    actor: str | None = None


class Rewound(_Frozen):
    """Carries the restored state so the index never replays to fold this."""

    op: Literal["rewound"] = "rewound"
    branch_id: str
    to_step: int
    selections: dict[str, str] = Field(default_factory=dict)
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


class UploadStateChanged(_Frozen):
    op: Literal["upload_state_changed"] = "upload_state_changed"
    mat_id: str
    output: str
    state: UploadState
    attempts: int = 0


class UploadRecorded(_Frozen):
    """The success terminal: the collection reference lands on the output."""

    op: Literal["upload_recorded"] = "upload_recorded"
    mat_id: str
    output: str
    ref: LumlRef


class FlagSet(_Frozen):
    """A version flag, or — with no `version_id` — a flag on the transaction."""

    op: Literal["flag_set"] = "flag_set"
    flag: str
    version_id: str | None = None
    detail: str | None = None


class AgentBegin(_Frozen):
    """`worktree` separates a session that edits files from one that only calls
    the API: only the first holds the worktree lock and collects file-edit
    attribution — an MCP session's attribution rides on the ops it invokes."""

    op: Literal["agent_begin"] = "agent_begin"
    actor: str
    label: str
    worktree: bool = False


class AgentEnd(_Frozen):
    op: Literal["agent_end"] = "agent_end"
    actor: str
    label: str | None = None


class SecretRefAdded(_Frozen):
    """Records that a secret name exists. Values never enter the journal."""

    op: Literal["secret_ref_added"] = "secret_ref_added"
    name: str


class Checkpointed(_Frozen):
    """A point somebody marked on purpose.

    A marker, never a snapshot: every version the branch selects at this step
    is already in the store, so what a checkpoint adds is the transaction's own
    intent — the one thing the journal cannot record without being told.
    """

    op: Literal["checkpointed"] = "checkpointed"
    branch_id: str


Op = Annotated[
    FlowInit
    | CellAccepted
    | CellRemoved
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
    | UploadStateChanged
    | UploadRecorded
    | FlagSet
    | AgentBegin
    | AgentEnd
    | SecretRefAdded
    | Checkpointed,
    Field(discriminator="op"),
]


class Transaction(BaseModel):
    """One journal line. `branch` is the branch id the batch was scoped to."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: int
    ts: str
    actor: str
    intent: str
    offline: bool = False
    settled: bool = False
    branch: str | None = None
    ops: list[Op]

    def to_line(self) -> bytes:
        return canonical_json(self.model_dump(mode="json")) + b"\n"

    @classmethod
    def from_line(cls, line: bytes) -> Self:
        return cls.model_validate_json(line)


class FlowSettings(BaseModel):
    """`eager` names cells by uid: `flow.yaml` already indexes them, and a slug
    is a name that renames."""

    model_config = ConfigDict(extra="forbid")

    eager_cost_threshold_s: float = 5.0
    reactivity: Reactivity = "auto"
    eager: list[str] = Field(default_factory=list)
    paranoid: bool = False
    strict: bool = False
    sandbox: SandboxSetting = "auto"
    # What an env change does to a kernel holding the old imports. The banner is
    # the floor under all three: `never` still says the kernel is behind, it
    # only never acts on it.
    env_policy: EnvPolicy = "ask"


class FlowManifest(BaseModel):
    """`flow.yaml` — daemon-written, committed, the slug↔uid cross-check."""

    model_config = ConfigDict(extra="forbid")

    flow_id: str
    name: str
    language: Literal["python"] = "python"
    cells: dict[str, str] = Field(default_factory=dict)
    settings: FlowSettings = Field(default_factory=FlowSettings)
