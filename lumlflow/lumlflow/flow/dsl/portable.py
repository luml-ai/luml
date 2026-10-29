import keyword
import re
from collections.abc import Sequence
from dataclasses import dataclass

from lumlflow.flow.errors import FlowError

MARKER = "# %% cell: "
HEADER = "# lumlflow file export"

# A name out of this file becomes a filename under `cells/`, and the file came
_UNSAFE = re.compile(r"[\x00-\x1f\x7f/\\:*?\"<>|]")
# A name given to a new or renamed cell is also how code and the CLI refer to
# it (`score.result`, `cells show score`), so it has to read as an identifier.
# A leading underscore is refused too: `__init__` would make `cells/` a package.
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*")
CELL_NAME_RULE = (
    "lowercase letters, digits and underscores, starting with a letter "
    "and not a Python keyword"
)


@dataclass(frozen=True)
class PortableCell:
    slug: str
    source: str


def render(cells: Sequence[PortableCell], *, flow: str, branch: str) -> str:
    blocks = [_preamble(flow, branch, len(cells))]
    blocks += [f"{MARKER}{cell.slug}\n{_body(cell.source)}" for cell in cells]
    return "\n\n".join(blocks)


def read(text: str) -> list[PortableCell]:
    cells: list[PortableCell] = []
    slug: str | None = None
    body: list[str] = []
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        if not line.startswith(MARKER):
            if slug is not None:
                body.append(line)
            continue
        if slug is not None:
            cells.append(PortableCell(slug=slug, source=_body("\n".join(body))))
        slug, body = cell_name(line[len(MARKER) :], line=number), []
    if slug is not None:
        cells.append(PortableCell(slug=slug, source=_body("\n".join(body))))
    if not cells and not text.lstrip().startswith(HEADER):
        raise FlowError(
            "this file is not a lumlflow export. `lumlflow export <file>` "
            "writes the form `lumlflow import` reads"
        )
    return cells


def _preamble(flow: str, branch: str, count: int) -> str:
    return (
        f"{HEADER} · flow `{flow}` · branch `{branch}` · {counted(count)}\n"
        "#\n"
        "# One branch's cells, in one file. A file export, not the flow itself:\n"
        "# no history, no results, no other branches. `lumlflow import <file>`\n"
        "# reads it back into a flow, cell for cell, each keeping its identity.\n"
    )


def _body(source: str) -> str:
    return source.rstrip("\n") + "\n"


def cell_name(raw: str, *, line: int | None = None) -> str:
    slug = raw.strip()
    if not slug or slug.startswith(".") or ".." in slug or _UNSAFE.search(slug):
        location = f"line {line}: " if line is not None else ""
        raise FlowError(
            f"{location}`{slug}` is not a name a cell can have. use a non-empty "
            "name without path separators, `..`, control characters or a leading dot"
        )
    return slug


def new_cell_name(raw: str) -> str:
    slug = raw.strip()
    if not _IDENTIFIER.fullmatch(slug) or keyword.iskeyword(slug):
        raise FlowError(
            f"`{slug}` is not a name a cell can have. use {CELL_NAME_RULE}, "
            "like `my_cell_1`"
        )
    return slug


def counted(count: int) -> str:
    return f"{count} cell{'' if count == 1 else 's'}"
