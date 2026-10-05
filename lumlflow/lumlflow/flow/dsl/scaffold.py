"""The file `cells new` writes, and the one the UI's "add cell downstream" gets.

A scaffold's whole job is to be edited: it spells the DSL correctly so nobody
has to remember it, wires the inputs when the caller said what this cell comes
after, and gives type checkers something to hold on to without putting any
import a cell would execute into the file.

The conformance footer and the stub import are `TYPE_CHECKING`-only, and the
bound source a run executes is the class node alone — so nothing here reaches
the workspace venv, which holds no lumlflow code.
"""

import keyword
import unicodedata
from collections.abc import Sequence

TYPING_MODULE = "lumlflow_typing"

_HEADER = """from __future__ import annotations

# Run `lumlflow guide` for the cell DSL and commands.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from {module} import CellProtocol
"""

_FOOTER = """


if TYPE_CHECKING:
    _check: CellProtocol = {name}()
"""

_DEFAULT_DOCSTRING = "What this cell is for."


def cell_source(
    slug: str,
    *,
    docstring: str | None = None,
    producer: str | None = None,
    outputs: Sequence[str] = (),
) -> str:
    """A cell file for `slug`, consuming `producer`'s outputs when named."""
    name = class_name(slug)
    consumes = (
        {output: f"{producer}.{output}" for output in outputs} if producer else {}
    )
    lines = [
        _HEADER.format(module=TYPING_MODULE),
        "",
        f"class {name}:",
        f'    """{docstring or _DEFAULT_DOCSTRING}"""',
        "",
    ]
    if consumes:
        lines.append(f"    consumes = {_literal(consumes)}")
    lines += [
        '    produces = {"result": "asset"}',
        "",
        f"    def materialize(self, ctx{''.join(f', {name}' for name in consumes)}):",
        '        return {"result": None}',
    ]
    return "\n".join(lines) + _FOOTER.format(name=name)


def class_name(slug: str) -> str:
    """`train_model` → `TrainModel`, `2d-plot` → `Cell2dPlot`, `none` → `CellNone`.

    Any name the daemon accepts as a file name yields a valid identifier: words
    break at every character an identifier cannot hold, and a result that
    starts with a digit or is a keyword gets a `Cell` prefix.

    The digits of a placeholder like `untitled_3` are not part of a class name:
    carrying them through would have the daemon suggest renaming the new cell to
    the placeholder it was just given.
    """
    words = [word for word in _words(slug) if not word.isdigit()]
    name = "".join(word[0].upper() + word[1:] for word in words)
    if not name:
        return "Untitled"
    if not name.isidentifier() or keyword.iskeyword(name):
        return f"Cell{name}"
    return name


def _words(slug: str) -> list[str]:
    # Python reads identifiers NFKC-normalized, so `x²` becomes `x2` before the
    # split rather than splitting at a character no identifier may hold.
    normalized = unicodedata.normalize("NFKC", slug)
    spaced = "".join(
        char if char != "_" and f"x{char}".isidentifier() else " "
        for char in normalized
    )
    return spaced.split()


def _literal(consumes: dict[str, str]) -> str:
    body = ", ".join(f'"{name}": "{ref}"' for name, ref in consumes.items())
    return f"{{{body}}}"
