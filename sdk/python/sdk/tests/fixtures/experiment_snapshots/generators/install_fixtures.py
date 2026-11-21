"""Copy generated artifacts into the fixture directory and write their expected JSON.

Usage: python install_fixtures.py <workspace> [<fixture_dir>]
<fixture_dir> defaults to the directory that contains this generators directory.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]).resolve() / "out"
DEST = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE.parent

FIXTURES = [
    (
        "A.tar",
        "a_premigration_legacy_indexes",
        {
            "era": "pre-migration, legacy indexes (before 78051758)",
            "producer": (
                "commit 271f778ff40717364612e4b9bcf8102d8ce786ba "
                "(78051758~1, package 'dataforce')"
            ),
            "generation": "real code",
            "artifact_kind": "model",
            "has_data": True,
            "has_annotations": False,
        },
    ),
    (
        "A_noend.tar",
        "a_premigration_wal_lost",
        {
            "era": (
                "pre-migration, legacy indexes (before 78051758); "
                "link_to_model without end_experiment"
            ),
            "producer": (
                "commit 271f778ff40717364612e4b9bcf8102d8ce786ba "
                "(78051758~1, package 'dataforce')"
            ),
            "generation": "real code",
            "artifact_kind": "model",
            "has_data": False,
            "has_annotations": False,
        },
    ),
    (
        "B.tar",
        "b_premigration",
        {
            "era": "pre-migration, no legacy indexes (78051758..54eba85c)",
            "producer": (
                "commit 57ab5a89124e87ea2de3d600fada7e57a0f3b24a "
                "(54eba85c~1, package 'luml')"
            ),
            "generation": "real code",
            "artifact_kind": "experiment",
            "has_data": True,
            "has_annotations": False,
        },
    ),
    (
        "C.tar",
        "c_sdk_0_1_0",
        {
            "era": "first release with migrations",
            "producer": "luml-sdk==0.1.0 (PyPI)",
            "generation": "real code",
            "artifact_kind": "experiment",
            "has_data": True,
            "has_annotations": True,
        },
    ),
    (
        "D.tar",
        "d_sdk_0_5_0",
        {
            "era": "newest release",
            "producer": "luml-sdk==0.5.0 (PyPI)",
            "generation": "real code",
            "artifact_kind": "experiment",
            "has_data": True,
            "has_annotations": True,
        },
    ),
    (
        "E.tar",
        "e_baseline_quirk",
        {
            "era": (
                "pre-migration DB migrated by a released SDK (baseline "
                "quirk: revision 2, no annotation tables)"
            ),
            "producer": (
                "store from commit 57ab5a89 (54eba85c~1), read and linked to "
                "a model by luml-sdk==0.5.0"
            ),
            "generation": "real code",
            "artifact_kind": "model",
            "has_data": True,
            "has_annotations": False,
        },
    ),
    (
        "F.tar",
        "f_model_sdk_0_5_0",
        {
            "era": "newest release, snapshot embedded in a model artifact",
            "producer": "luml-sdk==0.5.0 (PyPI)",
            "generation": "real code",
            "artifact_kind": "model",
            "has_data": True,
            "has_annotations": True,
        },
    ),
]

DEST.mkdir(parents=True, exist_ok=True)
for source, name, spec in FIXTURES:
    target = DEST / f"{name}.tar"
    shutil.copyfile(OUT / source, target)
    subprocess.run(
        [
            sys.executable,
            "-I",
            str(HERE / "describe.py"),
            str(target),
            str(OUT / f"{source}.log.json"),
            str(DEST / f"{name}.json"),
            json.dumps(spec),
        ],
        check=True,
    )
