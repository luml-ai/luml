"""A daemon that only records, and a flow to run cells in."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from lumlflow_kernel.kernel import Kernel


class FakeLink:
    """Stands in for the daemon and keeps every event."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.stopped = False

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self.events.append((method, params))

    def stop(self) -> None:
        self.stopped = True

    def named(self, event: str) -> list[dict[str, Any]]:
        return [params for name, params in self.events if name == event]

    def names(self) -> list[str]:
        return [name for name, _ in self.events]


def make_kernel(
    tmp_path: Path, *, link: FakeLink | None = None, files: dict[str, str] | None = None
) -> tuple[Kernel, FakeLink]:
    """A workspace holding one flow, plus whatever workspace files a test needs."""
    workspace_dir = tmp_path / "project"
    flow_dir = workspace_dir / "churn.flow"
    (flow_dir / "cells").mkdir(parents=True, exist_ok=True)
    for relative, body in (files or {}).items():
        path = workspace_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body), encoding="utf-8")
    link = link or FakeLink()
    return (
        Kernel(flow_dir=flow_dir, workspace_dir=workspace_dir, link=link),
        link,
    )


def cell_source(body: str, *, name: str = "Cell", declarations: str = "") -> str:
    """A cell class as the store's bound source holds it."""
    parts = [f"class {name}:", '    """A cell."""']
    parts.extend(_indent(block) for block in (declarations, body) if block.strip())
    return "\n".join(parts) + "\n"


def _indent(block: str) -> str:
    return textwrap.indent(textwrap.dedent(block).strip("\n"), " " * 4)


def run(
    kernel: Kernel,
    body: str,
    *,
    slug: str = "cell",
    run_id: str = "run1",
    produces: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    ctx_info: dict[str, Any] | None = None,
    identity: dict[str, str] | None = None,
    declarations: str = "",
) -> dict[str, Any]:
    return kernel.run(
        {
            "run_id": run_id,
            "version": {
                "slug": slug,
                "source": cell_source(body, declarations=declarations),
                "produces": produces or {},
            },
            "inputs": inputs or {},
            "params": params or {},
            "ctx_info": ctx_info or {"branch": "main", "step": 7},
            "identity": identity or {},
        }
    )


def stored_value(kernel: Kernel, record: dict[str, Any], output: str) -> bytes:
    ref = record["outputs"][output]["value_ref"]
    return (kernel.flow_dir / ".lumlflow" / "values" / ref[:2] / ref).read_bytes()


def stored_preview(kernel: Kernel, record: dict[str, Any], output: str) -> Any:
    import json

    ref = record["outputs"][output]["preview_ref"]
    path = kernel.flow_dir / ".lumlflow" / "previews" / ref[:2] / ref
    return json.loads(path.read_bytes())


def stored_log(kernel: Kernel, record: dict[str, Any]) -> bytes:
    ref = record["log_ref"]
    if ref is None:
        return b""
    return (kernel.flow_dir / ".lumlflow" / "logs" / ref[:2] / ref).read_bytes()


def store_blobs(kernel: Kernel) -> list[bytes]:
    store = kernel.flow_dir / ".lumlflow"
    return [
        path.read_bytes()
        for path in sorted(store.rglob("*"))
        if path.is_file() and path.parent.name != "tmp"
    ]
