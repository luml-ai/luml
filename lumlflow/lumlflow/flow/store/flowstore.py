"""The store's front door: layout, `flow.yaml`, and the commit pipeline.

A commit is CAS blobs (written by the caller before it gets here) → fsync'd
journal append → index update. The journal append is the commit point; a
crash after it leaves an index that catches up on the next open, and a crash
before it leaves CAS blobs no transaction references — orphans for GC.
"""

import threading
import traceback
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.errors import FlowAlreadyExists, FlowError, FlowNotFound
from lumlflow.flow.ids import new_ulid
from lumlflow.flow.store.branches import MAIN_BRANCH, Branches, is_settled
from lumlflow.flow.store.cas import Cas
from lumlflow.flow.store.index import INDEX_SCHEMA_VERSION, Index
from lumlflow.flow.store.journal import Journal
from lumlflow.flow.store.models import (
    BranchCreated,
    FlowInit,
    FlowManifest,
    Op,
    Transaction,
)

FLOW_SUFFIX = ".flow"
STORE_DIRNAME = ".lumlflow"
CELLS_DIRNAME = "cells"
MANIFEST_NAME = "flow.yaml"
JOURNAL_NAME = "journal.jsonl"
INDEX_NAME = "store.sqlite"

_CAS_AREAS = ("objects", "values", "previews", "logs")
_STORE_SUBDIRS = (*_CAS_AREAS, "kernel", "worktrees")

_CLOUD_MARKER_FILES = {".dropbox": "Dropbox", ".dropbox.cache": "Dropbox"}
_CLOUD_DIR_NAMES = {
    "dropbox": "Dropbox",
    "icloud drive": "iCloud Drive",
    "com~apple~clouddocs": "iCloud Drive",
    "google drive": "Google Drive",
}


class FlowStore:
    def __init__(
        self,
        flow_dir: Path,
        manifest: FlowManifest,
        journal: Journal,
        index: Index,
    ) -> None:
        self.flow_dir = flow_dir
        self.store_dir = store_dir(flow_dir)
        self.manifest = manifest
        self.journal = journal
        self.index = index
        self.objects = Cas(self.store_dir / "objects")
        self.values = Cas(self.store_dir / "values")
        self.previews = Cas(self.store_dir / "previews")
        self.logs = Cas(self.store_dir / "logs")
        self.branches = Branches(self)
        self.warnings: list[str] = []
        # Whoever wants to hear about a commit as it lands — the daemon's
        # stream, and nobody else so far. The journal remains the record; this
        # is only how a subscriber learns of a line without polling for it.
        self.listeners: list[Callable[[Transaction], None]] = []
        self._lock = threading.Lock()
        self._next_step = index.last_step + 1
        self._index_stale = False

    @classmethod
    def init(
        cls, flow_dir: Path, *, name: str | None = None, actor: str = "user"
    ) -> "FlowStore":
        flow_dir = flow_dir.resolve()
        if store_dir(flow_dir).exists():
            raise FlowAlreadyExists(f"{flow_dir} already holds a flow store")
        _scaffold(flow_dir)
        # A clone carries flow.yaml but not the store: keep the committed
        # identity and root a fresh history under it.
        manifest = (
            _read_manifest(flow_dir)
            if manifest_path(flow_dir).exists()
            else FlowManifest(flow_id=new_ulid(), name=name or flow_name(flow_dir))
        )
        _write_manifest(flow_dir, manifest)
        journal = Journal(store_dir(flow_dir) / JOURNAL_NAME)
        journal.ensure()
        store = cls(
            flow_dir, manifest, journal, Index(store_dir(flow_dir) / INDEX_NAME)
        )
        provider = detect_cloud_sync(flow_dir)
        if provider is not None:
            store.warnings.append(
                f"this flow lives in a {provider} folder. the store and the "
                "file watcher are unreliable on cloud-synced storage"
            )
        if _git_repo_root(flow_dir) is not None:
            _ensure_gitignore(flow_dir)
        main = BranchCreated(branch_id=new_ulid(), name=MAIN_BRANCH)
        store.commit(
            [FlowInit(flow_id=manifest.flow_id, name=manifest.name), main],
            intent=f"created flow {manifest.name}",
            actor=actor,
            branch=main.branch_id,
        )
        return store

    @classmethod
    def open(cls, flow_dir: Path) -> "FlowStore":
        flow_dir = flow_dir.resolve()
        if not store_dir(flow_dir).is_dir():
            raise FlowNotFound(f"no flow at {flow_dir}")
        manifest = _read_manifest(flow_dir)
        _scaffold(flow_dir)
        journal = Journal(store_dir(flow_dir) / JOURNAL_NAME)
        journal.repair()
        index = _open_index(store_dir(flow_dir) / INDEX_NAME, journal)
        return cls(flow_dir, manifest, journal, index)

    @property
    def next_step(self) -> int:
        return self._next_step

    def commit(
        self,
        ops: Sequence[Op],
        *,
        intent: str,
        actor: str,
        branch: str | None = None,
        offline: bool = False,
    ) -> Transaction:
        if not intent.strip():
            raise ValueError("every transaction carries an intent")
        with self._lock:
            if self._index_stale:
                self._resync_index()
            transaction = self._settle(
                Transaction(
                    step=self._next_step,
                    ts=datetime.now(UTC).isoformat(),
                    actor=actor,
                    intent=intent,
                    offline=offline,
                    branch=branch,
                    ops=list(ops),
                )
            )
            self.journal.append(transaction)
            self._next_step += 1
            try:
                self.index.apply(transaction)
            except Exception:
                # The journal already holds the line, so nothing is lost. But an
                # index that folded around a step keeps advancing its own
                # `last_step` and reads as caught-up forever after, so the gap
                # has to be remembered and rebuilt away rather than folded onto.
                self._index_stale = True
                raise
        self._announce(transaction)
        return transaction

    def _announce(self, transaction: Transaction) -> None:
        """Tell the subscribers, outside the lock and past the commit point.

        A listener that throws loses its notification and nothing else: the
        line is already journaled, and a commit that failed because a browser
        was watching would be a store that works worse when observed.
        """
        for listener in self.listeners:
            try:
                listener(transaction)
            except Exception:
                traceback.print_exc()

    def _settle(self, draft: Transaction) -> Transaction:
        """Stamp the checkpoint badge: is the branch whole once this lands?

        The answer describes the state *after* the ops, but the journal append
        is the commit point and the line is immutable once written — so the
        verdict is read off a rolled-back probe of the index with the draft
        applied.
        """
        if draft.branch is None:
            return draft
        with self.index.probe(draft) as ahead:
            settled = is_settled(ahead, draft.branch)
        return draft.model_copy(update={"settled": True}) if settled else draft

    def _resync_index(self) -> None:
        path = self.store_dir / INDEX_NAME
        self.index.close()
        Index.discard(path)
        self.index = Index(path)
        self.index.rebuild(self.journal.replay())
        self._index_stale = False

    def save_manifest(self) -> None:
        _write_manifest(self.flow_dir, self.manifest)

    def close(self) -> None:
        self.index.close()


def store_dir(flow_dir: Path) -> Path:
    return flow_dir / STORE_DIRNAME


def manifest_path(flow_dir: Path) -> Path:
    return flow_dir / MANIFEST_NAME


def flow_name(flow_dir: Path) -> str:
    name = flow_dir.name
    return name[: -len(FLOW_SUFFIX)] if name.endswith(FLOW_SUFFIX) else name


def detect_cloud_sync(path: Path) -> str | None:
    """Name the cloud-sync provider whose folder `path` sits in, if any."""
    for parent in (path, *path.parents):
        for marker, provider in _CLOUD_MARKER_FILES.items():
            if (parent / marker).exists():
                return provider
        name = parent.name.lower()
        if name in _CLOUD_DIR_NAMES:
            return _CLOUD_DIR_NAMES[name]
        if name.startswith("onedrive"):
            return "OneDrive"
    return None


def _scaffold(flow_dir: Path) -> None:
    (flow_dir / CELLS_DIRNAME).mkdir(parents=True, exist_ok=True)
    for name in _STORE_SUBDIRS:
        (store_dir(flow_dir) / name).mkdir(parents=True, exist_ok=True)
    for name in _CAS_AREAS:
        Cas(store_dir(flow_dir) / name).ensure()


def _open_index(path: Path, journal: Journal) -> Index:
    index = Index(path)
    journal_step = journal.last_step()
    if index.schema_version != INDEX_SCHEMA_VERSION or index.last_step > journal_step:
        index.close()
        Index.discard(path)
        index = Index(path)
        index.rebuild(journal.replay())
        return index
    for transaction in journal.since(index.last_step):
        index.apply(transaction)
    return index


def _read_manifest(flow_dir: Path) -> FlowManifest:
    path = manifest_path(flow_dir)
    if not path.exists():
        raise FlowNotFound(f"no flow at {flow_dir}")
    try:
        return FlowManifest.model_validate(yaml.safe_load(path.read_text("utf-8")))
    except (yaml.YAMLError, ValidationError) as error:
        raise FlowError(f"{path} is unreadable") from error


def _write_manifest(flow_dir: Path, manifest: FlowManifest) -> None:
    body = yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False)
    atomic_write_bytes(manifest_path(flow_dir), body.encode("utf-8"))


def _git_repo_root(path: Path) -> Path | None:
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _ensure_gitignore(flow_dir: Path) -> None:
    target = flow_dir / ".gitignore"
    entry = f"{STORE_DIRNAME}/"
    text = target.read_text("utf-8") if target.exists() else ""
    if any(line.strip() in (entry, STORE_DIRNAME) for line in text.splitlines()):
        return
    if text and not text.endswith("\n"):
        text += "\n"
    atomic_write_bytes(target, f"{text}{entry}\n".encode())
