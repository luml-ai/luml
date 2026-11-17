"""Populate, export or embed the stores behind fixtures i to n, with the luml-sdk of the
Python that runs it (released 0.5.0 or this tree's). Run under fakeroot.

Usage:
  gen_gen2.py populate <work_dir> <exp_id> full|metrics|legacy
  gen_gen2.py export <work_dir> <exp_id> <out_tar>
  gen_gen2.py model <work_dir> <exp_id> <out_tar>

full: the standard fixture content (fixture_data) plus the metric log of metric_data.
metrics: static params and the metric log only. legacy: metrics plus a REAL step that
revision 3 cannot store, which only released SDKs accept.
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tinymodel"))

import fixture_data as fd  # noqa: E402
import metric_data as md  # noqa: E402

import luml  # noqa: E402
from luml.experiments.tracker import ExperimentTracker  # noqa: E402

mode, work_dir, exp_id = sys.argv[1], os.path.abspath(sys.argv[2]), sys.argv[3]
sys.stdout.write(f"luml-sdk {luml.__version__} {mode} {exp_id}\n")
os.makedirs(work_dir, exist_ok=True)
os.chdir(work_dir)
tracker = ExperimentTracker("sqlite://./experiments")


def log_metrics(entries: list[tuple[str, float, float | int]]) -> None:
    for key, value, step in entries:
        tracker.log_dynamic(key, value, step=step, experiment_id=exp_id)


def populate(content: str) -> None:
    tracker.start_experiment(name=exp_id, experiment_id=exp_id, tags=["fixture"])
    log: dict[str, object] = {"content": content}
    if content == "full":
        log.update(fd.populate(tracker, exp_id))
        fd.populate_annotations(tracker, exp_id)
    else:
        for key, value in fd.STATIC_PARAMS.items():
            tracker.log_static(key, value, experiment_id=exp_id)
    log_metrics(md.metric_log())  # type: ignore[arg-type]
    if content == "legacy":
        log_metrics([md.LEGACY_REAL_STEP])
    tracker.end_experiment(exp_id)
    Path(work_dir, "population.log.json").write_text(json.dumps(log, indent=2) + "\n")


def build_model(out_tar: str) -> None:
    from fnnx.extras.builder import PyfuncBuilder
    from fnnx.extras.pydantic_models.manifest import NDJSON
    from tiny_pyfunc import IdentityPyFunc

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


if mode == "populate":
    populate(sys.argv[4])
else:
    out_tar = os.path.abspath(sys.argv[4])
    fd.freeze_attachment_times(work_dir, exp_id)
    if mode == "export":
        tracker.export(out_tar, experiment_id=exp_id)
    else:
        from luml.artifacts.model import ModelReference

        build_model(out_tar)
        tracker.link_to_model(ModelReference(out_tar), experiment_id=exp_id)
    sys.stdout.write(f"wrote {out_tar}\n")
