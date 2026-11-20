"""Fixture B: pre-migration era without legacy indexes, real code of commit 54eba85c~1.

Run with envs/B python under fakeroot. Usage: gen_b.py <src_root> <work_dir> <out_tar>
Leaves the experiment store in <work_dir>/experiments so fixture E can reopen a copy.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
src_root, work_dir, out_tar = (os.path.abspath(a) for a in sys.argv[1:4])
sys.path.insert(0, str(Path(src_root) / "sdk" / "python" / "sdk"))
sys.path.insert(0, str(HERE))

from fixture_data import (  # noqa: E402
    freeze_attachment_times,
    populate,
    write_generation_log,
)

from luml.experiments.tracker import ExperimentTracker  # noqa: E402

os.makedirs(work_dir, exist_ok=True)
os.chdir(work_dir)

tracker = ExperimentTracker("sqlite://./experiments")
exp_id = tracker.start_experiment(name="fixture-b", experiment_id="fixture-b")
log = populate(tracker, exp_id)
tracker.end_experiment(exp_id)
freeze_attachment_times(work_dir, exp_id)
tracker.export(out_tar, experiment_id=exp_id)
write_generation_log(out_tar + ".log.json", log)
sys.stdout.write(f"wrote {out_tar}\n")
