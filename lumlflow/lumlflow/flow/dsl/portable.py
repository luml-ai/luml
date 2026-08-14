"""The single-file form of a flow: one branch's cells in one `.py`, and back.

A directory of files is how a flow is *stored* — the store's grain is the cell
version, and a file per cell is what makes renames, attribution and two agents
editing at once work. A single file is how a flow *travels*: into a gist, an
issue, an attachment, a paste. So this is a projection in both directions and
nothing of the runtime rides along with it — no history, no results, no other
branches.

Identity travels where it already lives: the line inside each cell that names
it. A file read back into a flow therefore reattaches to the cells it names
instead of minting copies of them, and the only thing the format has to add is
the one fact the source cannot carry — which name each cell answers to, since
everywhere else that is the filename.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from lumlflow.flow.errors import FlowError

MARKER = "# %% cell: "
HEADER = "# lumlflow file export"

# A name out of this file becomes a filename under `cells/`, and the file came
# from outside the workspace: anything that reads as a path is refused here
# rather than resolved somewhere below.
_UNSAFE = re.compile(r"[\x00-\x1f\x7f/\\:*?\"<>|]")


@dataclass(frozen=True)
class PortableCell:
    slug: str
    source: str


def render(cells: Sequence[PortableCell], *, flow: str, branch: str) -> str:
    """The file: a header nobody has to read, then one block per cell.

    Deterministic — the same cells in the same order render the same bytes, so
    two exports diffed against each other compare cells and never an order that
    moved underneath them.
    """
    blocks = [_preamble(flow, branch, len(cells))]
    blocks += [f"{MARKER}{cell.slug}\n{_body(cell.source)}" for cell in cells]
    # Two blank lines above each class, so the export is a file somebody can
    # lint as the ordinary Python it is.
    return "\n\n".join(blocks)


def read(text: str) -> list[PortableCell]:
    """The cells a file holds, in the order it holds them.

    The whitespace between blocks belongs to the format rather than to a cell,
    so what comes out is what went in and a round trip moves no byte any hash
    is taken over.
    """
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
        slug, body = _cell_name(line[len(MARKER) :], number), []
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


def _cell_name(raw: str, line: int) -> str:
    """The name the block's cell answers to — a filename, never a path.

    Case is left to acceptance, which lowercases it and says so, exactly as it
    does for a file somebody named `Features.py`.
    """
    slug = raw.strip()
    if not slug or slug.startswith(".") or _UNSAFE.search(slug):
        raise FlowError(f"line {line}: `{slug}` is not a name a cell can have")
    return slug


def counted(count: int) -> str:
    """How the file, the journal and the verbs all spell a number of cells."""
    return f"{count} cell{'' if count == 1 else 's'}"
