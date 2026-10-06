import logging
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml
from pydantic import ValidationError

from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.errors import FlowAlreadyExists, FlowError, FlowNotFound
from lumlflow.flow.ids import new_ulid
from lumlflow.flow.store.branches import MAIN_BRANCH, Branches, is_settled
from lumlflow.flow.store.cas import Cas
from lumlflow.flow.store.index import INDEX_SCHEMA_VERSION, Index, is_annotation
from lumlflow.flow.store.journal import Journal
from lumlflow.flow.store.models import (
    JOURNAL_SCHEMA_VERSION,
    BranchCreated,
    FlowInit,
    FlowManifest,
    Op,
    Transaction,
)

logger = logging.getLogger(__name__)

FLOW_SUFFIX = ".flow"
STORE_DIRNAME = ".lumlflow"
CELLS_DIRNAME = "cells"
MANIFEST_NAME = "flow.yaml"
JOURNAL_NAME = "journal.jsonl"
INDEX_NAME = "store.sqlite"

_CAS_AREAS = ("objects", "values", "previews", "logs")
_STORE_SUBDIRS = (*_CAS_AREAS, "kernel", "worktrees")

_ABSENT = object()

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
        self.listeners: list[Callable[[Transaction], None]] = []
        self._lock = threading.Lock()
        self._next_step = index.last_step + 1
        self._index_stale = False
        self._manifest_on_disk = _manifest_bytes(flow_dir)
        self._manifest_base = manifest.model_dump(mode="json")

    @classmethod
    def init(
        cls, flow_dir: Path, *, name: str | None = None, actor: str = "user"
    ) -> "FlowStore":
        flow_dir = flow_dir.resolve()
        if store_dir(flow_dir).exists():
            raise FlowAlreadyExists(f"{flow_dir} already holds a flow store")
        _scaffold(flow_dir)
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
        _validate_journal_version(flow_dir, journal)
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
            try:
                self.journal.append(transaction)
            except BaseException:
                self._next_step = self.journal.last_step() + 1
                raise
            self._next_step += 1
            try:
                self.index.apply(transaction)
            except Exception:
                # The journal already holds the line, so nothing is lost. But an
                self._index_stale = True
                raise
        self._announce(transaction)
        return transaction

    def _announce(self, transaction: Transaction) -> None:
        for listener in self.listeners:
            try:
                listener(transaction)
            except Exception:
                logger.exception("flow-store listener failed")

    def _settle(self, draft: Transaction) -> Transaction:
        if draft.branch is None or is_annotation(draft):
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

    def refresh_manifest(self) -> None:
        """Fold edits made to `flow.yaml` behind the store's back (a `git pull`,
        a hand edit) into the in-memory manifest.

        A three-way merge against the copy last read or written: a key the store
        has not changed since takes the disk's value, a key it has changed keeps
        its own, so neither side's edit is lost.
        """
        on_disk = _manifest_bytes(self.flow_dir)
        if on_disk is None or on_disk == self._manifest_on_disk:
            return
        theirs = _parse_manifest(manifest_path(self.flow_dir), on_disk)
        theirs_payload = theirs.model_dump(mode="json")
        merged = _merge3(
            self._manifest_base, self.manifest.model_dump(mode="json"), theirs_payload
        )
        self.manifest = FlowManifest.model_validate(merged)
        self._manifest_on_disk = on_disk
        self._manifest_base = theirs_payload

    def save_manifest(self) -> None:
        self.refresh_manifest()
        self._sync_manifest_cells()
        self._drop_unselected_order_entries()
        body = _manifest_body(self.manifest)
        if body == self._manifest_on_disk:
            return
        atomic_write_bytes(manifest_path(self.flow_dir), body)
        self._manifest_on_disk = body
        self._manifest_base = self.manifest.model_dump(mode="json")

    def effective_order(self) -> dict[str, Decimal]:
        born = self.index.creation_steps()
        fallback = {
            uid: Decimal(born[uid]) for uid in self._selected_uids() if uid in born
        }
        raw = self.manifest.order or {}
        mapped = {
            uid: key
            for uid in fallback
            if (key := _order_decimal(raw.get(uid))) is not None
        }

        while True:
            effective = {
                uid: mapped.get(uid, created) for uid, created in fallback.items()
            }
            collisions: dict[Decimal, list[str]] = {}
            for uid, key in effective.items():
                collisions.setdefault(key, []).append(uid)
            invalid = {
                uid
                for uids in collisions.values()
                if len(uids) > 1
                for uid in uids
                if uid in mapped
            }
            if not invalid:
                return effective
            for uid in invalid:
                mapped.pop(uid)

    def order_before(self, anchor_uid: str, *, excluding_uid: str | None = None) -> str:
        effective, upper = self._order_anchor(anchor_uid, excluding_uid)
        lower = max(
            (key for key in effective.values() if key < upper),
            default=Decimal(0),
        )
        if lower >= upper:
            raise FlowError("the anchor's order must be later than the first step")
        return _order_text(_exact_midpoint(lower, upper))

    def order_after(self, anchor_uid: str, *, excluding_uid: str | None = None) -> str:
        effective, lower = self._order_anchor(anchor_uid, excluding_uid)
        upper = min((key for key in effective.values() if key > lower), default=None)
        if upper is None:
            upper = Decimal(self.next_step)
        if upper <= lower:
            raise FlowError("the anchor's order must be earlier than the next step")
        return _order_text(_exact_midpoint(lower, upper))

    def _order_anchor(
        self, anchor_uid: str, excluding_uid: str | None
    ) -> tuple[dict[str, Decimal], Decimal]:
        effective = self.effective_order()
        if excluding_uid is not None:
            effective.pop(excluding_uid, None)
        if anchor_uid not in effective:
            raise FlowError("the anchor is no longer selected on any lane")
        return effective, effective[anchor_uid]

    def _selected_uids(self) -> set[str]:
        return {
            uid
            for branch in self.index.branches()
            for uid in self.index.selections(branch.branch_id)
        }

    def _sync_manifest_cells(self) -> None:
        known = set(self.index.creation_steps())
        selected: dict[str, set[str]] = {}
        for slug, uid in self.index.selected_slugs():
            selected.setdefault(slug, set()).add(uid)

        synced: dict[str, str] = {}
        for slug, uid in self.manifest.cells.items():
            candidates = selected.pop(slug, None)
            if candidates:
                synced[slug] = uid if uid in candidates else min(candidates)
            elif uid not in known:
                synced[slug] = uid
        for slug, candidates in selected.items():
            synced[slug] = min(candidates)
        self.manifest.cells = synced

    def _drop_unselected_order_entries(self) -> None:
        if self.manifest.order is None:
            return
        selected = self._selected_uids()
        known = set(self.index.creation_steps())
        rebuilding = set(self.manifest.cells.values()) - known
        self.manifest.order = {
            uid: key
            for uid, key in self.manifest.order.items()
            if uid in selected or uid in rebuilding
        } or None

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


def _validate_journal_version(flow_dir: Path, journal: Journal) -> None:
    for transaction in journal.replay():
        for op in transaction.ops:
            if not isinstance(op, FlowInit):
                continue
            stored = op.schema_version
            if stored > JOURNAL_SCHEMA_VERSION:
                raise FlowError(
                    f"journal schema version {stored} is newer than this lumlflow's "
                    f"version {JOURNAL_SCHEMA_VERSION}"
                )
            if stored < JOURNAL_SCHEMA_VERSION:
                raise FlowError(
                    f"journal schema version {stored} is older than this lumlflow's "
                    f"version {JOURNAL_SCHEMA_VERSION}; delete {store_dir(flow_dir)}/ "
                    "and re-initialise it from cells/ and flow.yaml"
                )


def _read_manifest(flow_dir: Path) -> FlowManifest:
    path = manifest_path(flow_dir)
    if not path.exists():
        raise FlowNotFound(f"no flow at {flow_dir}")
    return _parse_manifest(path, path.read_bytes())


def _parse_manifest(path: Path, body: bytes) -> FlowManifest:
    try:
        return FlowManifest.model_validate(yaml.safe_load(body.decode("utf-8")))
    except (yaml.YAMLError, ValidationError, UnicodeDecodeError) as error:
        raise FlowError(f"{path} is unreadable") from error


def _manifest_bytes(flow_dir: Path) -> bytes | None:
    try:
        return manifest_path(flow_dir).read_bytes()
    except FileNotFoundError:
        return None


def _write_manifest(flow_dir: Path, manifest: FlowManifest) -> None:
    atomic_write_bytes(manifest_path(flow_dir), _manifest_body(manifest))


def _manifest_body(manifest: FlowManifest) -> bytes:
    payload = manifest.model_dump(mode="json")
    if payload.get("order") is None:
        payload.pop("order", None)
    return yaml.safe_dump(payload, sort_keys=False).encode("utf-8")


def _merge3(base: object, ours: object, theirs: object) -> object:
    if ours == base:
        return theirs
    if theirs == base or not (
        isinstance(base, dict) and isinstance(ours, dict) and isinstance(theirs, dict)
    ):
        return ours
    merged: dict[object, object] = {}
    for key in {**base, **ours, **theirs}:
        value = _merge3(
            base.get(key, _ABSENT), ours.get(key, _ABSENT), theirs.get(key, _ABSENT)
        )
        if value is not _ABSENT:
            merged[key] = value
    return merged


def _order_decimal(value: object) -> Decimal | None:
    try:
        key = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return key if key.is_finite() else None


def _exact_midpoint(lower: Decimal, upper: Decimal) -> Decimal:
    lower_tuple = lower.as_tuple()
    upper_tuple = upper.as_tuple()
    exponent = min(int(lower_tuple.exponent), int(upper_tuple.exponent))

    def scaled(value: Decimal) -> int:
        parts = value.as_tuple()
        coefficient = int("".join(str(digit) for digit in parts.digits) or "0")
        if parts.sign:
            coefficient = -coefficient
        return coefficient * 10 ** (int(parts.exponent) - exponent)

    # Coefficient arithmetic keeps the midpoint exact regardless of the active
    coefficient = (scaled(lower) + scaled(upper)) * 5
    sign = int(coefficient < 0)
    digits = tuple(int(digit) for digit in str(abs(coefficient))) or (0,)
    return Decimal((sign, digits, exponent - 1))


def _order_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


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
