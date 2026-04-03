import contextlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

RESULT_DIR = ".luml-agent"
RESULT_FILENAME = "result.json"
ARTIFACT_FILENAME = "artifact.luml"

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@dataclass
class ResultData:
    success: bool
    experiment_id: str | None = None
    experiment_ids: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    model_path: str | None = None
    error_message: str | None = None


def _parse_result_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse result file %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        logger.warning("Result file %s is not a JSON object", path)
        return None
    return data


def _extract_experiment_ids(data: dict[str, Any]) -> list[str]:
    if "experiment_ids" in data and isinstance(data["experiment_ids"], list):
        return [str(eid) for eid in data["experiment_ids"]]
    if "experiment_id" in data and data["experiment_id"] is not None:
        return [str(data["experiment_id"])]
    return []


def _extract_metrics(data: dict[str, Any]) -> dict[str, float]:
    if "metrics" in data and isinstance(data["metrics"], dict):
        metrics: dict[str, float] = {}
        for k, v in data["metrics"].items():
            with contextlib.suppress(TypeError, ValueError):
                metrics[str(k)] = float(v)
        return metrics
    if "metric" in data:
        with contextlib.suppress(TypeError, ValueError):
            return {"metric": float(data["metric"])}
    return {}


def _extract_model_path(data: dict[str, Any]) -> str | None:
    if isinstance(data.get("artifacts"), dict):
        mp = data["artifacts"].get("model_path")
        if mp is not None:
            return str(mp)
    if data.get("model_path") is not None:
        return str(data["model_path"])
    return None


def resolve_artifact_path(worktree_path: str) -> str | None:
    path = Path(worktree_path) / RESULT_DIR / ARTIFACT_FILENAME
    if path.exists():
        return str(path)
    return None


def read_result_file(worktree_path: str) -> ResultData | None:
    path = Path(worktree_path) / RESULT_DIR / RESULT_FILENAME
    if not path.exists():
        return None
    data = _parse_result_json(path)
    if data is None:
        return None

    error_message = data.get("error_message")
    if error_message is not None:
        error_message = str(error_message)

    return ResultData(
        success=bool(data.get("success", False)),
        experiment_id=data.get("experiment_id"),
        experiment_ids=_extract_experiment_ids(data),
        metrics=_extract_metrics(data),
        model_path=_extract_model_path(data),
        error_message=error_message,
    )


def parse_stdout_metric(logs: str) -> Any:  # noqa: ANN401
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
