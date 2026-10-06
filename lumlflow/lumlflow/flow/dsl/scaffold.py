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
    words = [word for word in _words(slug) if not word.isdigit()]
    name = "".join(word[0].upper() + word[1:] for word in words)
    if not name:
        return "Untitled"
    if not name.isidentifier() or keyword.iskeyword(name):
        return f"Cell{name}"
    return name


def _words(slug: str) -> list[str]:
    # Python reads identifiers NFKC-normalized, so `x²` becomes `x2` before the
    normalized = unicodedata.normalize("NFKC", slug)
    spaced = "".join(
        char if char != "_" and f"x{char}".isidentifier() else " "
        for char in normalized
    )
    return spaced.split()


def _literal(consumes: dict[str, str]) -> str:
    body = ", ".join(f'"{name}": "{ref}"' for name, ref in consumes.items())
    return f"{{{body}}}"
