"""The kernel: the one process that runs user code.

It is path-injected into the workspace venv from the tool install, so it runs
on whatever Python the venv has (>=3.10), imports stdlib only at module import
time, and never imports `lumlflow`. Serde libraries load lazily, inside the
kind that needs them.

The daemon spawns it as `<venv-python> -m lumlflow_kernel --socket <addr>
--flow-dir <path>` and speaks JSON-RPC over that socket.
"""

from __future__ import annotations

PROTOCOL_VERSION = 1
