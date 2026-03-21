import json
import re
from pathlib import Path
from typing import Any

RESULT_DIR = ".luml-agent"
RESULT_FILENAME = "result.json"

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def read_result_file(worktree_path: str) -> dict[str, Any] | None:
    path = Path(worktree_path) / RESULT_DIR / RESULT_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or "success" not in data:
        return None
    return data


def parse_stdout_metric(logs: str) -> Any:  # noqa: ANN401
    """Extract the last metric value from luml-agent-message jsonlines in stdout."""
    metric = None
    for line in logs.splitlines():
        line = _ANSI_ESCAPE_RE.sub("", line).strip()
        if not line or not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if (
            isinstance(data, dict)
            and data.get("type") == "luml-agent-message"
            and "metric" in data
        ):
            metric = data["metric"]
    return metric
