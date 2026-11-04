from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import httpx
import pytest
from luml.experiments.tracker import ExperimentTracker
from luml_api._exceptions import NotFoundError
from lumlflow.schemas.experiments import UpdateExperiment
from lumlflow.schemas.luml import (
    ArtifactIn,
    UploadArtifactForm,
    UploadFileForm,
    UploadModelForm,
    UploadType,
)
from lumlflow.tui.data import DataFacade


@pytest.fixture
def facade(tmp_path: Path) -> DataFacade:
    return DataFacade(tracker=ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}"))


@pytest.mark.parametrize(
    "kind", ["experiment", "models", "model", "embed", "auto", "file"]
)
@pytest.mark.parametrize("fail", [False, True])
def test_upload_allows_local_reads_and_mutations(
    facade: DataFacade, tmp_path: Path, kind: str, fail: bool
) -> None:
    tracker = facade.tracker
    experiment_id = tracker.start_experiment(name="original")
    source = tmp_path / "model.luml"
    source.write_bytes(b"model")
    model, _ = tracker.backend.log_model(experiment_id, str(source), name="model")
    fields = dict(
        organization_id="org",
        orbit_id="orbit",
        collection_id="collection",
        artifact=ArtifactIn(),
    )
    if kind == "file":
        form = UploadFileForm(file_path=str(source), **fields)
        upload = facade.upload_file_artifact
    elif kind in {"model", "embed"}:
        form = UploadModelForm(
            experiment_id=experiment_id,
            model_id=model.id,
            embed_experiment=kind == "embed",
            **fields,
        )
        upload = facade.upload_model_artifact
    else:
        form = UploadArtifactForm(
            experiment_id=experiment_id,
            upload_type={
                "experiment": UploadType.EXPERIMENT,
                "models": UploadType.MODEL,
                "auto": UploadType.AUTO,
            }[kind],
            **fields,
        )
        upload = facade.upload_artifact
    facade.progress_store.create("job")
    entered, release = Event(), Event()
    artifact = MagicMock(id="remote-artifact")
    artifact.model_dump.return_value = {"id": "remote-artifact"}

    def network_upload(**kwargs):
        kwargs["on_progress"].on_chunk(1, 2)
        entered.set()
        assert release.wait(5)
        if fail:
            raise RuntimeError("upload failed")
        return artifact

    client = MagicMock()
    client.artifacts.upload.side_effect = network_upload
    with (
        patch.object(facade.artifacts, "_get_luml_client", return_value=client),
        patch.object(tracker, "link_to_model"),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        worker = pool.submit(upload, form, "job")
        try:
            assert entered.wait(5)
            assert pool.submit(facade.get_experiment, experiment_id).result(1).ok
            assert (
                pool.submit(
                    facade.update_experiment,
                    experiment_id,
                    UpdateExperiment(name="updated"),
                )
                .result(1)
                .ok
            )
            assert not worker.done()
            job = facade.progress_store.get("job")
            assert job is not None and job.status == "running" and job.percent == 50
        finally:
            release.set()
        assert worker.result(5).ok
    job = facade.progress_store.get("job")
    assert job is not None
    assert job.status == ("error" if fail else "complete")
    if fail:
        assert job.error == "upload failed"
        assert tracker.get_remote_artifact("model", model.id, "orbit") is None
    else:
        assert job.result == [{"id": "remote-artifact"}]
        if kind != "file":
            entity, entity_id = (
                ("experiment", experiment_id)
                if kind == "experiment"
                else ("model", model.id)
            )
            assert (
                tracker.get_remote_artifact(entity, entity_id, "orbit")
                == "remote-artifact"
            )
    assert facade.get_experiment(experiment_id).unwrap().name == "updated"


@pytest.mark.parametrize(
    "phase",
    [
        "get_models",
        "link_to_model",
        "get_remote_artifact",
        "set_remote_artifact",
        "delete_remote_artifact",
        "get_experiment_record",
        "save_experiment",
    ],
)
def test_upload_tracker_phases_serialize_local_reads(
    facade: DataFacade, tmp_path: Path, phase: str
) -> None:
    tracker = facade.tracker
    experiment_id = tracker.start_experiment(name="experiment")
    source = tmp_path / "model.luml"
    source.write_bytes(b"model")
    model, _ = tracker.backend.log_model(experiment_id, str(source), name="model")
    tracker.set_remote_artifact("experiment", experiment_id, "orbit", "stale")
    form = UploadArtifactForm(
        experiment_id=experiment_id,
        upload_type=UploadType.EXPERIMENT
        if phase in {"get_experiment_record", "save_experiment"}
        else UploadType.MODEL,
        embed_experiment=phase == "link_to_model",
        organization_id="org",
        orbit_id="orbit",
        collection_id="collection",
        artifact=ArtifactIn(),
    )
    entered, release, read_started = Event(), Event(), Event()
    client = MagicMock()
    client.artifacts.upload.return_value = MagicMock(id="remote")
    if phase == "delete_remote_artifact":
        error = NotFoundError(
            "gone",
            response=httpx.Response(
                404, request=httpx.Request("POST", "https://example.test")
            ),
            body={},
        )
        client.artifacts.upload.side_effect = [error, MagicMock(id="remote")]
        client.artifacts.get_lineage.side_effect = error

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    def read():
        read_started.set()
        return facade.list_groups()

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(facade.artifacts, "_get_luml_client", return_value=client)
        )
        if phase == "save_experiment":
            from lumlflow.handlers.luml.artifacts import save_experiment

            original = save_experiment
            stack.enter_context(
                patch(
                    "lumlflow.handlers.luml.artifacts.save_experiment",
                    side_effect=blocked,
                )
            )
        else:
            original = (
                (lambda *a, **k: None)
                if phase == "link_to_model"
                else getattr(tracker, phase)
            )
            stack.enter_context(patch.object(tracker, phase, side_effect=blocked))
        with ThreadPoolExecutor(max_workers=2) as pool:
            worker = pool.submit(facade.upload_artifact, form, "job")
            try:
                assert entered.wait(5)
                local_read = pool.submit(read)
                assert read_started.wait(5)
                with pytest.raises(TimeoutError):
                    local_read.result(0.1)
            finally:
                release.set()
            assert worker.result(5).ok
            assert local_read.result(5).ok


@pytest.mark.parametrize(
    ("handler", "method", "args"),
    [
        ("luml", "get_luml_organizations", ()),
        ("luml", "get_luml_orbits", ("org",)),
        ("luml", "get_luml_collections", ("org", "orbit")),
        ("auth", "set_api_key", ("test-key",)),
    ],
)
def test_cloud_network_calls_allow_local_reads(
    facade: DataFacade, handler: str, method: str, args: tuple
) -> None:
    entered, release = Event(), Event()

    def network(*args, **kwargs):
        entered.set()
        assert release.wait(5)

    facade_method = {
        "get_luml_organizations": "list_organizations",
        "get_luml_orbits": "list_orbits",
        "get_luml_collections": "list_collections",
        "set_api_key": "set_api_key",
    }[method]
    with (
        patch.object(getattr(facade, handler), method, side_effect=network),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        worker = pool.submit(getattr(facade, facade_method), *args)
        try:
            assert entered.wait(5)
            assert pool.submit(facade.list_groups).result(1).ok
        finally:
            release.set()
        assert worker.result(5).ok


@pytest.mark.parametrize("stage", ["client", "lineage", "retry"])
def test_stale_lineage_network_phases_allow_local_reads(
    facade: DataFacade, tmp_path: Path, stage: str
) -> None:
    tracker = facade.tracker
    experiment_id = tracker.start_experiment(name="experiment")
    source = tmp_path / "model.luml"
    source.write_bytes(b"model")
    model, _ = tracker.backend.log_model(experiment_id, str(source), name="model")
    tracker.set_remote_artifact("experiment", experiment_id, "orbit", "stale")
    form = UploadModelForm(
        experiment_id=experiment_id,
        model_id=model.id,
        organization_id="org",
        orbit_id="orbit",
        collection_id="collection",
        artifact=ArtifactIn(),
    )
    facade.progress_store.create("job")
    entered, release = Event(), Event()
    error = NotFoundError(
        "gone",
        response=httpx.Response(
            404, request=httpx.Request("POST", "https://example.test")
        ),
        body={},
    )
    artifact = MagicMock(id="remote")
    client = MagicMock()

    def wait_for_read():
        entered.set()
        assert release.wait(5)

    def get_client(*args):
        if stage == "client":
            wait_for_read()
        return client

    def upload(**kwargs):
        if kwargs["lineage_inputs"] is not None:
            raise error
        if stage == "retry":
            wait_for_read()
        return artifact

    def get_lineage(*args, **kwargs):
        if stage == "lineage":
            wait_for_read()
        raise error

    client.artifacts.upload.side_effect = upload
    client.artifacts.get_lineage.side_effect = get_lineage
    with (
        patch.object(facade.artifacts, "_get_luml_client", side_effect=get_client),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        worker = pool.submit(facade.upload_model_artifact, form, "job")
        try:
            assert entered.wait(5)
            assert pool.submit(facade.list_groups).result(1).ok
        finally:
            release.set()
        assert worker.result(5).ok
    job = facade.progress_store.get("job")
    assert job is not None and job.status == "complete"
    assert tracker.get_remote_artifact("experiment", experiment_id, "orbit") is None
    assert tracker.get_remote_artifact("model", model.id, "orbit") == "remote"
