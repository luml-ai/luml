"""Experiment store location and the orchestrator contract files."""

import json
import os
from pathlib import Path

from luml.experiments.tracker import ExperimentTracker

EXPERIMENTS_DIR = Path(
    os.environ.get("LUML_EXPERIMENTS_DIR", str(Path.home() / ".luml" / "experiments"))
)
RESULT_PATH = Path(".prisma/result.json")
ARTIFACT_PATH = Path(".prisma/artifact.luml")
REGISTRY_METRICS_TAG = "dataforce.studio::registry_metrics:v1"


def make_tracker() -> ExperimentTracker:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    return ExperimentTracker(f"sqlite://{EXPERIMENTS_DIR}")


def register_metrics(model_ref, metrics: dict[str, float]) -> None:
    """Stamp the registry metrics block the platform lists next to the artifact."""
    model_ref._append_metadata(
        idx=None,
        tags=[REGISTRY_METRICS_TAG],
        payload={"metrics": metrics},
        data=[],
        prefix=REGISTRY_METRICS_TAG,
    )


def write_result(experiment_id: str, metrics: dict[str, float]) -> None:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(
            {"success": True, "experiment_id": experiment_id, "metrics": metrics},
            indent=2,
        )
    )
    print(json.dumps({"type": "prisma-message", "metric": metrics["metric"]}))
