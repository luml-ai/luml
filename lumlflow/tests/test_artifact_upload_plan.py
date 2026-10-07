from pathlib import Path
from typing import Any

import pytest
from lumlflow.handlers.luml.artifacts import ArtifactHandler, UploadPlan, upload_plan
from lumlflow.infra.progress_store import ProgressStore
from lumlflow.schemas.luml import ArtifactIn, UploadArtifactForm, UploadType


@pytest.mark.parametrize(
    ("upload_type", "embed", "models", "plan"),
    [
        (
            UploadType.AUTO,
            False,
            0,
            UploadPlan(models=True, embed=False, experiment=True),
        ),
        (
            UploadType.AUTO,
            False,
            1,
            UploadPlan(models=True, embed=True, experiment=False),
        ),
        (
            UploadType.AUTO,
            True,
            2,
            UploadPlan(models=True, embed=True, experiment=True),
        ),
        (
            UploadType.MODEL,
            True,
            2,
            UploadPlan(models=True, embed=True, experiment=False),
        ),
        (
            UploadType.MODEL,
            False,
            1,
            UploadPlan(models=True, embed=False, experiment=False),
        ),
        (
            UploadType.EXPERIMENT,
            True,
            3,
            UploadPlan(models=False, embed=False, experiment=True),
        ),
    ],
)
def test_upload_plan(
    upload_type: UploadType, embed: bool, models: int, plan: UploadPlan
) -> None:
    assert upload_plan(upload_type, embed, models) == plan


class _Uploaded:
    def model_dump(self) -> dict[str, Any]:
        return {}


def _form(upload_type: UploadType) -> UploadArtifactForm:
    return UploadArtifactForm(
        upload_type=upload_type,
        experiment_id="exp",
        organization_id="org",
        orbit_id="orbit",
        collection_id="coll",
        artifact=ArtifactIn(name="run"),
    )


def test_without_model_files_the_experiments_linked_models_go(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    store = ProgressStore()
    handler = ArtifactHandler.__new__(ArtifactHandler)
    handler.progress_store = store
    linked = [SimpleNamespace(name=name) for name in ("forest", "boost")]
    handler.tracker = SimpleNamespace(get_models=lambda experiment_id: linked)
    calls: list[tuple[Any, ...]] = []

    def upload_model(data, model, embed, on_progress):
        calls.append(("model", model.name, embed, data.artifact.name))
        return _Uploaded()

    def upload_experiment(data, on_progress):
        calls.append(("experiment", data.artifact.name))
        return _Uploaded()

    monkeypatch.setattr(handler, "_upload_model", upload_model)
    monkeypatch.setattr(handler, "_upload_experiment", upload_experiment)
    monkeypatch.setattr(store, "set_complete", lambda job_id, results: None)

    handler.upload_model_files(_form(UploadType.AUTO), "job", [])

    assert calls == [
        ("model", "forest", True, "run_1"),
        ("model", "boost", True, "run_2"),
        ("experiment", "run"),
    ]


@pytest.mark.parametrize(
    ("models", "sent"),
    [
        (["forest"], [("model", "forest", True, "run")]),
        (
            ["forest", "boost"],
            [
                ("model", "forest", True, "run_1"),
                ("model", "boost", True, "run_2"),
                ("experiment", "run"),
            ],
        ),
    ],
)
def test_model_files_follow_the_auto_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, models: list[str], sent: list[Any]
) -> None:
    store = ProgressStore()
    handler = ArtifactHandler.__new__(ArtifactHandler)
    handler.progress_store = store
    calls: list[tuple[Any, ...]] = []

    def upload_model_file(data, path, name, embed, on_progress):
        calls.append(("model", name, embed, data.artifact.name))
        return _Uploaded()

    def upload_experiment(data, on_progress):
        calls.append(("experiment", data.artifact.name))
        return _Uploaded()

    monkeypatch.setattr(handler, "_upload_model_file", upload_model_file)
    monkeypatch.setattr(handler, "_upload_experiment", upload_experiment)
    monkeypatch.setattr(store, "set_complete", lambda job_id, results: None)

    handler.upload_model_files(
        _form(UploadType.AUTO), "job", [(tmp_path / name, name) for name in models]
    )

    assert calls == sent
