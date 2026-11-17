"""Writes experiments with released luml-sdk 0.5.0 (exp.db.zip format).

Run with the interpreter of a venv holding luml-sdk==0.5.0:

- ``python -I old_sdk_experiment.py <store dir> <output tar>`` writes and exports one
  experiment whose series matches the regular experiments of prepare_platform.py.
- ``python -I old_sdk_experiment.py legacy <store dir>`` writes the ``fallback``
  experiment only: integer steps plus rows revision 3 cannot store (a fractional REAL
  step and a text step), so this SDK's export keeps the old format.
"""

import math
import random
import sys

from luml.experiments.tracker import ExperimentTracker

STEPS = 3_000
SEED = 31
LEGACY_STEPS = 40
LEGACY_ID = "fallback"


def write_regular(store: str, output: str) -> None:
    tracker = ExperimentTracker(f"sqlite://{store}")
    experiment_id = tracker.start_experiment(name="old", group="e2e")
    tracker.log_static("seed", SEED)
    rng = random.Random(SEED)
    for step in range(STEPS):
        value = math.exp(-step / STEPS * 3) + rng.random() * 0.01
        tracker.log_dynamic("train/loss", value, step=step)
    tracker.end_experiment()
    tracker.export(output, experiment_id)


def write_legacy(store: str) -> None:
    tracker = ExperimentTracker(f"sqlite://{store}")
    tracker.start_experiment(name=LEGACY_ID, group="e2e", experiment_id=LEGACY_ID)
    for step in range(LEGACY_STEPS):
        tracker.log_dynamic("loss", 2.0 * 0.9**step, step=step)
    # 0.5.0 stores the step as given. Charts leave both rows out; only the text one is
    # counted as skipped (the fractional REAL one is not).
    tracker.log_dynamic("loss", 7.0, step=2.5)  # type: ignore[arg-type]
    tracker.log_dynamic("loss", 8.0, step="oops")  # type: ignore[arg-type]
    tracker.end_experiment()


def main() -> None:
    if sys.argv[1] == "legacy":
        write_legacy(sys.argv[2])
    else:
        write_regular(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
