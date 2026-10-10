from pathlib import Path

import pytest
from lumlflow.flow.errors import ValueNotStored
from lumlflow.flow.store.flowstore import store_dir
from lumlflow.flow.store.models import RunRecorded

from tests.daemon.helpers import (
    daemon_api,
    make_workspace,
    ops_of,
    write_cell,
)

PRODUCER_CELL = """
class Embed:
    \"\"\"Too big to keep.\"\"\"
    produces = {"vectors": {"type": "asset", "persist": False}}

    def materialize(self, ctx):
        return {"vectors": [1, 2, 3]}
"""

CONSUMER_CELL = """
class Total:
    \"\"\"Reads the vectors.\"\"\"
    consumes = {"vectors": "embed.vectors"}
    produces = {"total": "asset"}

    def materialize(self, ctx, vectors):
        return {"total": sum(vectors)}
"""

FILE_PRODUCER_CELL = """
class Weights:
    \"\"\"A checkpoint nobody keeps.\"\"\"
    produces = {"checkpoint": {"type": "asset", "persist": False}}

    def materialize(self, ctx):
        checkpoint = ctx.tempdir() / "weights.bin"
        checkpoint.write_bytes(b"WEIGHTS")
        return {"checkpoint": checkpoint}
"""

FILE_CONSUMER_CELL = """
class Load:
    \"\"\"Reads the checkpoint.\"\"\"
    consumes = {"checkpoint": "weights.checkpoint"}
    produces = {"loaded": "asset"}

    def materialize(self, ctx, checkpoint):
        return {"loaded": checkpoint.read_text()}
"""


async def test_a_consumer_reads_an_unpersisted_output_through_the_kernel(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "embed", PRODUCER_CELL)
    write_cell(root / "churn.flow", "total", CONSUMER_CELL)

    async with daemon_api(root) as api:
        first = await api.run({"flow": "churn", "target": "total"})
        again = await api.run({"flow": "churn", "target": "total"})
        total = await api.asset_preview({"flow": "churn", "target": "total.total"})
        session = api.hub.session("churn")
        vectors = [
            op.outputs["vectors"]
            for op in ops_of(session, RunRecorded)
            if "vectors" in op.outputs
        ]
        with pytest.raises(ValueNotStored):
            await api.asset_page({"flow": "churn", "target": "embed.vectors"})
        with pytest.raises(ValueNotStored):
            await api.asset_download(
                {"flow": "churn", "target": "embed.vectors", "to": str(tmp_path)}
            )

    assert first["executed"] == ["embed", "total"]
    assert again["executed"] == ["embed", "total"]
    assert total["preview"]["blocks"][0]["entries"]["value"] == "6"
    assert [(record.persisted, record.value_ref) for record in vectors] == [
        (False, None),
        (False, None),
    ]


async def test_a_consumer_reads_an_unpersisted_file_through_the_kernel(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "weights", FILE_PRODUCER_CELL)
    write_cell(root / "churn.flow", "load", FILE_CONSUMER_CELL)
    copies = store_dir(root / "churn.flow") / "kernel" / "unpersisted"

    async with daemon_api(root) as api:
        ran = await api.run({"flow": "churn", "target": "load"})
        loaded = await api.asset_preview({"flow": "churn", "target": "load.loaded"})
        session = api.hub.session("churn")
        (load,) = [op for op in ops_of(session, RunRecorded) if "loaded" in op.outputs]
        value_ref = load.outputs["loaded"].value_ref
        assert value_ref is not None
        loaded_bytes = session.store.values.path(value_ref).read_bytes()
        held = [path.name for path in copies.rglob("*") if path.is_file()]

    assert ran["executed"] == ["weights", "load"]
    assert loaded["persisted"] is True
    assert loaded_bytes == b"WEIGHTS"
    assert held == ["weights.bin"]
    assert not copies.exists()
