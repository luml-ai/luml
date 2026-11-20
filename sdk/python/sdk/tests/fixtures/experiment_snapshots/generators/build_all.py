"""Regenerate every fixture artifact into <workspace>/out from scratch.

Usage: python build_all.py <workspace>

The workspace must hold the historical code and one environment per era:
  src/A  git archive 78051758~1 sdk/python | tar -x -C src/A
  src/B  git archive 54eba85c~1 sdk/python | tar -x -C src/B
  envs/A uv venv -p 3.12; pyfnx-utils==0.0.1 pydantic==2.11.7 httpx==0.28.1
         shortuuid uuid6 numpy fnnx==0.0.6
  envs/B uv venv -p 3.12; pyfnx-utils==0.0.1 "cloudpickle>=3.1.2,<4" fnnx==0.0.11
         "pydantic>=2.11.7,<3" numpy
  envs/C uv venv -p 3.12; luml-sdk==0.1.0
  envs/D uv venv -p 3.12; luml-sdk==0.5.0
Each generator runs under fakeroot, so the files the SDK packs are owned by uid/gid 0
('root') instead of the local account. Then run install_fixtures.py, then
`fakeroot python -I gen_raw.py` to derive the raw-transport fixtures.
"""

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
WORKSPACE = Path(sys.argv[1]).resolve()
WORK = WORKSPACE / "work"
OUT = WORKSPACE / "out"


def run(env: str, script: str, *args: str) -> None:
    python = WORKSPACE / "envs" / env / "bin" / "python"
    command = ["fakeroot", str(python), str(SCRIPTS / script), *args]
    subprocess.run(command, check=True, cwd=WORKSPACE)


shutil.rmtree(WORK, ignore_errors=True)
shutil.rmtree(OUT, ignore_errors=True)
WORK.mkdir()
OUT.mkdir()

run("A", "gen_a.py", "src/A", "work/A", "out/A.tar")
run("A", "gen_a.py", "src/A", "work/A_noend", "out/A_noend.tar", "--no-end")
run("B", "gen_b.py", "src/B", "work/B", "out/B.tar")
run("C", "gen_released.py", "experiment", "work/C", "out/C.tar", "fixture-c")
run("D", "gen_released.py", "experiment", "work/D", "out/D.tar", "fixture-d")
run("D", "gen_released.py", "model", "work/F", "out/F.tar", "fixture-f")
shutil.copytree(WORK / "B", WORK / "E")
shutil.copyfile(OUT / "B.tar.log.json", WORK / "E" / "population.log.json")
run("D", "gen_released.py", "reopen-model", "work/E", "out/E.tar", "fixture-b")
