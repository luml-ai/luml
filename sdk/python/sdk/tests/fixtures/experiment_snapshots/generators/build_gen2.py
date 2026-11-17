"""Regenerate fixtures i to o (artifact generation 2, its fallback, and a revision 2
artifact with the trace and eval edge cases) and their JSON.

Usage: python build_gen2.py <workspace> <new_python> [<fixture_dir>]

<workspace>/envs/D is the luml-sdk==0.5.0 environment described in build_all.py;
<new_python> is a Python running this tree's luml-sdk (sdk/python/sdk/.venv/bin/python).
Every SDK run happens under fakeroot, so packed files are owned by root, and attachment
mtimes are fixed before each export. <fixture_dir> defaults to the directory that
contains this generators directory. Fixtures l and n stand for artifacts already
published: to regenerate the others, write to a separate <fixture_dir> and copy only
those.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
WORKSPACE = Path(sys.argv[1]).resolve()
NEW = sys.argv[2]
OLD = str(WORKSPACE / "envs" / "D" / "bin" / "python")
DEST = Path(sys.argv[3]) if len(sys.argv) > 3 else SCRIPTS.parent
WORK = WORKSPACE / "work-gen2"
OUT = WORKSPACE / "out-gen2"
NEW_PRODUCER = "this luml-sdk (artifact generation 2)"
OLD_PRODUCER = "luml-sdk==0.5.0 (PyPI)"


def run(python: str, *args: str) -> None:
    command = ["fakeroot", python, "-I", str(SCRIPTS / "gen_gen2.py"), *args]
    subprocess.run(command, check=True, cwd=WORKSPACE)


def describe(name: str, work: str, spec: dict[str, object]) -> None:
    target = DEST / f"{name}.tar"
    shutil.copyfile(OUT / f"{name}.tar", target)
    subprocess.run(
        [
            sys.executable,
            "-I",
            str(SCRIPTS / "describe_gen2.py"),
            str(target),
            str(WORK / work / "population.log.json"),
            str(DEST / f"{name}.json"),
            json.dumps(spec),
        ],
        check=True,
    )


def spec(era: str, producer: str, kind: str, annotations: bool) -> dict[str, object]:
    return {
        "era": era,
        "producer": producer,
        "artifact_kind": kind,
        "has_annotations": annotations,
    }


shutil.rmtree(WORK, ignore_errors=True)
shutil.rmtree(OUT, ignore_errors=True)
WORK.mkdir()
OUT.mkdir()
work = {name: str(WORK / name) for name in "ijklmno"}

run(NEW, "populate", work["i"], "fixture-i", "edge")
run(NEW, "export", work["i"], "fixture-i", str(OUT / "i_gen2_sdk_0_6_0.tar"))
run(NEW, "populate", work["j"], "fixture-j", "full")
run(NEW, "model", work["j"], "fixture-j", str(OUT / "j_gen2_model_sdk_0_6_0.tar"))
run(OLD, "populate", work["k"], "fixture-k", "full")
run(NEW, "export", work["k"], "fixture-k", str(OUT / "k_gen2_from_rev2.tar"))
run(OLD, "populate", work["l"], "fixture-twin", "metrics")
run(OLD, "export", work["l"], "fixture-twin", str(OUT / "l_gen1_twin.tar"))
run(NEW, "populate", work["m"], "fixture-twin", "metrics")
run(NEW, "export", work["m"], "fixture-twin", str(OUT / "m_gen2_twin.tar"))
run(OLD, "populate", work["n"], "fixture-n", "legacy")
run(NEW, "export", work["n"], "fixture-n", str(OUT / "n_gen1_fallback.tar"))
run(OLD, "populate", work["o"], "fixture-o", "edge")
run(OLD, "export", work["o"], "fixture-o", str(OUT / "o_gen1_edge_sdk_0_5_0.tar"))

describe(
    "i_gen2_sdk_0_6_0",
    "i",
    spec("artifact generation 2, standalone", NEW_PRODUCER, "experiment", True),
)
describe(
    "j_gen2_model_sdk_0_6_0",
    "j",
    spec("artifact generation 2, embedded in a model", NEW_PRODUCER, "model", True),
)
describe(
    "k_gen2_from_rev2",
    "k",
    spec(
        "artifact generation 2 exported from a revision 2 store",
        f"store by {OLD_PRODUCER}, exported by {NEW_PRODUCER}",
        "experiment",
        True,
    ),
)
describe(
    "l_gen1_twin",
    "l",
    spec("generation 1 twin of m_gen2_twin", OLD_PRODUCER, "experiment", False),
)
describe(
    "m_gen2_twin",
    "m",
    spec("generation 2 twin of l_gen1_twin", NEW_PRODUCER, "experiment", False),
)
describe(
    "n_gen1_fallback",
    "n",
    spec(
        "generation 1 fallback: a REAL step revision 3 cannot store",
        f"store by {OLD_PRODUCER}, exported by {NEW_PRODUCER}",
        "experiment",
        False,
    ),
)
describe(
    "o_gen1_edge_sdk_0_5_0",
    "o",
    spec(
        "generation 1, revision 2, with the trace and eval edge cases",
        OLD_PRODUCER,
        "experiment",
        True,
    ),
)
