"""Names, identity write-back, and binding references to uids.

Two rewrites of a cell file are the daemon's to make, and both are token-sized:
the minted `uid` line, and the canonical spelling of a partial reference. Every
other byte the author wrote is left alone.

Binding is what makes a reference survive a rename: `features.train_split`
resolves through the branch namespace to a `(uid, output)` pair and is
substituted into the source the version hashes. The bound source is the
unparsed class — comments and formatting drop out of identity, docstrings stay.
"""

import ast
import copy
import difflib
import math
from dataclasses import dataclass, field
from typing import Any

from lumlflow.flow.dsl.loader import UID, ParsedCell
from lumlflow.flow.hashing import hash_json
from lumlflow.flow.store.models import ConsumedRef, VersionFlag

_SUGGESTION_CUTOFF = 0.6


@dataclass(frozen=True)
class Namespace:
    """What a branch's slice calls things: slug → uid, and what each produces."""

    uids: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def references(self) -> list[str]:
        return sorted(
            f"{slug}.{output}"
            for slug, outputs in self.outputs.items()
            for output in outputs
        )


@dataclass(frozen=True)
class Binding:
    """`canonical` maps a partial reference to the spelling written back."""

    consumes: dict[str, ConsumedRef]
    canonical: dict[str, str] = field(default_factory=dict)
    flags: list[VersionFlag] = field(default_factory=list)


def lowercase_slug(stem: str) -> tuple[str, list[VersionFlag]]:
    """Slugs are lowercase — case-insensitive filesystems make anything else a
    collision waiting to happen."""
    slug = stem.casefold()
    if slug == stem:
        return slug, []
    return slug, [
        VersionFlag(
            code="hygiene",
            detail=f"cell files are lowercase. `{stem}` is read as `{slug}`",
        )
    ]


def unique_slug(slug: str, taken: set[str]) -> tuple[str, list[VersionFlag]]:
    """Move a name aside when another cell already answers to it."""
    if slug not in taken:
        return slug, []
    suffixed = _suffix(slug, taken)
    return suffixed, [
        VersionFlag(
            code="hygiene",
            detail=f"another cell is named `{slug}`. this one is `{suffixed}`",
        )
    ]


def bind(cell: ParsedCell, namespace: Namespace) -> Binding:
    consumes: dict[str, ConsumedRef] = {}
    canonical: dict[str, str] = {}
    flags: list[VersionFlag] = []
    for name, reference in cell.consumes.items():
        resolved, rewrite, flag = _resolve(reference, namespace)
        consumes[name] = resolved
        if rewrite is not None:
            canonical[reference] = rewrite
        if flag is not None:
            flags.append(flag)
    return Binding(consumes=consumes, canonical=canonical, flags=flags)


def bound_source(cell: ParsedCell, consumes: dict[str, ConsumedRef], uid: str) -> str:
    """The class as the version records it: uid spelled out, references bound."""
    node = copy.deepcopy(cell.node)
    _set_uid(node, uid)
    for name, target in _consumes_nodes(node).items():
        reference = consumes.get(name)
        if reference is None:
            continue
        target.value = (
            f"{reference.uid}.{reference.output}"
            if reference.uid and reference.output
            else reference.ref
        )
    return ast.unparse(node)


def definition_hash(source: str, params: dict[str, Any]) -> str:
    return hash_json({"source": source, "params": _jsonable(params)})


def rewrite(
    source: str, cell: ParsedCell, *, uid: str, canonical: dict[str, str]
) -> str:
    """The file with its uid line and canonical references — other lines intact.

    Byte offsets, not lines: `ast` reports columns as UTF-8 offsets, and the
    edits are single tokens inside lines nobody else may disturb.
    """
    data = source.encode("utf-8")
    starts = _line_starts(data)
    edits: list[tuple[int, int, bytes]] = []
    if cell.uid != uid:
        edits.append(_uid_edit(data, starts, cell, uid))
    for target in _consumes_nodes(cell.node).values():
        spelling = canonical.get(str(target.value))
        if spelling is None or target.lineno != target.end_lineno:
            continue
        edits.append(
            (
                _offset(starts, target.lineno, target.col_offset),
                _offset(starts, target.end_lineno, target.end_col_offset or 0),
                _quote(data, starts, target, spelling),
            )
        )
    for start, end, text in sorted(edits, reverse=True):
        data = data[:start] + text + data[end:]
    return data.decode("utf-8")


def _uid_edit(
    data: bytes, starts: list[int], cell: ParsedCell, uid: str
) -> tuple[int, int, bytes]:
    """Replace the declared uid, or insert one line below the docstring."""
    declared = _uid_node(cell.node)
    if declared is not None:
        end_line = declared.end_lineno or declared.lineno
        return (
            _offset(starts, declared.lineno, declared.col_offset),
            _offset(starts, end_line, declared.end_col_offset or 0),
            _quote(data, starts, declared, uid),
        )
    anchor = cell.node.body[0]
    below_docstring = ast.get_docstring(cell.node) is not None
    if anchor.lineno == cell.node.lineno:
        at = _offset(
            starts, anchor.end_lineno or anchor.lineno, anchor.end_col_offset or 0
        )
        return at, at, f'; {UID} = "{uid}"'.encode()
    line = (
        (anchor.end_lineno or anchor.lineno) + 1 if below_docstring else anchor.lineno
    )
    at = _line_start(data, starts, line)
    newline = "\r\n" if b"\r\n" in data else "\n"
    indent = " " * anchor.col_offset
    text = f'{indent}{UID} = "{uid}"{newline}'.encode()
    lands_after_newline = at == 0 or data[at - 1 : at] in (b"\n", b"\r")
    return at, at, text if lands_after_newline else newline.encode() + text


def _quote(data: bytes, starts: list[int], node: ast.Constant, value: str) -> bytes:
    """Rewrite one string literal, keeping the quote character the author used."""
    start = _offset(starts, node.lineno, node.col_offset)
    quote = chr(data[start]) if chr(data[start]) in "'\"" else '"'
    return f"{quote}{value}{quote}".encode()


def _resolve(
    reference: str, namespace: Namespace
) -> tuple[ConsumedRef, str | None, VersionFlag | None]:
    if "." in reference:
        producer, output = reference.split(".", 1)
        uid = namespace.uids.get(producer)
        if uid is not None and output in namespace.outputs.get(producer, ()):
            return ConsumedRef(ref=reference, uid=uid, output=output), None, None
        return ConsumedRef(ref=reference), None, _dangling(reference, namespace)
    producers = sorted(
        slug for slug, outputs in namespace.outputs.items() if reference in outputs
    )
    if len(producers) == 1:
        spelling = f"{producers[0]}.{reference}"
        bound = ConsumedRef(
            ref=spelling, uid=namespace.uids[producers[0]], output=reference
        )
        return bound, spelling, None
    if not producers:
        return ConsumedRef(ref=reference), None, _dangling(reference, namespace)
    candidates = ", ".join(f"`{slug}.{reference}`" for slug in producers)
    return (
        ConsumedRef(ref=reference),
        None,
        VersionFlag(
            code="ambiguous",
            detail=f"`{reference}` is produced by more than one cell. "
            f"write one of {candidates}",
        ),
    )


def _dangling(reference: str, namespace: Namespace) -> VersionFlag:
    suggestion = _suggest(reference, namespace)
    detail = f"unknown reference `{reference}`"
    return VersionFlag(
        code="dangling_ref",
        detail=(
            f"{detail}. did you mean `{suggestion}`?"
            if suggestion
            else f"{detail}. no cell on this lane produces it"
        ),
    )


def _suggest(reference: str, namespace: Namespace) -> str | None:
    references = namespace.references()
    if "." in reference:
        close = difflib.get_close_matches(
            reference, references, n=1, cutoff=_SUGGESTION_CUTOFF
        )
        return close[0] if close else None
    # A bare name is compared against bare names — a full reference would dilute
    # the difference across the producer's slug and match nothing.
    by_output = {full.split(".", 1)[1]: full for full in references}
    close = difflib.get_close_matches(
        reference, list(by_output), n=1, cutoff=_SUGGESTION_CUTOFF
    )
    return by_output[close[0]] if close else None


def _consumes_nodes(node: ast.ClassDef) -> dict[str, ast.Constant]:
    """Input name → the string literal holding its reference, for rewriting."""
    for statement in node.body:
        match statement:
            case ast.Assign(
                targets=[ast.Name(id="consumes")], value=ast.Dict() as body
            ):
                return _dict_entries(body)
            case ast.AnnAssign(
                target=ast.Name(id="consumes"), value=ast.Dict() as body
            ):
                return _dict_entries(body)
    return {}


def _dict_entries(node: ast.Dict) -> dict[str, ast.Constant]:
    entries: dict[str, ast.Constant] = {}
    for key, value in zip(node.keys, node.values, strict=True):
        if (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            entries[key.value] = value
    return entries


def _uid_node(node: ast.ClassDef) -> ast.Constant | None:
    """The declared uid, however it is spelled — the loader reads both spellings,
    so a write-back that only knew one would insert a second line beside it."""
    for statement in node.body:
        match statement:
            case (
                ast.Assign(targets=[ast.Name(id=name)], value=ast.Constant() as value)
                | ast.AnnAssign(target=ast.Name(id=name), value=ast.Constant() as value)
            ):
                if name == UID and isinstance(value.value, str):
                    return value
    return None


def _set_uid(node: ast.ClassDef, uid: str) -> None:
    declared = _uid_node(node)
    if declared is not None:
        declared.value = uid
        return
    at = 1 if ast.get_docstring(node) is not None else 0
    node.body.insert(
        at,
        ast.Assign(
            targets=[ast.Name(id=UID, ctx=ast.Store())], value=ast.Constant(value=uid)
        ),
    )
    ast.fix_missing_locations(node)


def _suffix(slug: str, taken: set[str]) -> str:
    for attempt in range(2, len(taken) + 3):
        candidate = f"{slug}_{attempt}"
        if candidate not in taken:
            return candidate
    raise AssertionError("unreachable: the range exceeds the number of taken names")


def _line_starts(data: bytes) -> list[int]:
    starts, offset = [0], 0
    for line in data.splitlines(keepends=True):
        offset += len(line)
        starts.append(offset)
    return starts


def _offset(starts: list[int], lineno: int, column: int) -> int:
    return starts[lineno - 1] + column


def _line_start(data: bytes, starts: list[int], lineno: int) -> int:
    """Where a line begins, or the end of the file when it has fewer lines."""
    return starts[lineno - 1] if lineno - 1 < len(starts) else len(data)


def _jsonable(value: Any) -> Any:
    """Every literal a declaration can hold, in a shape canonical JSON accepts."""
    match value:
        case dict():
            return {str(key): _jsonable(item) for key, item in value.items()}
        case set() | frozenset():
            return sorted(repr(item) for item in value)
        case list() | tuple():
            return [_jsonable(item) for item in value]
        case bytes():
            return value.hex()
        case complex():
            return [value.real, value.imag]
        case float() if not math.isfinite(value):
            return repr(value)
        case _:
            return value
