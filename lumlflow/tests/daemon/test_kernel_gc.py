from pathlib import Path

import pytest
from lumlflow.flow.store import gc
from lumlflow.flow.store.flowstore import FlowStore

from tests.kernel.helpers import make_kernel, run


def test_gc_cannot_remove_an_output_between_staging_and_run_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kernel, _ = make_kernel(tmp_path)
    store = FlowStore.init(kernel.flow_dir)
    install = kernel.executor._values._install
    reports: list[gc.SweepReport] = []

    def install_then_sweep(
        staged: Path, target: Path, *, discard_on_error: bool
    ) -> None:
        install(staged, target, discard_on_error=discard_on_error)
        reports.append(gc.sweep(store))

    monkeypatch.setattr(kernel.executor._values, "_install", install_then_sweep)
    try:
        record = run(
            kernel,
            'def materialize(self, ctx):\n    return {"model": "WEIGHTS"}',
            produces={"model": "model"},
        )
        value_ref = record["outputs"]["model"]["value_ref"]

        assert reports == [gc.SweepReport(collected=0, freed_bytes=0, kept=1)]
        assert store.values.exists(value_ref)
    finally:
        store.index.release_values("run1")
        store.close()
