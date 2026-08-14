"""Native outputs: staged locally, published asynchronously, offline-safe.

Nothing here fakes the flow — the cells are files, the kernel is a process, and
the store is a store. Only the platform is a stand-in, because what these
assert is the *queue*: that a run's bytes land locally whether or not anything
can be uploaded, that every state an upload passes through is a journal line,
and that a network which is not there costs a cell nothing.
"""

import asyncio
import re
import tarfile
from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon import envs
from lumlflow.flow.daemon.hub import FlowSession
from lumlflow.flow.daemon.uploads import UploadRequest, bundle
from lumlflow.flow.errors import ValueNotStored
from lumlflow.flow.store.flowstore import store_dir
from lumlflow.flow.store.models import LumlRef, UploadRecorded, UploadStateChanged

from tests.daemon.helpers import (
    SCORE_CELL,
    TRAIN_CELL,
    FakeLuml,
    daemon_api,
    make_workspace,
    ops_of,
    write_cell,
)

SHA256 = re.compile(r"\b[0-9a-f]{64}\b")

BROKEN_NATIVE_CELL = """
class Train:
    \"\"\"Would publish, if it got that far.\"\"\"
    produces = {"model": "model"}

    def materialize(self, ctx):
        raise ValueError("the model did not converge")
"""

UNPERSISTED_NATIVE_CELL = """
class Train:
    \"\"\"Declares a published output and keeps none of it.\"\"\"
    produces = {"model": {"type": "model", "persist": False}}

    def materialize(self, ctx):
        return {"model": "WEIGHTS"}
"""

ONE_NATIVE_CELL = """
class Train:
    \"\"\"One thing that leaves the flow, so one queue entry.\"\"\"
    produces = {"model": "model"}

    def materialize(self, ctx):
        return {"model": "WEIGHTS"}
"""

RETRAINED_CELL = """
class Train:
    \"\"\"The same cell, publishing different weights.\"\"\"
    produces = {"model": "model"}

    def materialize(self, ctx):
        return {"model": "BETTER WEIGHTS"}
"""

OTHER_NATIVE_CELL = """
class Sample:
    \"\"\"A second publisher, queued behind the first.\"\"\"
    produces = {"rows": "dataset"}

    def materialize(self, ctx):
        return {"rows": "ROWS"}
"""


class GatedLuml(FakeLuml):
    """A platform that holds an upload open until the test lets it go."""

    def __init__(self) -> None:
        super().__init__()
        self.reached = asyncio.Event()
        self.gate = asyncio.Event()

    async def upload(self, request: Any) -> LumlRef:
        self.reached.set()
        await self.gate.wait()
        return await super().upload(request)


class UnreadableBlob(FakeLuml):
    """A platform that fails the way a missing value does — naming the file."""

    async def upload(self, request: Any) -> LumlRef:
        raise FileNotFoundError(f"[Errno 2] No such file or directory: {request.path}")


async def test_a_native_output_is_staged_locally_and_published_after(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "train", TRAIN_CELL)
    platform = FakeLuml()

    async with daemon_api(root, uploader=platform) as api:
        await api.run({"target": "train"})
        session = api.hub.session("churn")
        await _settle(session)
        shown = await api.cells_show({"slug": "train"})

    # Staged first: both values are in the flow's own CAS, so a fork or a cold
    # rerun reads them without asking anyone.
    assert _stored_values(root / "churn.flow") == 2
    assert {(request.slug, request.output) for request in platform.received} == {
        ("train", "model"),
        ("train", "run"),
    }
    assert [output["uploaded"] for output in shown["materialized"]] == [True, True]


async def test_the_queue_entry_is_journal_visible_before_anything_uploads(
    tmp_path: Path,
):
    """The scenario's offline case: the run succeeds, the bytes are local, and
    the journal says `queued` — an upload nobody could perform is a recorded
    intention rather than a silence."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "train", TRAIN_CELL)
    platform = FakeLuml(offline=True)

    async with daemon_api(root, uploader=platform) as api:
        outcome = await api.run({"target": "train"})
        session = api.hub.session("churn")
        await _settle(session)
        states = [
            (op.output, op.state, op.attempts)
            for op in ops_of(session, UploadStateChanged)
        ]

    # A cell never fails because the network dropped.
    assert outcome["executed"] == ["train"] and outcome["failed"] is None
    assert ("model", "queued", 0) in states
    assert ("model", "uploading", 0) in states
    assert ("model", "failed", 1) in states
    assert ops_of(session, UploadRecorded) == []
    assert _stored_values(root / "churn.flow") == 2


async def test_the_upload_lands_when_the_network_comes_back(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "train", TRAIN_CELL)
    platform = FakeLuml(offline=True)

    async with daemon_api(root, uploader=platform) as api:
        await api.run({"target": "train"})
        session = api.hub.session("churn")
        await _settle(session)

        platform.offline = False
        published = await session.uploads.drain()

        recorded = {op.output: op.ref for op in ops_of(session, UploadRecorded)}
        mat = session.store.index.materialization(_baseline(session, "train"))

    assert sorted(entry.state for entry in published) == ["uploaded", "uploaded"]
    assert set(recorded) == {"model", "run"}
    assert recorded["model"].collection == "col-1"
    # The reference lands on the materialization, so a card renders it without
    # asking the platform again.
    assert mat is not None and mat.outputs["model"].luml_ref == recorded["model"]


async def test_a_failed_run_never_enqueues_an_upload(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "train", BROKEN_NATIVE_CELL)
    platform = FakeLuml()

    async with daemon_api(root, uploader=platform) as api:
        outcome = await api.run({"target": "train"})
        session = api.hub.session("churn")
        await _settle(session)

    assert outcome["failed"] == "train"
    assert ops_of(session, UploadStateChanged) == []
    assert platform.received == []


async def test_a_memo_hit_reuses_the_reference_instead_of_uploading_again(
    tmp_path: Path,
):
    """A hit produced no new bytes, so there is nothing new to publish — and
    the branch that hit inherits the reference the run it hit logged."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "train", TRAIN_CELL)
    platform = FakeLuml()

    async with daemon_api(root, uploader=platform) as api:
        # Forked before anything ran, so `sweep` carries no baseline and the
        # run below is a real cross-branch hit rather than a pruned step.
        await api.fork({"name": "sweep"})
        await api.run({"target": "train"})
        session = api.hub.session("churn")
        await _settle(session)
        uploaded_once = len(platform.received)

        outcome = await api.run({"target": "train", "branch": "sweep"})
        await _settle(session)

        entries = session.store.index.uploads()
        on_fork = await api.cells_show({"slug": "train", "branch": "sweep"})

    assert outcome["cached"] == ["train"]
    assert uploaded_once == 2
    assert len(platform.received) == 2
    assert sorted(entry.state for entry in entries) == ["done", "done"]
    assert all(output["uploaded"] for output in on_fork["materialized"])


async def test_an_unpersisted_native_output_has_no_bytes_to_publish(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "train", UNPERSISTED_NATIVE_CELL)
    platform = FakeLuml()

    async with daemon_api(root, uploader=platform) as api:
        await api.run({"target": "train"})
        session = api.hub.session("churn")
        await _settle(session)

    assert ops_of(session, UploadStateChanged) == []
    assert platform.received == []


async def test_promote_publishes_an_output_declared_inline(tmp_path: Path):
    """The authoring default is `asset`; promoting is the cheap way out of it,
    because the bytes were staged the moment the cell succeeded."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    platform = FakeLuml()

    async with daemon_api(root, uploader=platform) as api:
        await api.run({"target": "score"})
        session = api.hub.session("churn")
        await _settle(session)
        # Nothing publishes on its own: `asset` means inline.
        assert platform.received == []

        promoted = await api.promote({"target": "score.summary"})

    assert promoted["state"] == "uploaded"
    assert (promoted["slug"], promoted["output"]) == ("score", "summary")
    assert promoted["reference"]["collection"] == "col-1"
    assert [op.output for op in ops_of(session, UploadRecorded)] == ["summary"]
    assert [(request.slug, request.asset_type) for request in platform.received] == [
        ("score", "asset")
    ]


async def test_promote_offline_reports_the_failure_and_retries_later(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    platform = FakeLuml(offline=True)

    async with daemon_api(root, uploader=platform) as api:
        await api.run({"target": "score"})
        offline = await api.promote({"target": "score.summary"})

        platform.offline = False
        again = await api.promote({"target": "score.summary"})

    assert offline["state"] == "failed"
    assert "unreachable" in offline["detail"]
    assert again["state"] == "uploaded"


async def test_promoting_what_was_never_run_says_so_rather_than_publishing_nothing(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root, uploader=FakeLuml()) as api:
        with pytest.raises(ValueNotStored):
            await api.promote({"target": "score.summary"})


async def test_promoting_twice_asks_the_platform_once(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    platform = FakeLuml()

    async with daemon_api(root, uploader=platform) as api:
        await api.run({"target": "score"})
        first = await api.promote({"target": "score.summary"})
        second = await api.promote({"target": "score.summary"})

    assert first["reference"] == second["reference"]
    assert len(platform.received) == 1


async def test_promote_answers_for_the_materialization_it_names(tmp_path: Path):
    """Two runs of one cell share a slug and an output name, so an answer picked
    by those names is another run's artifact handed back as this one's."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "train", ONE_NATIVE_CELL)
    platform = FakeLuml(offline=True)

    async with daemon_api(root, uploader=platform) as api:
        await api.run({"target": "train"})
        session = api.hub.session("churn")
        await _settle(session)
        write_cell(flow, "train", RETRAINED_CELL)
        await api.run({"target": "train"})
        await _settle(session)

        # Two queue entries now, both owed, neither uploaded.
        assert len(session.store.index.uploads(pending=True)) == 2
        platform.offline = False
        promoted = await api.promote({"target": "train.model"})

        current = session.store.index.materialization(_baseline(session, "train"))

    assert current is not None and current.outputs["model"].luml_ref is not None
    assert promoted["reference"] == current.outputs["model"].luml_ref.model_dump(
        mode="json"
    )
    assert len(platform.received) == 1


async def test_an_output_queued_behind_a_slow_upload_still_publishes(tmp_path: Path):
    """A run that queues an output while a drain is in flight starts no second
    drain, so the one in flight has to come back for it — otherwise a big model
    upload strands everything queued behind it until an unrelated op runs."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "train", ONE_NATIVE_CELL)
    platform = GatedLuml()

    async with daemon_api(root, uploader=platform) as api:
        await api.run({"target": "train"})
        session = api.hub.session("churn")
        await platform.reached.wait()

        write_cell(flow, "sample", OTHER_NATIVE_CELL)
        await api.run({"target": "sample"})
        platform.gate.set()
        await _settle(session)

        pending = session.store.index.uploads(pending=True)

    assert {(request.slug, request.output) for request in platform.received} == {
        ("train", "model"),
        ("sample", "rows"),
    }
    assert pending == []


async def test_a_failure_that_names_the_value_file_prints_no_content_hash(
    tmp_path: Path,
):
    """A value's path ends in its content hash, and a hash is not something a
    reader is ever shown — the reason still has to be readable, though."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root, uploader=UnreadableBlob()) as api:
        await api.run({"target": "score"})
        failed = await api.promote({"target": "score.summary"})

    assert failed["state"] == "failed"
    assert "No such file" in failed["detail"]
    assert not SHA256.search(failed["detail"])


def test_the_platform_is_handed_an_archive_its_reader_can_open(tmp_path: Path):
    """The store keeps a value as a bare hash-named blob and the SDK reads an
    artifact as a named archive with a manifest in it, so publishing packs."""
    from luml_api.handlers.model_artifacts import ModelFileHandler

    blob = tmp_path / "values" / "ab" / f"ab{'0' * 62}"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"ARROW1\x00\x00WEIGHTS")
    staging = tmp_path / "staging"
    staging.mkdir()
    request = UploadRequest(
        flow="churn",
        slug="train",
        output="model",
        kind="pickle",
        asset_type="model",
        path=blob,
        content_hash=blob.name,
        size=blob.stat().st_size,
    )

    # Handing over the blob's own path is what does not work: the reader opens
    # an artifact as an archive, and a stored value is only ever its bytes.
    with pytest.raises(tarfile.ReadError):
        ModelFileHandler(str(blob)).artifact_details()

    packed = bundle(request, staging)
    details = ModelFileHandler(str(packed)).artifact_details()

    # The SDK takes the format out of the file name, so the name carries one.
    assert details.file_name == "train_model.tar"
    assert details.file_name.split(".")[1] == "tar"
    assert details.manifest["name"] == "train.model"
    assert set(details.file_index) == {"manifest.json", "train_model"}
    with tarfile.open(packed) as archive:
        payload = archive.extractfile("train_model")
        assert payload is not None and payload.read() == blob.read_bytes()


async def test_a_daemon_with_nowhere_to_publish_keeps_the_entry_queued(
    tmp_path: Path,
):
    """The object graph never reaches the network on its own. Without an
    uploader the fact is journaled anyway — the same state an offline daemon
    holds, and the next one with a platform drains it."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "train", TRAIN_CELL)

    async with daemon_api(root) as api:
        await api.run({"target": "train"})
        pending = api.hub.session("churn").store.index.uploads(pending=True)

    assert sorted(entry.output for entry in pending) == ["model", "run"]
    assert all(entry.state == "queued" for entry in pending)


async def test_a_restarted_daemon_picks_up_what_it_never_uploaded(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "train", TRAIN_CELL)

    async with daemon_api(root) as api:
        await api.run({"target": "train"})

    platform = FakeLuml()
    async with daemon_api(root, uploader=platform) as api:
        published = await api.hub.session("churn").uploads.drain()

    assert sorted(entry.output for entry in published) == ["model", "run"]
    assert len(platform.received) == 2


async def test_one_flows_queue_is_not_anothers(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "fraud"))
    write_cell(root / "churn.flow", "train", TRAIN_CELL)
    write_cell(root / "fraud.flow", "score", SCORE_CELL)
    platform = FakeLuml()

    async with daemon_api(root, uploader=platform) as api:
        await api.run({"target": "train", "flow": "churn"})
        await api.run({"target": "score", "flow": "fraud"})
        await _settle(api.hub.session("churn"))
        await _settle(api.hub.session("fraud"))

        assert api.hub.session("fraud").store.index.uploads() == []

    assert {request.flow for request in platform.received} == {"churn"}


async def test_declaring_a_published_output_scaffolds_the_sdk_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project", flows=("churn", "fraud"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    asked: list[Path] = []
    monkeypatch.setattr(envs, "ensure_sdk", _record(asked))

    async with daemon_api(root) as api:
        # Nothing published yet: an inline flow needs no platform library.
        await api.cells_list({"flow": "churn"})
        assert asked == []

        write_cell(root / "churn.flow", "train", TRAIN_CELL)
        await api.cells_list({"flow": "churn"})
        # The env is a workspace singleton, so a second flow declaring one too
        # does not shell out to uv again over the same `pyproject.toml`.
        write_cell(root / "fraud.flow", "train", TRAIN_CELL)
        await api.cells_list({"flow": "fraud"})

    assert asked == [root]


async def test_a_flow_that_publishes_nothing_never_asks_for_the_sdk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    asked: list[Path] = []
    monkeypatch.setattr(envs, "ensure_sdk", _record(asked))

    async with daemon_api(root) as api:
        await api.run({"target": "score"})
        await api.cells_list({})

    assert asked == []


def _record(asked: list[Path]):
    async def ensure_sdk(workspace_dir: Path) -> bool:
        asked.append(workspace_dir)
        return True

    return ensure_sdk


async def _settle(session: FlowSession) -> None:
    """Wait out the background drain the run started, if it started one."""
    draining = session.uploads.draining
    if draining is not None:
        await asyncio.gather(draining, return_exceptions=True)


def _stored_values(flow_dir: Path) -> int:
    values = store_dir(flow_dir) / "values"
    return sum(
        1 for path in values.rglob("*") if path.is_file() and path.parent.name != "tmp"
    )


def _baseline(session: FlowSession, slug: str) -> str:
    """The materialization the branch last observed for a cell."""
    here = session.store.index
    branch = here.branch(session.branch)
    assert branch is not None
    uid = next(
        version.uid
        for version in here.slice_versions(branch.branch_id).values()
        if version.slug == slug
    )
    return here.baselines(branch.branch_id)[uid]
