"""The SQLite index — a materialized view of the journal, never truth.

Applying a transaction is a pure fold: every op carries the facts its rows
need. That is what makes a full rebuild from the journal equivalent to the
incremental path, and why a missing, stale, or corrupt index is only ever a
latency problem.
"""

import json
import sqlite3
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from lumlflow.flow.hashing import canonical_json
from lumlflow.flow.store.models import (
    Adopted,
    AgentBegin,
    AgentEnd,
    BranchArchived,
    BranchCreated,
    CellAccepted,
    CellManifest,
    CellRemoved,
    Checkpointed,
    EnvChanged,
    FlagSet,
    FlowInit,
    InputRef,
    MaterializationState,
    MemoHit,
    Op,
    OutputRecord,
    Renamed,
    Rewound,
    RunRecorded,
    SecretRefAdded,
    SelectionSet,
    Transaction,
    UploadRecorded,
    UploadStateChanged,
    VersionFlag,
    WorkspaceCodeChanged,
    WorktreeBound,
)

INDEX_SCHEMA_VERSION = 5

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE cells (
    uid TEXT PRIMARY KEY,
    created_step INTEGER NOT NULL,
    copied_from TEXT
);

CREATE TABLE asset_versions (
    version_id TEXT PRIMARY KEY,
    uid TEXT NOT NULL,
    slug TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    raw_source_ref TEXT NOT NULL,
    bound_source_ref TEXT NOT NULL,
    manifest TEXT NOT NULL,
    flags TEXT NOT NULL,
    parent_version_id TEXT,
    author TEXT NOT NULL,
    created_step INTEGER NOT NULL
);
CREATE INDEX asset_versions_uid ON asset_versions (uid);

CREATE TABLE branches (
    branch_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    parent_branch_id TEXT,
    fork_step INTEGER NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE selections (
    branch_id TEXT NOT NULL,
    uid TEXT NOT NULL,
    version_id TEXT NOT NULL,
    pinned INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (branch_id, uid)
);

CREATE TABLE baselines (
    branch_id TEXT NOT NULL,
    uid TEXT NOT NULL,
    mat_id TEXT NOT NULL,
    -- How this branch came to observe that materialization: it ran it, a memo
    -- hit handed it over, a fork inherited it, or a rewind restored it. Only
    -- the first two are claims about work, and only a hit is a claim that work
    -- was skipped, which is what the reader is told.
    source TEXT NOT NULL DEFAULT 'run',
    PRIMARY KEY (branch_id, uid)
);

CREATE TABLE materializations (
    mat_id TEXT PRIMARY KEY,
    uid TEXT NOT NULL,
    version_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    memo_key TEXT NOT NULL,
    state TEXT NOT NULL,
    inputs TEXT NOT NULL,
    outputs TEXT NOT NULL,
    identity_dependent INTEGER NOT NULL,
    external INTEGER NOT NULL,
    env_lock_hash TEXT,
    cost_seconds REAL,
    log_ref TEXT,
    started_step INTEGER NOT NULL,
    finished_step INTEGER
);
CREATE INDEX materializations_memo ON materializations (memo_key, state);

CREATE TABLE transactions (
    step INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    intent TEXT NOT NULL,
    offline INTEGER NOT NULL,
    settled INTEGER NOT NULL,
    marker INTEGER NOT NULL DEFAULT 0,
    branch TEXT,
    ops TEXT NOT NULL
);

CREATE TABLE worktrees (
    path TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    actor TEXT,
    lock_holder TEXT
);

CREATE TABLE upload_queue (
    mat_id TEXT NOT NULL,
    output TEXT NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (mat_id, output)
);

CREATE TABLE workspace_tree (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    tree_hash TEXT NOT NULL,
    changed_paths TEXT NOT NULL,
    files TEXT NOT NULL,
    changed_step INTEGER NOT NULL
);

CREATE TABLE agent_sessions (
    actor TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    worktree INTEGER NOT NULL,
    begun_step INTEGER NOT NULL
);

CREATE TABLE value_pins (
    run_id TEXT NOT NULL,
    digest TEXT NOT NULL,
    PRIMARY KEY (run_id, digest)
);
"""


@dataclass(frozen=True)
class BranchRow:
    branch_id: str
    name: str
    parent_branch_id: str | None
    fork_step: int
    archived: bool


@dataclass(frozen=True)
class VersionRow:
    version_id: str
    uid: str
    slug: str
    definition_hash: str
    raw_source_ref: str
    bound_source_ref: str
    manifest: CellManifest
    flags: list[VersionFlag]
    parent_version_id: str | None
    author: str
    created_step: int


@dataclass(frozen=True)
class WorkspaceTreeRow:
    tree_hash: str
    changed_paths: list[str]
    files: dict[str, str]
    changed_step: int


@dataclass(frozen=True)
class EnvRow:
    lock_hash: str
    packages: dict[str, str]


@dataclass(frozen=True)
class AgentSessionRow:
    """A registered agent session. `worktree` ones hold the flow's files."""

    actor: str
    label: str
    worktree: bool
    begun_step: int


@dataclass(frozen=True)
class TransactionRow:
    """A journal line as the surfaces read it: who did what, and when."""

    step: int
    ts: str
    actor: str
    intent: str
    offline: bool
    settled: bool
    branch: str | None
    # Somebody marked this step on purpose, as opposed to `settled`, which the
    # commit computes. The two answer the same question from opposite ends.
    marker: bool = False


@dataclass(frozen=True)
class UploadRow:
    """One output's place in the upload queue. `done` carries its reference on
    the materialization, so the queue keeps only the state."""

    mat_id: str
    output: str
    state: str
    attempts: int


@dataclass(frozen=True)
class MaterializationRow:
    mat_id: str
    uid: str
    version_id: str
    branch_id: str
    memo_key: str
    state: MaterializationState
    inputs: dict[str, InputRef]
    outputs: dict[str, OutputRecord]
    identity_dependent: bool
    external: bool
    env_lock_hash: str | None
    cost_seconds: float | None
    log_ref: str | None
    started_step: int
    finished_step: int | None


class Index:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._schema_version = self._prepare()

    @classmethod
    def in_memory(cls) -> "Index":
        """A throwaway index — how as-of-step state is read back from a replay."""
        return cls(Path(":memory:"))

    @staticmethod
    def discard(path: Path) -> None:
        for suffix in ("", "-wal", "-shm"):
            path.with_name(path.name + suffix).unlink(missing_ok=True)

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @property
    def schema_version(self) -> int:
        return self._schema_version

    @property
    def last_step(self) -> int:
        if self._schema_version != INDEX_SCHEMA_VERSION:
            return 0
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'last_step'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def apply(self, transaction: Transaction) -> None:
        with self._lock, self._conn:
            self._apply(transaction)

    def rebuild(self, transactions: Iterable[Transaction]) -> None:
        with self._lock, self._conn:
            for transaction in transactions:
                self._apply(transaction)

    @contextmanager
    def probe(self, transaction: Transaction) -> Iterator["Index"]:
        """Read the index as if `transaction` had landed; every write rolls back.

        Facts about the state a transaction arrives at — `settled` is the one
        that matters — have to be known before the journal append that commits
        it, and folding the ops is the only honest way to know them.

        The savepoint owns the connection's transaction for its duration, so a
        probe expects no write already open on it and does not nest.
        """
        with self._lock:
            self._conn.execute("SAVEPOINT probe")
            try:
                self._apply(transaction)
                yield self
            finally:
                self._conn.execute("ROLLBACK TO probe")
                self._conn.execute("RELEASE probe")

    def branch(self, name: str) -> BranchRow | None:
        row = self._conn.execute(
            "SELECT * FROM branches WHERE name = ?", (name,)
        ).fetchone()
        return _branch(row) if row is not None else None

    def branch_by_id(self, branch_id: str) -> BranchRow | None:
        row = self._conn.execute(
            "SELECT * FROM branches WHERE branch_id = ?", (branch_id,)
        ).fetchone()
        return _branch(row) if row is not None else None

    def branches(self) -> list[BranchRow]:
        return [
            _branch(row)
            for row in self._conn.execute("SELECT * FROM branches ORDER BY fork_step")
        ]

    def selections(self, branch_id: str) -> dict[str, str]:
        return {
            row["uid"]: row["version_id"]
            for row in self._conn.execute(
                "SELECT uid, version_id FROM selections WHERE branch_id = ? "
                "ORDER BY uid",
                (branch_id,),
            )
        }

    def baselines(self, branch_id: str) -> dict[str, str]:
        return {
            row["uid"]: row["mat_id"]
            for row in self._conn.execute(
                "SELECT uid, mat_id FROM baselines WHERE branch_id = ? ORDER BY uid",
                (branch_id,),
            )
        }

    def reused_baselines(self, branch_id: str) -> set[str]:
        """Cells this branch observed without running them: a memo hit served it."""
        return {
            row["uid"]
            for row in self._conn.execute(
                "SELECT uid FROM baselines WHERE branch_id = ? AND source = 'hit'",
                (branch_id,),
            )
        }

    def baseline_branches(self, mat_id: str) -> int:
        """How many branches are live on this materialization.

        More than one means two branches read the same value, which under
        strict mode is what earns their consumers a defensive copy: the kernel
        caches a value once, and one branch mutating it in place would
        otherwise be handing the other a value it never produced.
        """
        row = self._conn.execute(
            "SELECT COUNT(*) AS branches FROM baselines WHERE mat_id = ?", (mat_id,)
        ).fetchone()
        return int(row["branches"]) if row is not None else 0

    def slice_versions(self, branch_id: str) -> dict[str, VersionRow]:
        """The branch's resolved slice: uid → the version it selects."""
        return {
            row["uid"]: _version(row)
            for row in self._conn.execute(
                "SELECT asset_versions.* FROM selections "
                "JOIN asset_versions USING (version_id) "
                "WHERE selections.branch_id = ? ORDER BY asset_versions.uid",
                (branch_id,),
            )
        }

    def version(self, version_id: str) -> VersionRow | None:
        row = self._conn.execute(
            "SELECT * FROM asset_versions WHERE version_id = ?", (version_id,)
        ).fetchone()
        return _version(row) if row is not None else None

    def materialization(self, mat_id: str) -> MaterializationRow | None:
        row = self._conn.execute(
            "SELECT * FROM materializations WHERE mat_id = ?", (mat_id,)
        ).fetchone()
        return _materialization(row) if row is not None else None

    def materializations_since(self, step: int) -> list[MaterializationRow]:
        """Runs that produced something after `step`, oldest first.

        Only the succeeded ones: a failure produced no bytes, and the caller
        asking is the uploader, which has nothing to publish for either.
        """
        rows = self._conn.execute(
            "SELECT * FROM materializations WHERE state = 'succeeded' "
            "AND COALESCE(finished_step, started_step) > ? "
            "ORDER BY COALESCE(finished_step, started_step)",
            (step,),
        ).fetchall()
        return [_materialization(row) for row in rows]

    def uploads(self, *, pending: bool = False) -> list[UploadRow]:
        """The upload queue. `pending` drops what already has its reference."""
        clause = "WHERE state != 'done' " if pending else ""
        rows = self._conn.execute(
            "SELECT mat_id, output, state, attempts FROM upload_queue "
            f"{clause}ORDER BY mat_id, output"
        ).fetchall()
        return [
            UploadRow(
                mat_id=row["mat_id"],
                output=row["output"],
                state=row["state"],
                attempts=int(row["attempts"]),
            )
            for row in rows
        ]

    def knows_cell(self, uid: str) -> bool:
        """Has this store ever minted or observed the cell? Deleting it from a
        branch drops the selection, not the cell."""
        row = self._conn.execute("SELECT 1 FROM cells WHERE uid = ?", (uid,)).fetchone()
        return row is not None

    def creation_steps(self) -> dict[str, int]:
        """The step each cell was minted at — the order the notebook ties on.

        Read for the whole store rather than per cell: a slice asks for all of
        them at once, and the mint order is what pins card order against a
        rename, which sorting by slug would move.
        """
        rows = self._conn.execute("SELECT uid, created_step FROM cells").fetchall()
        return {str(row["uid"]): int(row["created_step"]) for row in rows}

    def selection(self, branch_id: str, uid: str) -> str | None:
        row = self._conn.execute(
            "SELECT version_id FROM selections WHERE branch_id = ? AND uid = ?",
            (branch_id, uid),
        ).fetchone()
        return str(row["version_id"]) if row is not None else None

    def pinned(self, branch_id: str) -> set[str]:
        """Cells this branch is holding at the version it forked with.

        Pin-at-fork is the only v1 mode, so this is exactly the set the branch
        inherited and has not re-authored since — what tells a difference the
        branch chose from one it merely never picked up.
        """
        return {
            str(row["uid"])
            for row in self._conn.execute(
                "SELECT uid FROM selections WHERE branch_id = ? AND pinned = 1",
                (branch_id,),
            )
        }

    def workspace_code_step(self) -> int:
        """The step the watched workspace code last changed under, 0 if never."""
        row = self._conn.execute("SELECT changed_step FROM workspace_tree").fetchone()
        return int(row["changed_step"]) if row is not None else 0

    def workspace_tree(self) -> WorkspaceTreeRow | None:
        """The shared code every behavior hash is taken against, if any is known."""
        row = self._conn.execute("SELECT * FROM workspace_tree").fetchone()
        if row is None:
            return None
        return WorkspaceTreeRow(
            tree_hash=row["tree_hash"],
            changed_paths=json.loads(row["changed_paths"]),
            files=json.loads(row["files"]),
            changed_step=int(row["changed_step"]),
        )

    def agent_sessions(self) -> list[AgentSessionRow]:
        """Registered agent sessions that have not ended, newest first."""
        return [
            AgentSessionRow(
                actor=row["actor"],
                label=row["label"],
                worktree=bool(row["worktree"]),
                begun_step=int(row["begun_step"]),
            )
            for row in self._conn.execute(
                "SELECT * FROM agent_sessions ORDER BY begun_step DESC"
            )
        ]

    def worktree_holder(self) -> AgentSessionRow | None:
        """The agent session the flow's files belong to while it lasts."""
        return next(
            (session for session in self.agent_sessions() if session.worktree), None
        )

    def history(
        self, *, limit: int = 20, branch_id: str | None = None, shared: bool = False
    ) -> list[TransactionRow]:
        """The most recent transactions, newest first — what happened, in words.

        `shared` folds in the lines that carry no branch — a shared-code edit, an
        env change, an agent session opening. They are context for a branch, not
        something that happened to it, so what asks for "this branch's last
        intent" leaves them out and what asks "what has been going on" does not.
        """
        where = ""
        arguments: tuple[object, ...] = (limit,)
        if branch_id is not None:
            where = (
                "WHERE branch IS NULL OR branch = ?" if shared else "WHERE branch = ?"
            )
            arguments = (branch_id, limit)
        return [
            _transaction(row)
            for row in self._conn.execute(
                f"SELECT * FROM transactions {where} ORDER BY step DESC LIMIT ?",
                arguments,
            )
        ]

    def checkpoint(self, branch_id: str) -> TransactionRow | None:
        """The branch's last marked or settled step.

        Two ways of arriving at the same question. `settled` is the commit's
        own verdict — a whole slice, nothing unsynced — and a marker is
        somebody saying this point mattered whether or not it was whole. The
        newest of the two wins, rather than one class of answer permanently
        outranking the other: a branch settled ten steps after it was marked
        has moved on, and a branch marked after it settled has been spoken for.
        """
        row = self._conn.execute(
            "SELECT * FROM transactions "
            "WHERE branch = ? AND (settled = 1 OR marker = 1) "
            "ORDER BY step DESC LIMIT 1",
            (branch_id,),
        ).fetchone()
        return _transaction(row) if row is not None else None

    def transaction(self, step: int) -> TransactionRow | None:
        """One journal line by step — what a version was accepted under."""
        row = self._conn.execute(
            "SELECT * FROM transactions WHERE step = ?", (step,)
        ).fetchone()
        return _transaction(row) if row is not None else None

    def transaction_flags(self, step: int) -> list[str]:
        """Flags a transaction raised over itself rather than over a version.

        Attribution uncertainty is one of these: a mixed editing window is a
        property of the window, not of any cell that landed in it, so it rides
        the line and nothing copies it onto the versions.
        """
        row = self._conn.execute(
            "SELECT ops FROM transactions WHERE step = ?", (step,)
        ).fetchone()
        if row is None:
            return []
        return [
            str(op["flag"])
            for op in json.loads(row["ops"])
            if op.get("op") == "flag_set" and op.get("version_id") is None
        ]

    def first_version(self, uid: str) -> VersionRow | None:
        """The version a cell was born as — who created it, and when."""
        row = self._conn.execute(
            "SELECT * FROM asset_versions WHERE uid = ? "
            "ORDER BY created_step, version_id LIMIT 1",
            (uid,),
        ).fetchone()
        return _version(row) if row is not None else None

    def version_by_source(self, uid: str, raw_source_ref: str) -> VersionRow | None:
        """A version of that cell whose file bytes these are, newest first."""
        row = self._conn.execute(
            "SELECT * FROM asset_versions WHERE uid = ? AND raw_source_ref = ? "
            "ORDER BY created_step DESC, version_id DESC LIMIT 1",
            (uid, raw_source_ref),
        ).fetchone()
        return _version(row) if row is not None else None

    def env_lock_hash(self) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'env_lock_hash'"
        ).fetchone()
        return str(row["value"]) if row is not None else None

    def env(self) -> EnvRow | None:
        """The env this flow last observed — the hash, and what it pinned."""
        found = self.env_lock_hash()
        if found is None:
            return None
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'env_packages'"
        ).fetchone()
        return EnvRow(
            lock_hash=found,
            packages=json.loads(row["value"]) if row is not None else {},
        )

    def memo_candidates(self, memo_key: str) -> list[MaterializationRow]:
        """Succeeded materializations of that key, newest first — every branch's.

        Cross-branch hits are the same lookup, not a special case: a key that
        matches means the same code ran on the same inputs, whoever asked.
        """
        return [
            _materialization(row)
            for row in self._conn.execute(
                "SELECT * FROM materializations WHERE memo_key = ? "
                "AND state = 'succeeded' ORDER BY started_step DESC, mat_id DESC",
                (memo_key,),
            )
        ]

    def last_cost(self, uid: str) -> float | None:
        """What the cell took last time it ran — the only cost estimate there is."""
        row = self._conn.execute(
            "SELECT cost_seconds FROM materializations WHERE uid = ? "
            "AND state = 'succeeded' AND cost_seconds IS NOT NULL "
            "ORDER BY started_step DESC, mat_id DESC LIMIT 1",
            (uid,),
        ).fetchone()
        return float(row["cost_seconds"]) if row is not None else None

    def worktree_branch(self, path: str) -> str | None:
        row = self._conn.execute(
            "SELECT branch_id FROM worktrees WHERE path = ?", (path,)
        ).fetchone()
        return str(row["branch_id"]) if row is not None else None

    def pin_values(self, run_id: str, digests: Iterable[str]) -> None:
        """Hold a run's values against the sweep until its transaction lands.

        Pins are in-flight state, deliberately outside the journal fold: a
        rebuild drops them, which is correct — nothing is in flight then.
        """
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT OR IGNORE INTO value_pins (run_id, digest) VALUES (?, ?)",
                [(run_id, digest) for digest in digests],
            )

    def release_values(self, run_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM value_pins WHERE run_id = ?", (run_id,))

    def pinned_values(self) -> set[str]:
        return {
            row["digest"] for row in self._conn.execute("SELECT digest FROM value_pins")
        }

    def close(self) -> None:
        self._conn.close()

    def _prepare(self) -> int:
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            existing = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'"
            ).fetchone()
            if existing is None:
                self._conn.executescript(_SCHEMA)
                self._set_meta("schema_version", str(INDEX_SCHEMA_VERSION))
                self._conn.commit()
                return INDEX_SCHEMA_VERSION
            stored = self._conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            return int(stored["value"]) if stored else -1
        except (sqlite3.DatabaseError, ValueError):
            return -1

    def _set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def _apply(self, transaction: Transaction) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO transactions "
            "(step, ts, actor, intent, offline, settled, marker, branch, ops) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                transaction.step,
                transaction.ts,
                transaction.actor,
                transaction.intent,
                int(transaction.offline),
                int(transaction.settled),
                int(any(isinstance(op, Checkpointed) for op in transaction.ops)),
                transaction.branch,
                _dump([op.model_dump(mode="json") for op in transaction.ops]),
            ),
        )
        for op in transaction.ops:
            self._apply_op(op, transaction.step)
        self._set_meta("last_step", str(transaction.step))

    def _apply_op(self, op: Op, step: int) -> None:
        match op:
            case FlowInit():
                self._set_meta("flow_id", op.flow_id)
            case CellAccepted():
                self._accept_cell(op, step)
            case CellRemoved():
                self._conn.execute(
                    "DELETE FROM selections WHERE branch_id = ? AND uid = ?",
                    (op.branch_id, op.uid),
                )
                self._conn.execute(
                    "DELETE FROM baselines WHERE branch_id = ? AND uid = ?",
                    (op.branch_id, op.uid),
                )
            case SelectionSet():
                self._select(op.branch_id, op.uid, op.version_id, op.pinned)
            case Adopted():
                self._select(op.branch_id, op.uid, op.version_id, pinned=False)
            case BranchCreated():
                self._conn.execute(
                    "INSERT OR REPLACE INTO branches "
                    "(branch_id, name, parent_branch_id, fork_step, archived) "
                    "VALUES (?, ?, ?, ?, 0)",
                    (op.branch_id, op.name, op.parent_branch_id, op.fork_step),
                )
                if op.parent_branch_id is not None:
                    self._dense_copy(op.branch_id, op.parent_branch_id)
            case BranchArchived():
                self._conn.execute(
                    "UPDATE branches SET archived = 1 WHERE branch_id = ?",
                    (op.branch_id,),
                )
            case WorktreeBound():
                self._conn.execute(
                    "INSERT INTO worktrees (path, branch_id, actor) VALUES (?, ?, ?) "
                    "ON CONFLICT(path) DO UPDATE SET "
                    "branch_id = excluded.branch_id, actor = excluded.actor",
                    (op.path, op.branch_id, op.actor),
                )
            case Rewound():
                self._rewind(op)
            case RunRecorded():
                self._record_run(op)
            case MemoHit():
                self._set_baseline(op.branch_id, op.uid, op.mat_id, "hit")
            case WorkspaceCodeChanged():
                self._conn.execute(
                    "INSERT INTO workspace_tree "
                    "(id, tree_hash, changed_paths, files, changed_step) "
                    "VALUES (1, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                    "tree_hash = excluded.tree_hash, "
                    "changed_paths = excluded.changed_paths, "
                    "files = excluded.files, "
                    "changed_step = excluded.changed_step",
                    (op.tree_hash, _dump(op.changed_paths), _dump(op.files), step),
                )
            case EnvChanged():
                self._set_meta("env_lock_hash", op.lock_hash)
                self._set_meta("env_packages", _dump(op.packages))
            case UploadStateChanged():
                self._set_upload(op.mat_id, op.output, op.state, op.attempts)
            case UploadRecorded():
                self._record_upload(op)
            case FlagSet():
                self._flag_version(op)
            case AgentBegin():
                self._conn.execute(
                    "INSERT OR REPLACE INTO agent_sessions "
                    "(actor, label, worktree, begun_step) VALUES (?, ?, ?, ?)",
                    (op.actor, op.label, int(op.worktree), step),
                )
            case AgentEnd():
                self._conn.execute(
                    "DELETE FROM agent_sessions WHERE actor = ?", (op.actor,)
                )
            # The marker rides the transaction row itself — there is no state
            # for it to fold into, which is the whole point of a marker.
            case SecretRefAdded() | Renamed() | Checkpointed():
                pass

    def _accept_cell(self, op: CellAccepted, step: int) -> None:
        self._conn.execute(
            "INSERT INTO cells (uid, created_step, copied_from) VALUES (?, ?, ?) "
            "ON CONFLICT(uid) DO NOTHING",
            (op.uid, step, op.copied_from),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO asset_versions "
            "(version_id, uid, slug, definition_hash, raw_source_ref, "
            "bound_source_ref, manifest, flags, parent_version_id, author, "
            "created_step) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                op.version_id,
                op.uid,
                op.slug,
                op.definition_hash,
                op.raw_source_ref,
                op.bound_source_ref,
                _dump(op.manifest.model_dump(mode="json")),
                _dump([flag.model_dump(mode="json") for flag in op.flags]),
                op.parent_version_id,
                op.author,
                step,
            ),
        )

    def _dense_copy(self, branch_id: str, parent_branch_id: str) -> None:
        """Fork the parent's slice into the new branch: selections and baselines.

        The copy lives in the fold rather than in journaled ops so a fork costs
        one op no matter how wide the slice is, and so a rebuild reproduces it
        from the parent's state at exactly the fork step. Copies are pinned —
        pin-at-fork is the only v1 mode, so a sweep stays comparable.
        """
        self._conn.execute(
            "INSERT OR REPLACE INTO selections (branch_id, uid, version_id, pinned) "
            "SELECT ?, uid, version_id, 1 FROM selections WHERE branch_id = ?",
            (branch_id, parent_branch_id),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO baselines (branch_id, uid, mat_id, source) "
            "SELECT ?, uid, mat_id, 'fork' FROM baselines WHERE branch_id = ?",
            (branch_id, parent_branch_id),
        )

    def _select(self, branch_id: str, uid: str, version_id: str, pinned: bool) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO selections (branch_id, uid, version_id, pinned) "
            "VALUES (?, ?, ?, ?)",
            (branch_id, uid, version_id, int(pinned)),
        )

    def _set_baseline(
        self, branch_id: str, uid: str, mat_id: str, source: str = "run"
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO baselines (branch_id, uid, mat_id, source) "
            "VALUES (?, ?, ?, ?)",
            (branch_id, uid, mat_id, source),
        )

    def _rewind(self, op: Rewound) -> None:
        self._conn.execute(
            "DELETE FROM selections WHERE branch_id = ?", (op.branch_id,)
        )
        self._conn.execute("DELETE FROM baselines WHERE branch_id = ?", (op.branch_id,))
        for uid, version_id in op.selections.items():
            self._select(op.branch_id, uid, version_id, pinned=False)
        for uid, mat_id in op.baselines.items():
            # The journal carries which materialization the branch held, not how
            # it came by it; saying "rewind" is the honest end of that.
            self._set_baseline(op.branch_id, uid, mat_id, "rewind")

    def _record_run(self, op: RunRecorded) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO materializations "
            "(mat_id, uid, version_id, branch_id, memo_key, state, inputs, outputs, "
            "identity_dependent, external, env_lock_hash, cost_seconds, log_ref, "
            "started_step, finished_step) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                op.mat_id,
                op.uid,
                op.version_id,
                op.branch_id,
                op.memo_key,
                op.state,
                _dump(
                    {
                        name: ref.model_dump(mode="json")
                        for name, ref in op.inputs.items()
                    }
                ),
                _dump(
                    {
                        name: record.model_dump(mode="json")
                        for name, record in op.outputs.items()
                    }
                ),
                int(op.identity_dependent),
                int(op.external),
                op.env_lock_hash,
                op.cost_seconds,
                op.log_ref,
                op.started_step,
                op.finished_step,
            ),
        )
        if op.state in ("succeeded", "failed"):
            # The baseline is the last materialization *observed*, not the last
            # that worked: a failure is what the branch now knows about the
            # cell, and staleness derives `failed` from it. A cancelled or
            # still-running record observed nothing and leaves it standing.
            self._set_baseline(op.branch_id, op.uid, op.mat_id)

    def _set_upload(self, mat_id: str, output: str, state: str, attempts: int) -> None:
        self._conn.execute(
            "INSERT INTO upload_queue (mat_id, output, state, attempts) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(mat_id, output) DO UPDATE SET "
            "state = excluded.state, attempts = excluded.attempts",
            (mat_id, output, state, attempts),
        )

    def _record_upload(self, op: UploadRecorded) -> None:
        row = self._conn.execute(
            "SELECT outputs FROM materializations WHERE mat_id = ?", (op.mat_id,)
        ).fetchone()
        if row is not None:
            outputs = json.loads(row["outputs"])
            record = outputs.get(op.output)
            if record is not None:
                record["luml_ref"] = op.ref.model_dump(mode="json")
                self._conn.execute(
                    "UPDATE materializations SET outputs = ? WHERE mat_id = ?",
                    (_dump(outputs), op.mat_id),
                )
        self._conn.execute(
            "INSERT INTO upload_queue (mat_id, output, state, attempts) "
            "VALUES (?, ?, 'done', 0) ON CONFLICT(mat_id, output) DO UPDATE SET "
            "state = 'done'",
            (op.mat_id, op.output),
        )

    def _flag_version(self, op: FlagSet) -> None:
        if op.version_id is None:
            return
        row = self._conn.execute(
            "SELECT flags FROM asset_versions WHERE version_id = ?", (op.version_id,)
        ).fetchone()
        if row is None:
            return
        flags = json.loads(row["flags"])
        flags.append({"code": op.flag, "detail": op.detail})
        self._conn.execute(
            "UPDATE asset_versions SET flags = ? WHERE version_id = ?",
            (_dump(flags), op.version_id),
        )


def _dump(value: object) -> str:
    return canonical_json(value).decode()


def _branch(row: sqlite3.Row) -> BranchRow:
    return BranchRow(
        branch_id=row["branch_id"],
        name=row["name"],
        parent_branch_id=row["parent_branch_id"],
        fork_step=row["fork_step"],
        archived=bool(row["archived"]),
    )


def _version(row: sqlite3.Row) -> VersionRow:
    return VersionRow(
        version_id=row["version_id"],
        uid=row["uid"],
        slug=row["slug"],
        definition_hash=row["definition_hash"],
        raw_source_ref=row["raw_source_ref"],
        bound_source_ref=row["bound_source_ref"],
        manifest=CellManifest.model_validate_json(row["manifest"]),
        flags=[VersionFlag.model_validate(flag) for flag in json.loads(row["flags"])],
        parent_version_id=row["parent_version_id"],
        author=row["author"],
        created_step=row["created_step"],
    )


def _transaction(row: sqlite3.Row) -> TransactionRow:
    return TransactionRow(
        step=int(row["step"]),
        ts=row["ts"],
        actor=row["actor"],
        intent=row["intent"],
        offline=bool(row["offline"]),
        settled=bool(row["settled"]),
        branch=row["branch"],
        marker=bool(row["marker"]),
    )


def _materialization(row: sqlite3.Row) -> MaterializationRow:
    return MaterializationRow(
        mat_id=row["mat_id"],
        uid=row["uid"],
        version_id=row["version_id"],
        branch_id=row["branch_id"],
        memo_key=row["memo_key"],
        state=row["state"],
        inputs={
            name: InputRef.model_validate(ref)
            for name, ref in json.loads(row["inputs"]).items()
        },
        outputs={
            name: OutputRecord.model_validate(record)
            for name, record in json.loads(row["outputs"]).items()
        },
        identity_dependent=bool(row["identity_dependent"]),
        external=bool(row["external"]),
        env_lock_hash=row["env_lock_hash"],
        cost_seconds=row["cost_seconds"],
        log_ref=row["log_ref"],
        started_step=row["started_step"],
        finished_step=row["finished_step"],
    )
