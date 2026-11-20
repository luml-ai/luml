"""Load a LUML model artifact in a fresh environment and run it on sample inputs.

The environment holds only the pip dependencies the artifact declares, and the
model runs from an empty temporary directory with PYTHONPATH cleared, so a local
module or package that was not bundled fails here instead of after deployment.

    python verify_artifact.py model.luml inputs.json

`inputs.json` maps each input name to a list of values, e.g. {"x": [1.0, 2.0]}.
Needs `uv` on PATH.
"""

# ruff: noqa: T201  (a command-line script: its output is the report)

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

RUNNER = """
import json, sys
from fnnx.runtime import Runtime
inputs = json.loads(open(sys.argv[2]).read())
outputs = Runtime(sys.argv[1]).compute(inputs, dynamic_attributes={})
def plain(value):
    return value.tolist() if hasattr(value, "tolist") else str(value)
print(json.dumps(outputs, default=plain))
"""


def environment_spec(artifact: Path) -> dict[str, Any]:
    with tarfile.open(artifact) as archive:
        member = archive.extractfile("env.json")
        if member is None:
            raise SystemExit(f"{artifact} has no env.json")
        spec: dict[str, Any] = json.load(member)
    return spec.get("python3::conda_pip", spec)


def uv_command(spec: dict[str, Any]) -> list[str]:
    python = ".".join(str(spec.get("python_version") or "3.12").split(".")[:2])
    command = ["uv", "run", "--no-project", "--isolated", "--python", python]
    packages = [dependency["package"] for dependency in spec.get("dependencies") or []]
    for package in packages or ["fnnx[core]"]:
        command += ["--with", package]
    return command


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    if shutil.which("uv") is None:
        print("uv is required: pip install uv")
        return 2
    artifact, inputs = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    spec = environment_spec(artifact)
    if spec.get("build_dependencies"):
        print("note: conda build dependencies are not installed by this check")
    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    with tempfile.TemporaryDirectory() as empty_directory:
        result = subprocess.run(
            [
                *uv_command(spec),
                "python",
                "-I",
                "-c",
                RUNNER,
                str(artifact),
                str(inputs),
            ],
            cwd=empty_directory,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        print(result.stderr.strip()[-3000:])
        print("FAILED: the artifact does not load or run in a fresh environment")
        return 1
    print(result.stdout.strip())
    print("OK: the artifact runs in a fresh environment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
