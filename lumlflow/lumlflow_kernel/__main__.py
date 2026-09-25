"""`<venv-python> -m lumlflow_kernel --socket <addr> --flow-dir <path>`.

The daemon listens and the kernel dials in, so there is no readiness race to
poll for: by the time this process exists, the socket it was told about is
already accepting.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lumlflow_kernel import rpc
from lumlflow_kernel.kernel import Kernel


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    flow_dir = args.flow_dir.resolve()
    workspace_dir = (args.workspace_dir or flow_dir.parent).resolve()
    # `import helpers` works Jupyter-style from anywhere in the workspace.
    root = str(workspace_dir)
    if root not in sys.path:
        sys.path.insert(0, root)
    token = args.token_file.read_text("utf-8").strip() if args.token_file else None
    link = rpc.connect(args.socket, token=token)
    kernel = Kernel(flow_dir=flow_dir, workspace_dir=workspace_dir, link=link)
    link.serve(kernel)
    return 0


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lumlflow_kernel")
    parser.add_argument("--socket", required=True, help="unix path, or host:port")
    parser.add_argument("--flow-dir", required=True, type=Path)
    parser.add_argument("--workspace-dir", type=Path, default=None)
    parser.add_argument(
        "--token-file", type=Path, default=None, help="loopback transports only"
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
