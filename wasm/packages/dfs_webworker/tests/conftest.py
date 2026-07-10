"""Expose ``dfs_webworker`` as a namespace over the source package without executing
its real ``__init__`` — that eager-imports falcon and fnnx, which only exist in the
Pyodide runtime. With this shim, tests can import the falcon-free submodules
(``profiling``, ``reference_profile``, ``constants``) directly in plain CPython.
"""

import sys
import types
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent.parent / "dfs_webworker"

_shim = types.ModuleType("dfs_webworker")
_shim.__path__ = [str(_PKG_DIR)]  # type: ignore[attr-defined]
sys.modules.setdefault("dfs_webworker", _shim)
