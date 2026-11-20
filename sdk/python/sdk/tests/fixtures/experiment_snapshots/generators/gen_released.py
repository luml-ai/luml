"""Fixtures C, D, E, F with a released luml-sdk from PyPI (the env's installed version).

Run with envs/C or envs/D python under fakeroot.
Usage:
  gen_released.py experiment <work_dir> <out_tar> <exp_id>    # C, D
  gen_released.py model <work_dir> <out_tar> <exp_id>         # F
  gen_released.py reopen-model <store_dir> <out_tar> <exp_id> # E
E reads an existing store's experiment once, then links it to a tiny model.
tracker.export() of a pre-0.1.0 store fails in every released SDK on meta.db, but
link_to_model only reads exp.db, so this is the path by which a baseline-quirk exp.db
reaches the platform.
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
mode = sys.argv[1]
work_dir, out_tar = (os.path.abspath(a) for a in sys.argv[2:4])
exp_id_arg = sys.argv[4]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tinymodel"))

from fixture_data import (  # noqa: E402
    freeze_attachment_times,
    populate,
    populate_annotations,
    write_generation_log,
)

import luml  # noqa: E402
from luml.experiments.tracker import ExperimentTracker  # noqa: E402

sys.stdout.write(f"luml-sdk {luml.__version__}\n")
os.makedirs(work_dir, exist_ok=True)
os.chdir(work_dir)
tracker = ExperimentTracker("sqlite://./experiments")

if mode == "reopen-model":
    exp_id = exp_id_arg
    # Any read through the backend (here what the Flow UI does when the experiment is
    # opened) runs the exp.db migration runner; export_experiment_db alone does not.
    tracker.get_experiment_metric_history(exp_id, "train_loss")
    log = json.loads(Path(work_dir, "population.log.json").read_text())
else:
    exp_id = tracker.start_experiment(name=exp_id_arg, experiment_id=exp_id_arg)
    log = populate(tracker, exp_id)
    populate_annotations(tracker, exp_id)
    tracker.end_experiment(exp_id)
freeze_attachment_times(work_dir, exp_id)

if mode == "experiment":
    tracker.export(out_tar, experiment_id=exp_id)
else:
    from fnnx.extras.builder import PyfuncBuilder
    from fnnx.extras.pydantic_models.manifest import NDJSON
    from tiny_pyfunc import IdentityPyFunc

    from luml.artifacts.model import ModelReference

    builder = PyfuncBuilder(
        pyfunc=IdentityPyFunc, model_name="tiny", model_version="1.0.0"
    )
    builder.add_input(
        NDJSON(name="x", content_type="NDJSON", dtype="Array[float]", shape=["batch"])
    )
    builder.add_output(
        NDJSON(name="y", content_type="NDJSON", dtype="Array[float]", shape=["batch"])
    )
    builder.save(out_tar)
    if os.path.exists(out_tar + ".pyfnx"):
        os.replace(out_tar + ".pyfnx", out_tar)
    tracker.link_to_model(ModelReference(out_tar), experiment_id=exp_id)
write_generation_log(out_tar + ".log.json", log)
sys.stdout.write(f"wrote {out_tar}\n")
