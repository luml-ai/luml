"""The two rules that make a path-injected kernel possible.

It runs on the workspace venv's interpreter, which may be older than the
daemon's and holds no lumlflow code — so the kernel targets Python 3.10 and
imports nothing but the standard library and itself at module import time.
Serde libraries load inside the kind that needs them, never at the top of a
file.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import lumlflow_kernel

VENV_FLOOR = (3, 10)
KERNEL_ROOT = Path(lumlflow_kernel.__file__).resolve().parent
MODULES = sorted(KERNEL_ROOT.rglob("*.py"))


def test_the_package_is_not_empty():
    assert len(MODULES) >= 8


def test_every_module_parses_under_the_venv_floor():
    for module in MODULES:
        ast.parse(module.read_bytes(), filename=str(module), feature_version=VENV_FLOOR)


def test_no_module_imports_anything_but_the_standard_library_and_itself():
    for module in MODULES:
        for name in _module_level_imports(module):
            root = name.split(".", 1)[0]
            assert root in sys.stdlib_module_names or root == "lumlflow_kernel", (
                f"{module.name} imports `{name}` at module level"
            )


def test_importing_the_kernel_pulls_in_no_lumlflow_and_no_serde_libraries():
    imported = "; ".join(
        f"import lumlflow_kernel.{module.stem}"
        for module in MODULES
        if module.stem != "__init__" and module.parent == KERNEL_ROOT
    )
    probe = (
        f"import sys; {imported}; import lumlflow_kernel.kinds.builtin; "
        "print(sorted(n for n in sys.modules "
        "if n.split('.')[0] in "
        "{'lumlflow', 'pandas', 'polars', 'pyarrow', 'numpy', 'cloudpickle'}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        check=True,
        cwd=KERNEL_ROOT.parent,
        text=True,
    )

    assert result.stdout.strip() == "[]"


def _module_level_imports(path: Path) -> list[str]:
    """Imports that run when the module is imported — never a lazy one inside
    a function, which is exactly how the serde libraries are allowed in."""
    names: list[str] = []
    _collect(ast.parse(path.read_bytes()).body, names)
    return names


def _collect(body: list[ast.stmt], names: list[str]) -> None:
    for statement in body:
        if isinstance(statement, ast.Import):
            names.extend(alias.name for alias in statement.names)
        elif isinstance(statement, ast.ImportFrom) and statement.level == 0:
            names.append(statement.module or "")
        elif isinstance(statement, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
            _collect(statement.body, names)
            _collect(getattr(statement, "orelse", []), names)
            _collect(getattr(statement, "finalbody", []), names)
