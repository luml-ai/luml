from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from luml.experiments.backends.data_types import Model as DbModel
from luml.experiments.tracker import ExperimentTracker
from luml_api._exceptions import NotFoundError
from lumlflow.handlers.luml.artifacts import ArtifactHandler
from lumlflow.infra.progress_store import ProgressStore
from lumlflow.schemas.luml import (
    ArtifactIn,
    UploadArtifactForm,
    UploadModelForm,
    UploadType,
)


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def handler(tracker: ExperimentTracker) -> ArtifactHandler:
    artifact_handler = ArtifactHandler(progress_store=ProgressStore())
    artifact_handler.tracker = tracker
    return artifact_handler


def _seed_experiment(
    tracker: ExperimentTracker, tmp_path: Path, model_names: list[str]
) -> tuple[str, list[DbModel]]:
    tracker.create_group("group")
    experiment_id = tracker.start_experiment(name="experiment", group="group")
    models = []
    for name in model_names:
        source = tmp_path / f"{name}.luml"
        source.write_bytes(name.encode())
        model, _ = tracker.backend.log_model(experiment_id, str(source), name=name)
        models.append(model)
    return experiment_id, models


def _artifact_form(
    experiment_id: str,
    upload_type: UploadType,
    *,
    orbit_id: str = "orbit-1",
) -> UploadArtifactForm:
    return UploadArtifactForm(
        upload_type=upload_type,
        experiment_id=experiment_id,
        organization_id="organization-1",
        orbit_id=orbit_id,
        collection_id="collection-1",
        artifact=ArtifactIn(),
    )


def _model_form(
    experiment_id: str, model_id: str, *, orbit_id: str = "orbit-1"
) -> UploadModelForm:
    return UploadModelForm(
        model_id=model_id,
        experiment_id=experiment_id,
        organization_id="organization-1",
        orbit_id=orbit_id,
        collection_id="collection-1",
        artifact=ArtifactIn(),
    )


def _uploaded_artifact(artifact_id: str) -> MagicMock:
    artifact = MagicMock()
    artifact.id = artifact_id
    artifact.model_dump.return_value = {"id": artifact_id}
    return artifact


def _not_found_error(
    detail: str = "Artifact not found", method: str = "POST"
) -> NotFoundError:
    request = httpx.Request(method, "https://api.luml.test/artifacts")
    response = httpx.Response(404, request=request)
    return NotFoundError(
        detail,
        response=response,
        body={"detail": detail},
    )


def _start_job(handler: ArtifactHandler, job_id: str) -> None:
    handler.progress_store.create(job_id)


class TestOrderedPublish:
    def test_auto_uploads_experiment_before_models_and_remembers_all(
        self,
        handler: ArtifactHandler,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        experiment_id, models = _seed_experiment(
            tracker, tmp_path, ["model-1", "model-2"]
        )
        client = MagicMock()
        client.artifacts.upload.side_effect = [
            _uploaded_artifact("experiment-artifact"),
            _uploaded_artifact("model-artifact-1"),
            _uploaded_artifact("model-artifact-2"),
        ]
        _start_job(handler, "job-auto-many")

        with (
            patch.object(handler, "_get_luml_client", return_value=client),
            patch("lumlflow.handlers.luml.artifacts.save_experiment"),
            patch.object(tracker, "link_to_model"),
        ):
            handler.upload_artifact(
                _artifact_form(experiment_id, UploadType.AUTO),
                "job-auto-many",
            )

        calls = client.artifacts.upload.call_args_list
        assert [item.kwargs["name"] for item in calls] == [
            "experiment",
            "model-1",
            "model-2",
        ]
        assert calls[0].kwargs.get("lineage_inputs") is None
        assert calls[1].kwargs["lineage_inputs"] == ["experiment-artifact"]
        assert calls[2].kwargs["lineage_inputs"] == ["experiment-artifact"]
        assert (
            tracker.get_remote_artifact("experiment", experiment_id, "orbit-1")
            == "experiment-artifact"
        )
        assert (
            tracker.get_remote_artifact("model", models[0].id, "orbit-1")
            == "model-artifact-1"
        )
        assert (
            tracker.get_remote_artifact("model", models[1].id, "orbit-1")
            == "model-artifact-2"
        )
        job = handler.progress_store.get("job-auto-many")
        assert job is not None
        assert job.status == "complete"
        assert job.result == [
            {"id": "experiment-artifact"},
            {"id": "model-artifact-1"},
            {"id": "model-artifact-2"},
        ]

    def test_model_mode_without_mapping_uploads_models_unlinked(
        self,
        handler: ArtifactHandler,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        experiment_id, models = _seed_experiment(
            tracker, tmp_path, ["model-1", "model-2"]
        )
        client = MagicMock()
        client.artifacts.upload.side_effect = [
            _uploaded_artifact("model-artifact-1"),
            _uploaded_artifact("model-artifact-2"),
        ]
        _start_job(handler, "job-models")

        with patch.object(handler, "_get_luml_client", return_value=client):
            handler.upload_artifact(
                _artifact_form(experiment_id, UploadType.MODEL), "job-models"
            )

        calls = client.artifacts.upload.call_args_list
        assert len(calls) == 2
        assert all(item.kwargs.get("lineage_inputs") is None for item in calls)
        assert (
            tracker.get_remote_artifact("experiment", experiment_id, "orbit-1") is None
        )
        assert (
            tracker.get_remote_artifact("model", models[0].id, "orbit-1")
            == "model-artifact-1"
        )
        assert (
            tracker.get_remote_artifact("model", models[1].id, "orbit-1")
            == "model-artifact-2"
        )

    @pytest.mark.parametrize(
        ("remembered_id", "expected_lineage"),
        [(None, None), ("experiment-artifact", ["experiment-artifact"])],
    )
    def test_auto_single_model_embeds_and_uses_optional_mapping(
        self,
        handler: ArtifactHandler,
        tracker: ExperimentTracker,
        tmp_path: Path,
        remembered_id: str | None,
        expected_lineage: list[str] | None,
    ) -> None:
        experiment_id, models = _seed_experiment(tracker, tmp_path, ["model"])
        if remembered_id is not None:
            tracker.set_remote_artifact(
                "experiment", experiment_id, "orbit-1", remembered_id
            )
        client = MagicMock()
        client.artifacts.upload.return_value = _uploaded_artifact("model-artifact")
        _start_job(handler, "job-auto-one")

        with (
            patch.object(handler, "_get_luml_client", return_value=client),
            patch.object(tracker, "link_to_model") as link_to_model,
        ):
            handler.upload_artifact(
                _artifact_form(experiment_id, UploadType.AUTO),
                "job-auto-one",
            )

        link_to_model.assert_called_once()
        kwargs = client.artifacts.upload.call_args.kwargs
        if expected_lineage is None:
            assert kwargs.get("lineage_inputs") is None
        else:
            assert kwargs["lineage_inputs"] == expected_lineage
        assert (
            tracker.get_remote_artifact("model", models[0].id, "orbit-1")
            == "model-artifact"
        )


class TestRememberedExperiment:
    def test_upload_model_uses_remembered_experiment_without_lookup(
        self,
        handler: ArtifactHandler,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        experiment_id, models = _seed_experiment(tracker, tmp_path, ["model"])
        tracker.set_remote_artifact(
            "experiment", experiment_id, "orbit-1", "experiment-artifact"
        )
        client = MagicMock()
        client.artifacts.upload.return_value = _uploaded_artifact("model-artifact")
        _start_job(handler, "job-single")

        with patch.object(handler, "_get_luml_client", return_value=client):
            handler.upload_model(_model_form(experiment_id, models[0].id), "job-single")

        client.artifacts.upload.assert_called_once()
        assert client.artifacts.upload.call_args.kwargs["lineage_inputs"] == [
            "experiment-artifact"
        ]
        assert [item[0] for item in client.artifacts.method_calls] == ["upload"]
        assert (
            tracker.get_remote_artifact("model", models[0].id, "orbit-1")
            == "model-artifact"
        )

    def test_upload_model_without_mapping_does_not_query_platform(
        self,
        handler: ArtifactHandler,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        experiment_id, models = _seed_experiment(tracker, tmp_path, ["model"])
        client = MagicMock()
        client.artifacts.upload.return_value = _uploaded_artifact("model-artifact")
        _start_job(handler, "job-no-mapping")

        with patch.object(handler, "_get_luml_client", return_value=client):
            handler.upload_model(
                _model_form(experiment_id, models[0].id), "job-no-mapping"
            )

        client.artifacts.upload.assert_called_once()
        assert client.artifacts.upload.call_args.kwargs.get("lineage_inputs") is None
        assert [item[0] for item in client.artifacts.method_calls] == ["upload"]

    def test_stale_mapping_is_deleted_and_upload_retried_without_lineage(
        self,
        handler: ArtifactHandler,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        experiment_id, models = _seed_experiment(tracker, tmp_path, ["model"])
        tracker.set_remote_artifact(
            "experiment", experiment_id, "orbit-1", "stale-artifact"
        )
        client = MagicMock()
        client.artifacts.upload.side_effect = [
            _not_found_error(),
            _uploaded_artifact("model-artifact"),
        ]
        client.artifacts.get_lineage.side_effect = _not_found_error(method="GET")
        _start_job(handler, "job-stale")

        with patch.object(handler, "_get_luml_client", return_value=client):
            handler.upload_model(_model_form(experiment_id, models[0].id), "job-stale")

        calls = client.artifacts.upload.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["lineage_inputs"] == ["stale-artifact"]
        assert calls[1].kwargs.get("lineage_inputs") is None
        assert (
            tracker.get_remote_artifact("experiment", experiment_id, "orbit-1") is None
        )
        assert (
            tracker.get_remote_artifact("model", models[0].id, "orbit-1")
            == "model-artifact"
        )
        job = handler.progress_store.get("job-stale")
        assert job is not None
        assert job.status == "complete"

    def test_mapping_from_another_orbit_is_ignored(
        self,
        handler: ArtifactHandler,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        experiment_id, models = _seed_experiment(tracker, tmp_path, ["model"])
        tracker.set_remote_artifact(
            "experiment", experiment_id, "orbit-x", "foreign-artifact"
        )
        client = MagicMock()
        client.artifacts.upload.return_value = _uploaded_artifact("model-artifact")
        _start_job(handler, "job-other-orbit")

        with patch.object(handler, "_get_luml_client", return_value=client):
            handler.upload_model(
                _model_form(experiment_id, models[0].id, orbit_id="orbit-y"),
                "job-other-orbit",
            )

        assert client.artifacts.upload.call_args.kwargs.get("lineage_inputs") is None
        assert (
            tracker.get_remote_artifact("experiment", experiment_id, "orbit-x")
            == "foreign-artifact"
        )
        assert (
            tracker.get_remote_artifact("experiment", experiment_id, "orbit-y") is None
        )
        assert (
            tracker.get_remote_artifact("model", models[0].id, "orbit-y")
            == "model-artifact"
        )


class TestLinkingFailures:
    @pytest.mark.parametrize(
        ("error", "test_id"),
        [
            (_not_found_error("Collection not found"), "unrelated-create-error"),
            (_not_found_error(method="PATCH"), "error-after-create"),
        ],
    )
    def test_unrelated_not_found_is_not_treated_as_a_stale_mapping(
        self,
        handler: ArtifactHandler,
        tracker: ExperimentTracker,
        tmp_path: Path,
        error: NotFoundError,
        test_id: str,
    ) -> None:
        experiment_id, models = _seed_experiment(tracker, tmp_path, ["model"])
        tracker.set_remote_artifact(
            "experiment", experiment_id, "orbit-1", "experiment-artifact"
        )
        client = MagicMock()
        client.artifacts.upload.side_effect = error
        # The remembered experiment still exists on the platform.
        client.artifacts.get_lineage.return_value = MagicMock()
        job_id = f"job-{test_id}"
        _start_job(handler, job_id)

        with patch.object(handler, "_get_luml_client", return_value=client):
            handler.upload_model(_model_form(experiment_id, models[0].id), job_id)

        client.artifacts.upload.assert_called_once()
        assert (
            tracker.get_remote_artifact("experiment", experiment_id, "orbit-1")
            == "experiment-artifact"
        )
        job = handler.progress_store.get(job_id)
        assert job is not None
        assert job.status == "error"
        assert str(error) in (job.error or "")

    def test_job_experiment_not_found_is_not_retried(
        self,
        handler: ArtifactHandler,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        experiment_id, models = _seed_experiment(
            tracker, tmp_path, ["model-1", "model-2"]
        )
        client = MagicMock()
        client.artifacts.upload.side_effect = [
            _uploaded_artifact("experiment-artifact"),
            _uploaded_artifact("model-artifact-1"),
            _not_found_error(),
        ]
        _start_job(handler, "job-link-error")

        with (
            patch.object(handler, "_get_luml_client", return_value=client),
            patch("lumlflow.handlers.luml.artifacts.save_experiment"),
            patch.object(tracker, "link_to_model"),
        ):
            handler.upload_artifact(
                _artifact_form(experiment_id, UploadType.AUTO),
                "job-link-error",
            )

        assert client.artifacts.upload.call_count == 3
        assert (
            tracker.get_remote_artifact("experiment", experiment_id, "orbit-1")
            == "experiment-artifact"
        )
        assert (
            tracker.get_remote_artifact("model", models[0].id, "orbit-1")
            == "model-artifact-1"
        )
        assert tracker.get_remote_artifact("model", models[1].id, "orbit-1") is None
        job = handler.progress_store.get("job-link-error")
        assert job is not None
        assert job.status == "error"
        assert "Artifact not found" in (job.error or "")
