"""What a cell file declares, read by parsing it — never by importing it.

Only the declaration block is read: literal class attributes and whether a
`materialize` method exists. The body is never interpreted, so nothing here
infers wiring the file did not spell out, and no user code runs.

Classification inside a `cells/` file is a closed set of shapes: the one class
that declares a cell, a docstring-only class (a note), or nothing qualifying.
Every unhappy shape produces a flag and still yields something to accept —
agents iterate through broken intermediate states, so a file is never refused.
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Any, get_args

from lumlflow.flow.ids import is_ulid
from lumlflow.flow.store.models import (
    AssetType,
    CellClassification,
    OutputSpec,
    VersionFlag,
)

MATERIALIZE = "materialize"
UID = "uid"
DECLARATIONS = frozenset(
    {"consumes", "produces", "params", "volatility", "env_sensitive"}
)
ASSET_TYPES: tuple[str, ...] = get_args(AssetType)

_OVERRIDE_KEYS = frozenset({"type", "kind", "persist"})
_UID_ASSIGNMENT = re.compile(
    r"(?:^|;)[ \t]*uid(?:[ \t]*:[^=;\n]+)?[ \t]*=[ \t]*"
    r"(?P<quote>['\"])(?P<uid>[0-9A-Z]{26})(?P=quote)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class ParsedCell:
    node: ast.ClassDef
    classification: CellClassification = "cell"
    uid: str | None = None
    consumes: dict[str, str] = field(default_factory=dict)
    produces: dict[str, OutputSpec] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    volatility: str | None = None
    env_sensitive: bool = False

    @property
    def name(self) -> str:
        return self.node.name

    @property
    def docstring(self) -> str | None:
        return ast.get_docstring(self.node, clean=False)


@dataclass(frozen=True)
class ParsedFile:
    """`cell` is None only when the file holds nothing to accept a version of."""

    cell: ParsedCell | None
    flags: list[VersionFlag] = field(default_factory=list)
    recovered_uid: str | None = None

    @property
    def uid(self) -> str | None:
        return self.cell.uid if self.cell is not None else self.recovered_uid


def parse(source: str) -> ParsedFile:
    try:
        module = ast.parse(source)
    except SyntaxError as error:
        return ParsedFile(
            None,
            [_invalid(f"this file does not parse. {error.msg} on line {error.lineno}")],
            recovered_uid=_recover_uid(source),
        )
    flags: list[VersionFlag] = []
    candidates = [node for node in _classes(module) if _declares_a_cell(node)]
    if not candidates:
        return _parse_note(module, flags)
    if len(candidates) > 1:
        flags.append(
            VersionFlag(
                code="ambiguous",
                detail=(
                    f"{_names(candidates)} all look like the cell. "
                    "a cell file holds exactly one"
                ),
            )
        )
    node = candidates[0]
    if not _has_materialize(node):
        flags.append(
            VersionFlag(
                code="incomplete",
                detail=f"`{node.name}` has declarations but no `materialize` yet",
            )
        )
    return ParsedFile(_extract(node, flags), flags)


def _parse_note(module: ast.Module, flags: list[VersionFlag]) -> ParsedFile:
    notes = [node for node in _classes(module) if _is_note(node)]
    if not notes:
        return ParsedFile(
            None,
            [
                _invalid(
                    "no cell here. a cell is a class with a `materialize` "
                    "method. a class with only a docstring is a note"
                )
            ],
        )
    if len(notes) > 1:
        flags.append(
            VersionFlag(
                code="ambiguous",
                detail=f"{_names(notes)} are all notes. a cell file holds one",
            )
        )
    node = notes[0]
    return ParsedFile(
        ParsedCell(node=node, classification="note", uid=_declared_uid(node)), flags
    )


def _extract(node: ast.ClassDef, flags: list[VersionFlag]) -> ParsedCell:
    declared = _declared_literals(node, flags)
    return ParsedCell(
        node=node,
        uid=_string(declared.get(UID), UID, flags),
        consumes=_consumes(declared.get("consumes"), flags),
        produces=_produces(declared.get("produces"), flags),
        params=_mapping(declared.get("params"), "params", flags),
        volatility=_string(declared.get("volatility"), "volatility", flags),
        env_sensitive=bool(declared.get("env_sensitive") or False),
    )


def _declared_literals(
    node: ast.ClassDef, flags: list[VersionFlag]
) -> dict[str, object]:
    """Every declaration attribute the class assigns, evaluated as a literal.

    A non-literal is the one thing static extraction cannot follow, so it is
    flagged and dropped rather than guessed at.
    """
    declared: dict[str, object] = {}
    for statement in node.body:
        name, value = _assignment(statement)
        if name is None or value is None or name not in DECLARATIONS | {UID}:
            continue
        try:
            declared[name] = ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            flags.append(
                _invalid(
                    f"`{name}` is not a literal. lumlflow reads declarations "
                    "without running the file"
                )
            )
    return declared


def _assignment(statement: ast.stmt) -> tuple[str | None, ast.expr | None]:
    match statement:
        case ast.Assign(targets=[ast.Name(id=name)], value=value):
            return name, value
        case ast.AnnAssign(target=ast.Name(id=name), value=value) if value is not None:
            return name, value
        case _:
            return None, None


def _consumes(value: object, flags: list[VersionFlag]) -> dict[str, str]:
    entries = _mapping(value, "consumes", flags)
    consumes: dict[str, str] = {}
    for name, ref in entries.items():
        if isinstance(ref, str) and ref:
            consumes[name] = ref
        else:
            flags.append(
                _invalid(
                    f"`consumes[{name!r}]` is not a reference. write "
                    "`producer.output`, or the output name alone"
                )
            )
    return consumes


def _produces(value: object, flags: list[VersionFlag]) -> dict[str, OutputSpec]:
    entries = _mapping(value, "produces", flags)
    return {
        name: _output_spec(name, declared, flags) for name, declared in entries.items()
    }


def _output_spec(name: str, declared: object, flags: list[VersionFlag]) -> OutputSpec:
    """One output's declaration: a type word, or a dict overriding kind/persist."""
    if isinstance(declared, str):
        return OutputSpec(type=_asset_type(name, declared, flags))
    if not isinstance(declared, dict):
        flags.append(
            _invalid(f"`produces[{name!r}]` is neither {_vocabulary()} nor a mapping")
        )
        return OutputSpec(type="asset")
    unknown = sorted(str(key) for key in declared if key not in _OVERRIDE_KEYS)
    if unknown:
        flags.append(
            _invalid(
                f"`produces[{name!r}]` sets {', '.join(unknown)}. an output "
                "override takes type, kind, and persist"
            )
        )
    kind = declared.get("kind")
    return OutputSpec(
        type=_asset_type(name, declared.get("type", "asset"), flags),
        kind=kind if isinstance(kind, str) else None,
        persist=bool(declared.get("persist", True)),
    )


def _asset_type(name: str, declared: object, flags: list[VersionFlag]) -> AssetType:
    if declared in ASSET_TYPES:
        return declared  # type: ignore[return-value]
    # Coerced rather than dropped: the output keeps its name so consumers still
    # bind, and the flag carries what the word should have been.
    flags.append(
        _invalid(
            f"`produces[{name!r}]` declares {declared!r}. outputs are {_vocabulary()}"
        )
    )
    return "asset"


def _mapping(value: object, name: str, flags: list[VersionFlag]) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        flags.append(_invalid(f"`{name}` is not a mapping of names"))
        return {}
    return dict(value)


def _string(value: object, name: str, flags: list[VersionFlag]) -> str | None:
    if value is None or isinstance(value, str):
        return value
    flags.append(_invalid(f"`{name}` is not text"))
    return None


def _classes(module: ast.Module) -> list[ast.ClassDef]:
    return [node for node in module.body if isinstance(node, ast.ClassDef)]


def _declares_a_cell(node: ast.ClassDef) -> bool:
    if _has_materialize(node):
        return True
    return any(_assignment(statement)[0] in DECLARATIONS for statement in node.body)


def _has_materialize(node: ast.ClassDef) -> bool:
    return any(
        isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef)
        and statement.name == MATERIALIZE
        for statement in node.body
    )


def _is_note(node: ast.ClassDef) -> bool:
    """A docstring and nothing else — the uid write-back does not change that."""
    if ast.get_docstring(node) is None:
        return False
    return all(
        isinstance(statement, ast.Pass) or _assignment(statement)[0] == UID
        for statement in node.body[1:]
    )


def _declared_uid(node: ast.ClassDef) -> str | None:
    for statement in node.body:
        name, value = _assignment(statement)
        if name != UID or not isinstance(value, ast.Constant):
            continue
        if isinstance(value.value, str):
            return value.value
    return None


def _recover_uid(source: str) -> str | None:
    """Recover the daemon-written identity while the surrounding AST is broken."""
    for match in _UID_ASSIGNMENT.finditer(source):
        uid = match.group("uid")
        if is_ulid(uid):
            return uid
    return None


def _names(nodes: list[ast.ClassDef]) -> str:
    return ", ".join(f"`{node.name}`" for node in nodes)


def _vocabulary() -> str:
    return ", ".join(ASSET_TYPES[:-1]) + f", or {ASSET_TYPES[-1]}"


def _invalid(detail: str) -> VersionFlag:
    return VersionFlag(code="invalid", detail=detail)
