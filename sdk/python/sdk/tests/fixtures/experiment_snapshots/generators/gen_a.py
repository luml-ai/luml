"""Fixture A: pre-migration era with legacy indexes, real code of commit 78051758~1.

Run with envs/A python under fakeroot.
Usage: gen_a.py <src_root> <work_dir> <out_tar> [--no-end]
With --no-end the experiment is linked without end_experiment, so its data stays in
the WAL file and the published exp.db is empty.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
src_root, work_dir, out_tar = (os.path.abspath(a) for a in sys.argv[1:4])
end_before_link = "--no-end" not in sys.argv
sys.path.insert(0, str(Path(src_root) / "sdk" / "python"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tinymodel"))

from dataforce.experiments.tracker import ExperimentTracker  # noqa: E402
from dataforce.modelref import ModelReference  # noqa: E402
from fixture_data import (  # noqa: E402
    freeze_attachment_times,
    populate,
    write_generation_log,
)
from pyfnx_utils.builder import PyfuncBuilder  # noqa: E402
from pyfnx_utils.models.manifest import NDJSON  # noqa: E402
from tiny_pyfunc import IdentityPyFunc  # noqa: E402

os.makedirs(work_dir, exist_ok=True)
os.chdir(work_dir)

builder = PyfuncBuilder(pyfunc=IdentityPyFunc, model_name="tiny", model_version="1.0.0")
builder.add_input(NDJSON(name="x", dtype="Array[float]", shape=["batch"]))
builder.add_output(NDJSON(name="y", dtype="Array[float]", shape=["batch"]))
builder.save(out_tar)
if os.path.exists(out_tar + ".pyfnx"):
    os.replace(out_tar + ".pyfnx", out_tar)

tracker = ExperimentTracker("sqlite://./experiments")
exp_id = tracker.start_experiment(experiment_id="fixture-a", name="fixture-a")
log = populate(tracker, exp_id)
if end_before_link:
    tracker.end_experiment(exp_id)
freeze_attachment_times(work_dir, exp_id)
tracker.link_to_model(ModelReference(out_tar), experiment_id=exp_id)
write_generation_log(out_tar + ".log.json", log)
sys.stdout.write(f"wrote {out_tar}\n")
