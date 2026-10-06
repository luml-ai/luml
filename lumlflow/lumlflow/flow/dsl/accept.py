import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.dsl import loader, normalize
from lumlflow.flow.dsl.loader import ParsedCell
from lumlflow.flow.dsl.normalize import Namespace
from lumlflow.flow.hashing import hash_bytes
from lumlflow.flow.ids import new_ulid
from lumlflow.flow.store.branches import MAIN_BRANCH
from lumlflow.flow.store.flowstore import CELLS_DIRNAME, FlowStore
from lumlflow.flow.store.index import VersionRow
from lumlflow.flow.store.models import (
    CellAccepted,
    CellClassification,
    CellManifest,
    Op,
    Renamed,
    SelectionSet,
    VersionFlag,
)

CELL_SUFFIX = ".py"
PLACEHOLDER_SLUG = "untitled"

_EDITOR_CELL_PREFIXES = (".#", "._")
_PLACEHOLDER = re.compile(rf"^{PLACEHOLDER_SLUG}(_\d+)?$")
_WORD_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def cell_paths(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.glob(f"*{CELL_SUFFIX}")
        if not path.name.startswith(_EDITOR_CELL_PREFIXES)
    )


def cell_source_matches(
    data: bytes, source: bytes, flags: Sequence[VersionFlag]
) -> bool:
    if data == source:
        return True
    decoded, encoding_flags = _decode_cell(data)
    if not encoding_flags or decoded.encode("utf-8") != source:
        return False
    return any(
        flag.code == "invalid"
        and (flag.detail or "").startswith("UTF-8 decoding failed:")
        for flag in flags
    )


def assert_cell_path(path: Path, cells_dir: Path) -> None:
    boundary = cells_dir.parent.resolve() / cells_dir.name
    if path.resolve().parent != boundary:
        raise AssertionError(f"cell path must resolve directly under {boundary}")


class CellReadError(OSError):
    pass


@dataclass(frozen=True)
class AcceptedCell:
    uid: str
    slug: str
    version_id: str
    definition_hash: str
    classification: CellClassification = "cell"
    flags: list[VersionFlag] = field(default_factory=list)
    renamed_from: str | None = None
    copied_from: str | None = None
    rewire: list[str] = field(default_factory=list)
    unchanged: bool = False
    summary: str = ""


@dataclass
class Batch:
    ops: list[Op] = field(default_factory=list)
    overlay: dict[str, VersionRow] = field(default_factory=dict)
    removed: set[str] = field(default_factory=set)
    accepted: list[AcceptedCell] = field(default_factory=list)

    def slice_over(self, here: dict[str, VersionRow]) -> dict[str, VersionRow]:
        return {
            uid: version
            for uid, version in (here | self.overlay).items()
            if uid not in self.removed
        }

    def add(self, ops: Sequence[Op], accepted: AcceptedCell, row: VersionRow) -> None:
        self.ops.extend(ops)
        self.overlay[row.uid] = row
        self.removed.discard(row.uid)
        self.accepted.append(accepted)

    def rename(self, op: Renamed, accepted: AcceptedCell, row: VersionRow) -> None:
        self.ops.append(op)
        self.overlay[row.uid] = row
        self.accepted.append(accepted)


@dataclass(frozen=True)
class _Identity:
    uid: str
    previous: VersionRow | None
    renamed_from: str | None = None
    copied_from: str | None = None
    copy_of_slug: str | None = None


@dataclass(frozen=True)
class _Draft:
    identity: _Identity
    slug: str
    source: str
    bound: str
    manifest: CellManifest
    definition_hash: str
    flags: list[VersionFlag]


class Acceptance:
    def __init__(self, store: FlowStore) -> None:
        self._store = store

    def cell_path(self, slug: str) -> Path:
        cells_dir = self._store.flow_dir / CELLS_DIRNAME
        path = cells_dir / f"{slug}{CELL_SUFFIX}"
        assert_cell_path(path, cells_dir)
        return path

    def accept_path(
        self,
        path: Path,
        *,
        branch: str = MAIN_BRANCH,
        actor: str = "user",
        intent: str | None = None,
        base_version_id: str | None = None,
        batch: Batch | None = None,
    ) -> AcceptedCell:
        assert_cell_path(path, self._store.flow_dir / CELLS_DIRNAME)
        try:
            data = path.read_bytes()
        except OSError as error:
            raise CellReadError(f"could not read cell file {path}") from error
        source, encoding_flags = _decode_cell(data)
        return self._accept(
            path.stem,
            source,
            path=path,
            branch=branch,
            actor=actor,
            intent=intent,
            base_version_id=base_version_id,
            batch=batch,
            source_flags=encoding_flags,
            write_back=not encoding_flags,
        )

    def accept_source(
        self,
        slug: str,
        source: str,
        *,
        branch: str = MAIN_BRANCH,
        actor: str = "user",
        intent: str | None = None,
        uid: str | None = None,
        fresh: bool = False,
        base_version_id: str | None = None,
        batch: Batch | None = None,
    ) -> AcceptedCell:
        return self._accept(
            slug,
            source,
            path=None,
            branch=branch,
            actor=actor,
            intent=intent,
            uid=uid,
            fresh=fresh,
            base_version_id=base_version_id,
            batch=batch,
        )

    def reaccept(
        self,
        slugs: Sequence[str] = (),
        *,
        uids: Sequence[str] = (),
        branch: str = MAIN_BRANCH,
        actor: str = "system",
        intent: str | None = None,
    ) -> list[AcceptedCell]:
        record = self._store.branches.get(branch)
        here = self._store.index.slice_versions(record.branch_id)
        by_slug: dict[str, tuple[str, VersionRow]] = {}
        for uid, version in here.items():
            by_slug.setdefault(version.slug, (uid, version))
        selected: list[tuple[str, VersionRow]] = []
        seen: set[str] = set()
        for uid in uids:
            selected_version = here.get(uid)
            if selected_version is not None and uid not in seen:
                selected.append((uid, selected_version))
                seen.add(uid)
        for slug in slugs:
            found = by_slug.get(slug)
            if found is None or found[0] in seen:
                continue
            selected.append(found)
            seen.add(found[0])
        accepted: list[AcceptedCell] = []
        for uid, version in selected:
            source = self._store.objects.get(version.raw_source_ref).decode("utf-8")
            # The stored source of an undecodable file is already lossy: only
            encoding_flags = [
                flag
                for flag in version.flags
                if flag.code == "invalid"
                and (flag.detail or "").startswith("UTF-8 decoding failed:")
            ]
            accepted.append(
                self._accept(
                    version.slug,
                    source,
                    path=None,
                    branch=branch,
                    actor=actor,
                    intent=intent or f"rebound {version.slug}",
                    uid=uid,
                    source_flags=encoding_flags,
                    write_back=not encoding_flags,
                )
            )
        return accepted

    def rewire(
        self,
        uids: Sequence[str],
        *,
        branch: str = MAIN_BRANCH,
        actor: str = "system",
        intent: str | None = None,
    ) -> list[AcceptedCell]:
        record = self._store.branches.get(branch)
        here = self._store.index.slice_versions(record.branch_id)
        accepted = []
        for uid in uids:
            version = here.get(uid)
            if version is None:
                continue
            source = self._store.objects.get(version.raw_source_ref).decode("utf-8")
            parsed = loader.parse(source).cell
            if parsed is None:
                continue
            canonical = _respelled(parsed, version, here)
            rewritten = (
                normalize.rewrite(source, parsed, uid=uid, canonical=canonical)
                if canonical
                else source
            )
            if rewritten == source:
                continue
            accepted.append(
                self._accept(
                    version.slug,
                    rewritten,
                    path=None,
                    branch=branch,
                    actor=actor,
                    intent=intent or f"rewired {version.slug}",
                    uid=uid,
                )
            )
        return accepted

    def _accept(
        self,
        stem: str,
        source: str,
        *,
        path: Path | None,
        branch: str,
        actor: str,
        intent: str | None,
        base_version_id: str | None = None,
        uid: str | None = None,
        fresh: bool = False,
        batch: Batch | None = None,
        source_flags: Sequence[VersionFlag] = (),
        write_back: bool = True,
    ) -> AcceptedCell:
        record = self._store.branches.get(branch)
        here = self._store.index.slice_versions(record.branch_id)
        if batch is not None:
            here = batch.slice_over(here)
        draft = self._draft(
            stem,
            source,
            here,
            path=path,
            given=uid,
            fresh=fresh,
            base_version_id=base_version_id,
            source_flags=source_flags,
            write_back=write_back,
        )
        previous = draft.identity.previous
        if previous is not None and _is_unchanged(previous, draft):
            return AcceptedCell(
                uid=draft.identity.uid,
                slug=draft.slug,
                version_id=previous.version_id,
                definition_hash=draft.definition_hash,
                classification=draft.manifest.classification,
                flags=list(previous.flags),
                unchanged=True,
            )
        if previous is not None and _is_rename_only(previous, draft):
            return self._rename(
                draft,
                here,
                branch_id=record.branch_id,
                actor=actor,
                intent=intent,
                batch=batch,
            )
        return self._record(
            draft,
            here,
            branch_id=record.branch_id,
            actor=actor,
            intent=intent,
            base_version_id=base_version_id,
            batch=batch,
        )

    def _rename(
        self,
        draft: _Draft,
        here: dict[str, VersionRow],
        *,
        branch_id: str,
        actor: str,
        intent: str | None,
        batch: Batch | None,
    ) -> AcceptedCell:
        identity = draft.identity
        previous = identity.previous
        if previous is None or identity.renamed_from is None:
            raise ValueError("a rename needs a previous version and name")
        op = Renamed(
            uid=identity.uid,
            branch_id=branch_id,
            old_slug=identity.renamed_from,
            new_slug=draft.slug,
        )
        summary = _auto_intent(draft.slug, identity)
        accepted = AcceptedCell(
            uid=identity.uid,
            slug=draft.slug,
            version_id=previous.version_id,
            definition_hash=previous.definition_hash,
            classification=previous.manifest.classification,
            flags=list(previous.flags),
            renamed_from=identity.renamed_from,
            rewire=_consumers_of(here, identity.renamed_from, identity.uid),
            summary=summary,
        )
        renamed = replace(previous, slug=draft.slug)
        if batch is not None:
            batch.rename(op, accepted, renamed)
            self._index_in_manifest(draft.slug, identity, save=False)
            return accepted
        self._store.commit(
            [op], intent=intent or summary, actor=actor, branch=branch_id
        )
        self._index_in_manifest(draft.slug, identity)
        return accepted

    def _draft(
        self,
        stem: str,
        source: str,
        here: dict[str, VersionRow],
        *,
        path: Path | None,
        given: str | None,
        fresh: bool = False,
        base_version_id: str | None,
        source_flags: Sequence[VersionFlag],
        write_back: bool,
    ) -> _Draft:
        parsed = loader.parse(source)
        slug, naming = normalize.lowercase_slug(stem)
        self.cell_path(slug)
        identity = self._identify(
            slug, parsed.uid, here, path=path, given=given, fresh=fresh
        )
        slug, taken = normalize.unique_slug(
            slug, {other.slug for uid, other in here.items() if uid != identity.uid}
        )
        if identity.renamed_from == slug:
            # The suffix rule handed the name back: the cell whose file is called
            identity = replace(identity, renamed_from=None)
        binding = (
            normalize.bind(parsed.cell, _namespace(here, identity.uid))
            if parsed.cell is not None
            else normalize.Binding(consumes={})
        )
        written = (
            self._write_back(source, parsed.cell, identity.uid, binding, path)
            if write_back
            else source
        )
        bound = (
            normalize.bound_source(parsed.cell, binding.consumes, identity.uid)
            if parsed.cell is not None
            else written
        )
        manifest = _manifest(parsed.cell, binding)
        return _Draft(
            identity=identity,
            slug=slug,
            source=written,
            bound=bound,
            manifest=manifest,
            definition_hash=normalize.definition_hash(bound, manifest.params),
            flags=[
                *source_flags,
                *parsed.flags,
                *naming,
                *taken,
                *binding.flags,
                *_divergence(slug, base_version_id, identity.previous),
                *_placeholder(slug, parsed.cell),
            ],
        )

    def _record(
        self,
        draft: _Draft,
        here: dict[str, VersionRow],
        *,
        branch_id: str,
        actor: str,
        intent: str | None,
        base_version_id: str | None,
        batch: Batch | None = None,
    ) -> AcceptedCell:
        identity = draft.identity
        version_id = new_ulid()
        ops: list[Op] = []
        if identity.renamed_from is not None:
            ops.append(
                Renamed(
                    uid=identity.uid,
                    branch_id=branch_id,
                    old_slug=identity.renamed_from,
                    new_slug=draft.slug,
                )
            )
        ops.append(
            CellAccepted(
                uid=identity.uid,
                version_id=version_id,
                slug=draft.slug,
                definition_hash=draft.definition_hash,
                raw_source_ref=self._store.objects.put(draft.source.encode("utf-8")),
                bound_source_ref=self._store.objects.put(draft.bound.encode("utf-8")),
                manifest=draft.manifest,
                parent_version_id=base_version_id
                or (identity.previous.version_id if identity.previous else None),
                copied_from=identity.copied_from,
                author=actor,
                flags=draft.flags,
            )
        )
        ops.append(
            SelectionSet(branch_id=branch_id, uid=identity.uid, version_id=version_id)
        )
        summary = _auto_intent(draft.slug, identity)
        accepted = AcceptedCell(
            uid=identity.uid,
            slug=draft.slug,
            version_id=version_id,
            definition_hash=draft.definition_hash,
            classification=draft.manifest.classification,
            flags=draft.flags,
            renamed_from=identity.renamed_from,
            copied_from=identity.copied_from,
            rewire=_consumers_of(here, identity.renamed_from, identity.uid),
            summary=summary,
        )
        if batch is not None:
            batch.add(ops, accepted, _row(ops, self._store.next_step))
            self._index_in_manifest(draft.slug, identity, save=False)
            return accepted
        self._store.commit(ops, intent=intent or summary, actor=actor, branch=branch_id)
        self._index_in_manifest(draft.slug, identity)
        return accepted

    def _identify(
        self,
        slug: str,
        declared: str | None,
        here: dict[str, VersionRow],
        *,
        path: Path | None,
        given: str | None,
        fresh: bool = False,
    ) -> _Identity:
        if given is not None:
            current = here.get(given)
            if current is not None and current.slug != slug:
                # The caller named the cell and a different name for it: a
                return _Identity(uid=given, previous=current, renamed_from=current.slug)
            return _Identity(uid=given, previous=current)
        if fresh:
            return _Identity(uid=new_ulid(), previous=None)
        if declared is not None and declared in here:
            current = here[declared]
            if current.slug == slug:
                return _Identity(uid=declared, previous=current)
            if path is not None and self.cell_path(current.slug).exists():
                return _Identity(
                    uid=new_ulid(),
                    previous=None,
                    copied_from=declared,
                    copy_of_slug=current.slug,
                )
            return _Identity(uid=declared, previous=current, renamed_from=current.slug)
        if declared is not None:
            return _Identity(uid=declared, previous=None)
        return self._reattach(slug, here, path)

    def _reattach(
        self, slug: str, here: dict[str, VersionRow], path: Path | None
    ) -> _Identity:
        owner = self.cell_path(slug)
        if path is not None and owner.exists() and not _same_file(path, owner):
            return _Identity(uid=new_ulid(), previous=None)
        for uid, version in here.items():
            if version.slug == slug:
                return _Identity(uid=uid, previous=version)
        committed = self._store.manifest.cells.get(slug)
        if committed is not None and not self._store.index.knows_cell(committed):
            # `flow.yaml` names a cell this store has never seen: a clone,
            return _Identity(uid=committed, previous=None)
        return _Identity(uid=new_ulid(), previous=None)

    def _write_back(
        self,
        source: str,
        cell: ParsedCell | None,
        uid: str,
        binding: normalize.Binding,
        path: Path | None,
    ) -> str:
        if cell is None:
            return source
        rewritten = normalize.rewrite(
            source, cell, uid=uid, canonical=binding.canonical
        )
        if path is not None and rewritten != source:
            atomic_write_bytes(path, rewritten.encode("utf-8"))
        return rewritten

    def _index_in_manifest(
        self, slug: str, identity: _Identity, *, save: bool = True
    ) -> None:
        cells = self._store.manifest.cells
        if identity.renamed_from is not None:
            cells.pop(identity.renamed_from, None)
        cells[slug] = identity.uid
        if save:
            self._store.save_manifest()


def _namespace(here: dict[str, VersionRow], own: str) -> Namespace:
    uids: dict[str, str] = {}
    outputs: dict[str, tuple[str, ...]] = {}
    for uid, version in here.items():
        if uid == own or version.slug in uids:
            continue
        uids[version.slug] = uid
        outputs[version.slug] = tuple(version.manifest.produces)
    return Namespace(uids=uids, outputs=outputs)


def _manifest(cell: ParsedCell | None, binding: normalize.Binding) -> CellManifest:
    if cell is None:
        return CellManifest()
    return CellManifest(
        classification=cell.classification,
        consumes=binding.consumes,
        produces=cell.produces,
        params=cell.params,
        volatility=cell.volatility,
        env_sensitive=cell.env_sensitive,
    )


def _divergence(
    slug: str, base_version_id: str | None, previous: VersionRow | None
) -> list[VersionFlag]:
    if base_version_id is None or previous is None:
        return []
    if base_version_id == previous.version_id:
        return []
    return [
        VersionFlag(
            code="divergent",
            detail=f"this edit started from an older version of `{slug}`. "
            "save it to a new lane, or overwrite what is there",
        )
    ]


def _placeholder(slug: str, cell: ParsedCell | None) -> list[VersionFlag]:
    if not _PLACEHOLDER.match(slug):
        return []
    derived = derived_slug(cell.name) if cell is not None else None
    return [
        VersionFlag(
            code="placeholder_slug",
            detail=(
                f"`{slug}` is a placeholder name. rename it to `{derived}`"
                if derived is not None
                else f"`{slug}` is a placeholder name. give the cell a name"
            ),
        )
    ]


def derived_slug(class_name: str) -> str | None:
    slug = _WORD_BREAK.sub("_", class_name).lower()
    return None if not slug or _PLACEHOLDER.match(slug) else slug


def _row(ops: Sequence[Op], step: int) -> VersionRow:
    accepted = next(op for op in ops if isinstance(op, CellAccepted))
    return VersionRow(
        version_id=accepted.version_id,
        uid=accepted.uid,
        slug=accepted.slug,
        definition_hash=accepted.definition_hash,
        raw_source_ref=accepted.raw_source_ref,
        bound_source_ref=accepted.bound_source_ref,
        manifest=accepted.manifest,
        flags=list(accepted.flags),
        parent_version_id=accepted.parent_version_id,
        author=accepted.author,
        created_step=step,
    )


def _is_unchanged(previous: VersionRow, draft: _Draft) -> bool:
    return (
        draft.identity.renamed_from is None
        and draft.identity.copied_from is None
        and previous.slug == draft.slug
        and previous.raw_source_ref == hash_bytes(draft.source.encode("utf-8"))
        and previous.definition_hash == draft.definition_hash
        and previous.flags == draft.flags
    )


def _is_rename_only(previous: VersionRow, draft: _Draft) -> bool:
    return (
        draft.identity.renamed_from is not None
        and draft.identity.copied_from is None
        and previous.raw_source_ref == hash_bytes(draft.source.encode("utf-8"))
        and previous.bound_source_ref == hash_bytes(draft.bound.encode("utf-8"))
        and previous.definition_hash == draft.definition_hash
        and previous.manifest == draft.manifest
        and previous.flags == draft.flags
    )


def _respelled(
    parsed: ParsedCell, version: VersionRow, here: dict[str, VersionRow]
) -> dict[str, str]:
    canonical = {}
    for name, reference in parsed.consumes.items():
        bound = version.manifest.consumes.get(name)
        producer, _, output = reference.rpartition(".")
        if bound is None or bound.uid is None or bound.uid not in here or not output:
            continue
        current = here[bound.uid].slug
        if producer != current:
            canonical[reference] = f"{current}.{output}"
    return canonical


def _consumers_of(here: dict[str, VersionRow], slug: str | None, own: str) -> list[str]:
    if slug is None:
        return []
    return sorted(
        uid
        for uid, version in here.items()
        if uid != own
        and any(
            consumed.ref.split(".", 1)[0] == slug
            for consumed in version.manifest.consumes.values()
            if "." in consumed.ref
        )
    )


def _same_file(path: Path, other: Path) -> bool:
    try:
        return path.samefile(other)
    except OSError:
        return False


def _decode_cell(data: bytes) -> tuple[str, list[VersionFlag]]:
    try:
        return data.decode("utf-8-sig"), []
    except UnicodeDecodeError as error:
        return data.decode("utf-8-sig", errors="replace"), [
            VersionFlag(
                code="invalid",
                detail=(
                    f"UTF-8 decoding failed: {error.reason}. "
                    "save cell files with UTF-8 encoding"
                ),
            )
        ]


def _auto_intent(slug: str, identity: _Identity) -> str:
    if identity.renamed_from is not None:
        return f"renamed {identity.renamed_from} to {slug}"
    if identity.copy_of_slug is not None:
        return f"copied {slug} from {identity.copy_of_slug}"
    return f"edited {slug}" if identity.previous is not None else f"added {slug}"
