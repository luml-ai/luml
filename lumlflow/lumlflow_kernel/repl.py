"""The scratch REPL: code against a branch's values, with nothing written back.

Names hydrate on first mention — an expression over one asset never
deserializes the other nineteen — and every one is handed out as a copy.

Nothing here writes an asset. A trailing expression comes back as its repr,
whatever the code printed comes back as text, and promoting scratch code to a
cell is an explicit op elsewhere.
"""

from __future__ import annotations

import ast
import traceback
from types import TracebackType
from typing import Any

from lumlflow_kernel.capture import Capture
from lumlflow_kernel.executor import Executor

FILENAME = "<eval>"
_REPLY_LIMIT_BYTES = 64 * 1024

Refs = dict[str, dict[str, str]]


def evaluate(executor: Executor, *, refs: Refs, code: str) -> dict[str, Any]:
    """Run `code` against the names a branch resolves.

    The console is captured so a `print` reaches whoever asked rather than the
    kernel's own stdout; stdin is left alone, because the REPL is the one
    interactive surface a flow has.
    """
    namespace = _Namespace(executor, refs)
    capture = Capture(_discard, stdin_at_eof=False)
    answer: str | None = None
    error: dict[str, Any] | None = None
    try:
        with capture:
            answer = _run(code, namespace)
    except BaseException as failure:  # noqa: B036 - a failure is an answer here
        error = _error(failure)
    return {
        "repr": _clip(answer),
        "output": _clip(capture.artifact().decode("utf-8", "backslashreplace")),
        "names": sorted(namespace.touched),
        "error": error,
    }


class _Namespace(dict):  # type: ignore[type-arg]
    """The branch's names, hydrated on first mention and never shared.

    A dict subclass rather than a prepared namespace: `__missing__` is what
    makes hydration lazy, and what a name the branch does not carry falls
    through — the interpreter turns a missing key here into the `NameError` it
    is.
    """

    def __init__(self, executor: Executor, refs: Refs) -> None:
        super().__init__()
        self._executor = executor
        self._refs = refs
        self.touched: dict[str, tuple[str, str]] = {}

    def __missing__(self, name: str) -> Any:
        ref = self._refs.get(name)
        if ref is None:
            raise KeyError(name)
        value_ref, kind = str(ref.get("value_ref")), str(ref.get("kind"))
        value = self._executor.copy_of(value_ref, kind)
        # Kept, so a second mention in the same code sees the mutation the
        # first one made: `df.dropna(inplace=True); len(df)` is one thought.
        self[name] = value
        self.touched[name] = (value_ref, kind)
        return value


def _run(code: str, namespace: _Namespace) -> str | None:
    """Execute the code, and answer with a trailing expression's value.

    Split the way a prompt does: `df.dropna(inplace=True); len(df)` is a
    statement and an expression, and a REPL that dropped the second would
    answer nothing to most of what anyone types.
    """
    parsed = ast.parse(code, filename=FILENAME, mode="exec")
    last = parsed.body[-1] if parsed.body else None
    tail = last.value if isinstance(last, ast.Expr) else None
    if tail is not None:
        parsed.body.pop()
    exec(compile(parsed, FILENAME, "exec"), namespace)
    if tail is None:
        return None
    value = eval(compile(ast.Expression(tail), FILENAME, "eval"), namespace)
    return None if value is None else repr(value)


def _error(failure: BaseException) -> dict[str, Any]:
    typed = _from_typed_line(failure.__traceback__)
    return {
        "type": type(failure).__name__,
        "message": str(failure) or type(failure).__name__,
        "traceback": "".join(traceback.format_exception(type(failure), failure, typed)),
    }


def _from_typed_line(tb: TracebackType | None) -> TracebackType | None:
    """The traceback from the author's own line down.

    Everything above it is this module getting there, and code that never
    reached the line — unreadable syntax — carries no frame worth showing at
    all.
    """
    while tb is not None and tb.tb_frame.f_code.co_filename != FILENAME:
        tb = tb.tb_next
    return tb


def _clip(text: str | None) -> str | None:
    if text is None:
        return None
    encoded = text.encode("utf-8")
    if len(encoded) <= _REPLY_LIMIT_BYTES:
        return text
    widest_marker = f"\n… {len(encoded)} bytes omitted".encode()
    prefix = encoded[: _REPLY_LIMIT_BYTES - len(widest_marker)].decode(
        "utf-8", "ignore"
    )
    omitted = len(encoded) - len(prefix.encode("utf-8"))
    return f"{prefix}\n… {omitted} bytes omitted"


def _discard(stream: str, seq: int, data: bytes) -> None:
    """The REPL has no live console channel: its output is its answer."""
