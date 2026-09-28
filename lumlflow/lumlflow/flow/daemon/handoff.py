"""Cell context copied from the workbench to an agent."""

import re
from typing import TYPE_CHECKING, Any

from lumlflow.flow.daemon import queries
from lumlflow.flow.errors import FlowError

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

FENCE = "lumlflow-context"

_TRACEBACK_HEADER = "Traceback (most recent call last):"
_FRAME = re.compile(
    r'^\s*File "(?P<file>.*)", line (?P<line>\d+), in (?P<function>.+)$'
)


def payload(
    session: "FlowSession", *, branch: str, slug: str | None = None
) -> dict[str, Any]:
    if not slug:
        raise FlowError("this context is about one cell. name it")

    detail = queries.show(session, branch, slug)
    lines = [
        f"```{FENCE}",
        f"lane: {branch}",
        f"slug: {slug}",
        f"step: {detail['provenance']['step']}",
    ]

    doc = str(detail["doc"])
    if doc:
        lines.extend(["doc: |", *(f"  {line}" for line in doc.splitlines())])
    else:
        lines.append("doc:")

    error = detail["error"]
    if error:
        captured = queries.logs(session, branch, slug)["logs"]
        frames, exception = _failure_context(str(captured or error), str(error))
        if frames:
            lines.append("traceback:")
            for filename, line, function in frames:
                lines.extend(
                    [
                        f"  - file: {filename}",
                        f"    line: {line}",
                        f"    function: {function}",
                    ]
                )
        if exception:
            lines.append(f"exception: {exception}")

    lines.append("```")
    return {
        "flow": session.ref.name,
        "branch": branch,
        "slug": slug,
        "text": "\n".join(lines),
    }


def _failure_context(
    captured: str, fallback: str
) -> tuple[list[tuple[str, int, str]], str | None]:
    start = captured.rfind(_TRACEBACK_HEADER)
    traceback_text = captured[start:] if start >= 0 else fallback
    frames = [
        (match.group("file"), int(match.group("line")), match.group("function"))
        for line in traceback_text.splitlines()
        if (match := _FRAME.match(line)) is not None
    ]
    exception = next(
        (
            line.strip()
            for line in reversed(traceback_text.splitlines())
            if line.strip() and not line.lstrip().startswith("hint:")
        ),
        None,
    )
    return frames, exception
