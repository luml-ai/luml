"""The SQLite index — a materialized view of the journal, never truth.

Applying a transaction is a pure fold: every op carries the facts its rows
need. That is what makes a full rebuild from the journal equivalent to the
incremental path, and why a missing, stale, or corrupt index is only ever a
latency problem.
"""

import json
import sqlite3
import threading
from collections.abc import Collection, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from lumlflow.flow.hashing import canonical_json
from lumlflow.flow.store.models import (
    AUTO_ACTOR,
    Adopted,
    AgentBegin,
    AgentEnd,
    BranchArchived,
    BranchCreated,
    CellAccepted,
    CellManifest,
    CellNoted,
    CellNoteKind,
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
    SelectionSet,
    Transaction,
    VersionFlag,
    WorkspaceCodeChanged,
    WorktreeBound,
)

INDEX_SCHEMA_VERSION = 15

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
    parent_step INTEGER,
    archived INTEGER NOT NULL DEFAULT 0,
    -- Where the branch stands. NULL means its newest own step; a rewind sets
    -- it, and the next change on the branch clears it.
    head_step INTEGER,
    -- The last verb that rewrote this branch's files, and the line it landed on.
    rewrite_verb TEXT,
    rewrite_step INTEGER
);

CREATE TABLE selections (
    branch_id TEXT NOT NULL,
    uid TEXT NOT NULL,
    version_id TEXT NOT NULL,
    slug TEXT NOT NULL,
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
    experiment_id TEXT,
    experiment_store TEXT,
    sdk_version_warning TEXT,
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
    mark TEXT,
    -- A step the branch can stand on: the line changed what the branch
    -- selects. Binding the files, noting a cell or an agent checking in
    -- are lines of the branch's history, not places in it.
    position INTEGER NOT NULL DEFAULT 1,
    branch TEXT,
    ops TEXT NOT NULL
);

CREATE TABLE cell_notes (
    branch_id TEXT NOT NULL,
    uid TEXT NOT NULL,
    kind TEXT NOT NULL,
    sentence TEXT NOT NULL,
    version_id TEXT,
    step INTEGER NOT NULL,
    actor TEXT NOT NULL,
    PRIMARY KEY (branch_id, uid, kind, step)
);

CREATE TABLE worktrees (
    flow_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    actor TEXT,
    lock_holder TEXT
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
    #: The parent's own step this branch copied, when the fork line recorded it.
    parent_step: int | None = None
    #: Where the branch stands when that is not its newest own step: a rewind
    #: sets it, the next change on the branch clears it.
    head_step: int | None = None


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
    actor: str
    label: str
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
    #: The words the step was marked under; the intent stays what it was.
    mark: str | None = None
    #: Whether the branch can stand on this line — it changed what the branch
    #: selects. A checkout or a note is history, not a place.
    position: bool = True


CellsRewriteVerb = Literal["use", "rewind", "adopt"]


@dataclass(frozen=True)
class CellsRewriteRow:
    verb: CellsRewriteVerb
    step: int


@dataclass(frozen=True)
class CellNoteRow:
    branch_id: str
    uid: str
    kind: CellNoteKind
    sentence: str
    version_id: str | None
    step: int
    actor: str


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
    experiment_id: str | None
    experiment_store: str | None
    sdk_version_warning: str | None
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

    def slice_versions(self, branch_id: str) -> dict[str, VersionRow]:
        """The branch's resolved slice: uid → the version it selects."""
        return {
            row["uid"]: _version(row)
            for row in self._conn.execute(
                "SELECT asset_versions.*, selections.slug AS selected_slug "
                "FROM selections "
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

    def selected_slugs(self) -> list[tuple[str, str]]:
        rows = self._conn.execute(
            "SELECT DISTINCT slug, uid FROM selections ORDER BY slug, uid"
        ).fetchall()
        return [(str(row["slug"]), str(row["uid"])) for row in rows]

    def version_slugs(self) -> set[str]:
        rows = self._conn.execute("SELECT DISTINCT slug FROM asset_versions").fetchall()
        return {str(row["slug"]) for row in rows}

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

    def env_changed_step(self) -> int:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'env_changed_step'"
        ).fetchone()
        return int(row["value"]) if row is not None else 0

    def selection_changed_after(
        self, branch_id: str, uids: Collection[str], step: int
    ) -> bool:
        if not uids:
            return False
        wanted = set(uids)
        for row in self._conn.execute(
            "SELECT ops FROM transactions WHERE branch = ? AND step > ? ORDER BY step",
            (branch_id, step),
        ):
            for op in json.loads(row["ops"]):
                kind = op.get("op")
                if kind == "rewound":
                    if op.get("branch_id") == branch_id and wanted.intersection(
                        op.get("selections") or {}
                    ):
                        return True
                    continue
                if kind not in {"selection_set", "adopted", "cell_removed"}:
                    continue
                if op.get("branch_id") == branch_id and op.get("uid") in wanted:
                    return True
        return False

    def explicit_run_after(self, branch_id: str, uid: str, step: int) -> bool:
        for row in self._conn.execute(
            "SELECT ops FROM transactions WHERE branch = ? AND actor != 'auto' "
            "AND step > ? ORDER BY step",
            (branch_id, step),
        ):
            if any(
                op.get("op") in {"run_recorded", "memo_hit"}
                and op.get("branch_id") == branch_id
                and op.get("uid") == uid
                for op in json.loads(row["ops"])
            ):
                return True
        return False

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
                begun_step=int(row["begun_step"]),
            )
            for row in self._conn.execute(
                "SELECT * FROM agent_sessions ORDER BY begun_step DESC"
            )
        ]

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

    def last_cells_rewrite(self, branch_id: str) -> CellsRewriteRow | None:
        row = self._conn.execute(
            "SELECT rewrite_verb, rewrite_step FROM branches WHERE branch_id = ?",
            (branch_id,),
        ).fetchone()
        if row is None or row["rewrite_verb"] is None:
            return None
        verb: CellsRewriteVerb = row["rewrite_verb"]
        return CellsRewriteRow(verb=verb, step=int(row["rewrite_step"]))

    def head(self, branch_id: str) -> TransactionRow | None:
        """The step the branch stands on: its own line at its position.

        The newest own line unless a rewind moved the branch back — then the
        line it was moved to, or the branch's newest own line before it when
        the target was not one of its own.
        """
        branch = self.branch_by_id(branch_id)
        if branch is None:
            return None
        if branch.head_step is not None:
            found = self.transaction(branch.head_step)
            if found is not None and found.branch == branch_id and found.position:
                return found
            step = self.last_step_on(branch_id, at_or_before=branch.head_step)
            return self.transaction(step) if step is not None else None
        return self._newest_position(branch_id)

    def _newest_position(self, branch_id: str) -> TransactionRow | None:
        row = self._conn.execute(
            "SELECT * FROM transactions WHERE branch = ? AND position = 1 "
            "ORDER BY step DESC LIMIT 1",
            (branch_id,),
        ).fetchone()
        return _transaction(row) if row is not None else None

    def head_step(self, branch_id: str) -> int:
        """Where the branch stands, as a step: its fork step with no own line."""
        found = self.head(branch_id)
        if found is not None:
            return found.step
        branch = self.branch_by_id(branch_id)
        return branch.fork_step if branch is not None else 0

    def newest_step(self, branch_id: str) -> int:
        """The branch's newest own position — where it would stand if not rewound."""
        newest = self._newest_position(branch_id)
        if newest is not None:
            return newest.step
        branch = self.branch_by_id(branch_id)
        return branch.fork_step if branch is not None else 0

    def last_step_on(self, branch_id: str, *, at_or_before: int) -> int | None:
        """The branch's newest own position at or before a global step.

        This is the state a fork copied from the branch.
        """
        row = self._conn.execute(
            "SELECT step FROM transactions WHERE branch = ? AND step <= ? "
            "AND position = 1 ORDER BY step DESC LIMIT 1",
            (branch_id, at_or_before),
        ).fetchone()
        return int(row["step"]) if row is not None else None

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

    def cell_notes(self, branch_id: str, uid: str) -> list[CellNoteRow]:
        """The newest note of every kind for a cell on one lane."""
        rows = self._conn.execute(
            "SELECT * FROM cell_notes WHERE branch_id = ? AND uid = ? "
            "ORDER BY step DESC, kind",
            (branch_id, uid),
        )
        latest: dict[CellNoteKind, CellNoteRow] = {}
        for row in rows:
            note = _cell_note(row)
            latest.setdefault(note.kind, note)
        return list(latest.values())

    def first_version(self, uid: str) -> VersionRow | None:
        """The version a cell was born as — who created it, and when."""
        row = self._conn.execute(
            "SELECT * FROM asset_versions WHERE uid = ? "
            "ORDER BY created_step, version_id LIMIT 1",
            (uid,),
        ).fetchone()
        return _version(row) if row is not None else None

    def version_by_source(
        self,
        uid: str,
        raw_source_ref: str,
        *,
        version_ids: Collection[str],
    ) -> VersionRow | None:
        """The newest matching version among the supplied version ids."""
        rows = self._conn.execute(
            "SELECT * FROM asset_versions WHERE uid = ? AND raw_source_ref = ? "
            "ORDER BY created_step DESC, version_id DESC",
            (uid, raw_source_ref),
        )
        for row in rows:
            if row["version_id"] in version_ids:
                return _version(row)
        return None

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

    def worktree_branch(self, flow_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT branch_id FROM worktrees WHERE flow_id = ?", (flow_id,)
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

    @contextmanager
    def protect_value_sweep(self) -> Iterator[set[str]]:
        """Keep a new run from adopting a candidate while it is unlinked."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield {
                    row["digest"]
                    for row in self._conn.execute("SELECT digest FROM value_pins")
                }
            finally:
                self._conn.rollback()

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
        # A line that only marks another step, or moves the branch to one, is
        # not a step: it gets no row of its own, and what it says folds onto the
        # branch or the row it names.
        if not is_annotation(transaction):
            self._conn.execute(
                "INSERT OR REPLACE INTO transactions "
                "(step, ts, actor, intent, offline, settled, position, branch, ops) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    transaction.step,
                    transaction.ts,
                    transaction.actor,
                    transaction.intent,
                    int(transaction.offline),
                    int(transaction.settled),
                    int(is_position(transaction)),
                    transaction.branch,
                    _dump([op.model_dump(mode="json") for op in transaction.ops]),
                ),
            )
        for op in transaction.ops:
            self._apply_op(op, transaction)
        # A change lands on the branch's newest position, so that is where it
        # stands now — whatever a rewind had set before.
        if (
            transaction.branch is not None
            and is_position(transaction)
            and any(isinstance(op, _MOVING) for op in transaction.ops)
        ):
            self._conn.execute(
                "UPDATE branches SET head_step = NULL WHERE branch_id = ?",
                (transaction.branch,),
            )
        self._set_meta("last_step", str(transaction.step))

    def _apply_op(self, op: Op, transaction: Transaction) -> None:
        step = transaction.step
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
            case CellNoted():
                if transaction.branch is None:
                    raise ValueError("cell notes require a lane-scoped transaction")
                self._conn.execute(
                    "INSERT OR REPLACE INTO cell_notes "
                    "(branch_id, uid, kind, sentence, version_id, step, actor) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        transaction.branch,
                        op.uid,
                        op.kind,
                        op.sentence,
                        op.version_id,
                        step,
                        transaction.actor,
                    ),
                )
            case SelectionSet():
                self._select(op.branch_id, op.uid, op.version_id, op.pinned)
            case Adopted():
                incoming = self._conn.execute(
                    "SELECT slug FROM selections WHERE branch_id = ? AND uid = ?",
                    (op.from_branch_id, op.uid),
                ).fetchone()
                self._select(
                    op.branch_id,
                    op.uid,
                    op.version_id,
                    pinned=False,
                    slug=str(incoming["slug"]) if incoming is not None else None,
                )
                self._conn.execute(
                    "UPDATE branches SET rewrite_verb = 'adopt', rewrite_step = ? "
                    "WHERE branch_id = ?",
                    (step, op.branch_id),
                )
            case BranchCreated():
                self._conn.execute(
                    "INSERT OR REPLACE INTO branches "
                    "(branch_id, name, parent_branch_id, fork_step, parent_step, "
                    "archived) VALUES (?, ?, ?, ?, ?, 0)",
                    (
                        op.branch_id,
                        op.name,
                        op.parent_branch_id,
                        op.fork_step,
                        op.parent_step,
                    ),
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
                    "INSERT INTO worktrees (flow_id, branch_id, actor) "
                    "VALUES (?, ?, ?) "
                    "ON CONFLICT(flow_id) DO UPDATE SET "
                    "branch_id = excluded.branch_id, actor = excluded.actor",
                    (op.flow_id, op.branch_id, op.actor),
                )
                self._conn.execute(
                    "UPDATE branches SET rewrite_verb = 'use', rewrite_step = ? "
                    "WHERE branch_id = ?",
                    (step, op.branch_id),
                )
            case Rewound():
                self._rewind(op)
                self._conn.execute(
                    "UPDATE branches SET head_step = ?, rewrite_verb = 'rewind', "
                    "rewrite_step = ? WHERE branch_id = ?",
                    (op.to_step, step, op.branch_id),
                )
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
                self._set_meta("env_changed_step", str(step))
            case FlagSet():
                self._flag_version(op)
            case AgentBegin():
                self._conn.execute(
                    "INSERT OR REPLACE INTO agent_sessions "
                    "(actor, label, begun_step) VALUES (?, ?, ?)",
                    (op.actor, op.label, step),
                )
            case AgentEnd():
                self._conn.execute(
                    "DELETE FROM agent_sessions WHERE actor = ?", (op.actor,)
                )
            case Renamed():
                self._conn.execute(
                    "UPDATE selections SET slug = ? WHERE branch_id = ? AND uid = ?",
                    (op.new_slug, op.branch_id, op.uid),
                )
            # The mark rides the row it names, under the marking line's own
            # words. Marking the same step again replaces the words. A line
            # from before marks folded names no step: it rides the position
            # the branch stood on when it was written.
            case Checkpointed():
                target = (
                    op.step
                    if op.step is not None
                    else self.last_step_on(op.branch_id, at_or_before=step)
                )
                if target is not None:
                    self._conn.execute(
                        "UPDATE transactions SET marker = 1, mark = ? "
                        "WHERE step = ? AND branch = ?",
                        (transaction.intent, target, op.branch_id),
                    )

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
            "INSERT OR REPLACE INTO selections "
            "(branch_id, uid, version_id, slug, pinned) "
            "SELECT ?, uid, version_id, slug, 1 FROM selections WHERE branch_id = ?",
            (branch_id, parent_branch_id),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO baselines (branch_id, uid, mat_id, source) "
            "SELECT ?, uid, mat_id, 'fork' FROM baselines WHERE branch_id = ?",
            (branch_id, parent_branch_id),
        )

    def _select(
        self,
        branch_id: str,
        uid: str,
        version_id: str,
        pinned: bool,
        *,
        slug: str | None = None,
    ) -> None:
        if slug is None:
            row = self._conn.execute(
                "SELECT slug FROM asset_versions WHERE version_id = ?", (version_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown version `{version_id}`")
            slug = str(row["slug"])
        self._conn.execute(
            "INSERT OR REPLACE INTO selections "
            "(branch_id, uid, version_id, slug, pinned) VALUES (?, ?, ?, ?, ?)",
            (branch_id, uid, version_id, slug, int(pinned)),
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
            self._select(
                op.branch_id,
                uid,
                version_id,
                pinned=False,
                slug=op.slugs.get(uid),
            )
        for uid, mat_id in op.baselines.items():
            # The journal carries which materialization the branch held, not how
            # it came by it; saying "rewind" is the honest end of that.
            self._set_baseline(op.branch_id, uid, mat_id, "rewind")

    def _record_run(self, op: RunRecorded) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO materializations "
            "(mat_id, uid, version_id, branch_id, memo_key, state, inputs, outputs, "
            "identity_dependent, external, env_lock_hash, cost_seconds, log_ref, "
            "experiment_id, experiment_store, sdk_version_warning, started_step, "
            "finished_step) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                op.experiment_id,
                op.experiment_store,
                op.sdk_version_warning,
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
        parent_step=row["parent_step"],
        head_step=row["head_step"],
    )


def _version(row: sqlite3.Row) -> VersionRow:
    return VersionRow(
        version_id=row["version_id"],
        uid=row["uid"],
        slug=(row["selected_slug"] if "selected_slug" in row.keys() else row["slug"]),
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
        mark=row["mark"],
        position=bool(row["position"]),
    )


#: The ops that move a branch: after one lands, the branch stands on its newest
#: line. Binding the files, noting a cell or flagging a version leave it where
#: it was, which after a rewind is somewhere behind.
_MOVING = (
    CellAccepted,
    CellRemoved,
    SelectionSet,
    Adopted,
    Renamed,
    RunRecorded,
    MemoHit,
)


#: Lines that are a branch's history without being places in it: nothing the
#: branch selects changed, so there is nothing there to stand on or go back to.
_NOT_A_PLACE = (
    WorktreeBound,
    CellNoted,
    FlagSet,
    AgentBegin,
    AgentEnd,
    WorkspaceCodeChanged,
    EnvChanged,
    BranchArchived,
    Checkpointed,
    Rewound,
)


def is_position(transaction: Transaction) -> bool:
    """Whether a branch can stand on this line: somebody changed what it
    selects or holds. What reactivity did on its own keeps the branch synced
    where it stands and is not a place it moved to."""
    if transaction.actor == AUTO_ACTOR:
        return False
    if not transaction.ops:
        return True
    return not all(isinstance(op, _NOT_A_PLACE) for op in transaction.ops)


def is_annotation(transaction: Transaction) -> bool:
    """A line that is not a step: it marks a step or moves the branch to one,
    and is folded onto what it names rather than listed."""
    return bool(transaction.ops) and all(
        isinstance(op, (Checkpointed, Rewound)) for op in transaction.ops
    )


def _cell_note(row: sqlite3.Row) -> CellNoteRow:
    return CellNoteRow(
        branch_id=row["branch_id"],
        uid=row["uid"],
        kind=row["kind"],
        sentence=row["sentence"],
        version_id=row["version_id"],
        step=int(row["step"]),
        actor=row["actor"],
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
        experiment_id=row["experiment_id"],
        experiment_store=row["experiment_store"],
        sdk_version_warning=row["sdk_version_warning"],
        started_step=row["started_step"],
        finished_step=row["finished_step"],
    )
