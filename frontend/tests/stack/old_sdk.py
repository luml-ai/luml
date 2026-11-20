"""The interpreter of the released luml-sdk 0.5.0 venv (``E2E_OLD_SDK_PYTHON``) that
writes the old-format experiments.

With ``E2E_STRICT=1`` (CI) a missing or broken venv ends the run: the old-format tests
must test what 0.5.0 writes. Otherwise they are skipped and one line says which.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

VERSION = "0.5.0"
VERSION_SCRIPT = "from importlib.metadata import version; print(version('luml-sdk'))"


def venv_problem(python: str) -> str | None:
    if not python:
        return "E2E_OLD_SDK_PYTHON is not set"
    if not Path(python).exists():
        return f"E2E_OLD_SDK_PYTHON {python} does not exist"
    result = subprocess.run(
        [python, "-I", "-c", VERSION_SCRIPT], capture_output=True, text=True
    )
    if result.returncode != 0:
        last = (result.stderr.strip().splitlines() or ["no output"])[-1]
        return f"{python} cannot tell its luml-sdk version ({last})"
    found = result.stdout.strip()
    if found != VERSION:
        return f"{python} has luml-sdk {found}, not {VERSION}"
    return None


def old_sdk_python(skipped: str) -> str | None:
    """The venv's interpreter, or None after saying what is skipped without it."""
    python = os.environ.get("E2E_OLD_SDK_PYTHON", "")
    problem = venv_problem(python)
    if problem is None:
        return python
    if os.environ.get("E2E_STRICT") == "1":
        sys.exit(f"luml-sdk {VERSION} is required (E2E_STRICT=1): {problem}")
    sys.stdout.write(f"no luml-sdk {VERSION}: {problem}; {skipped}\n")
    return None
