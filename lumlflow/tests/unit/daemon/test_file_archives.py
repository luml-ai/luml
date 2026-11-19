import asyncio
import io
import json
import tarfile
from pathlib import Path
from unittest.mock import ANY, Mock

import polars as pl
import pytest
from fnnx.extras.builder import PyfuncBuilder  # type: ignore[import-untyped]
from luml.artifacts.dataset import save_hf_dataset, save_tabular_dataset
from luml.artifacts.experiment import save_experiment
from luml.artifacts.model import ModelReference
from luml.integrations.sklearn.packaging._template import SKlearnPyFunc
from luml.utils.packaging import embed_reference_profile
from lumlflow.api.luml import artifact_handler, progress_store
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.errors import FlowError
from lumlflow.tracker import TrackerProvider


@pytest.fixture
def api(tmp_path: Path) -> Api:
    return Api(Hub(), directory=tmp_path)


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    path = tmp_path / "weather.v1.luml"
    frame = pl.DataFrame({"temp": [12, 15, 14]})
    source = tmp_path / "test.parquet"
    frame.write_parquet(source)
    save_tabular_dataset(
        {"train": frame, "test": source},
        chunk_size=2,
        name="Weather",
        output_path=str(path),
    )
    return path


def _record_member_reads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    reads = []
    extractfile = tarfile.TarFile.extractfile

    def record_read(tar, member):
        reads.append(member.name)
        return extractfile(tar, member)

    monkeypatch.setattr(tarfile.TarFile, "extractfile", record_read)
    return reads


async def test_inspect_sdk_tabular_dataset(
    api: Api, dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads = _record_member_reads(monkeypatch)
    result = await api.methods["file.inspect"]({"path": str(dataset)})
    assert reads == ["manifest.json"]
    assert result["kind"] == "dataset"
    assert result["variant"] == "tabular"
    assert result["manifest"]["name"] == "Weather"
    assert result["splits"] == [
        {
            "subset": "default",
            "name": "train",
            "format": "parquet",
            "files": [
                "data/default/train/chunk_000.parquet",
                "data/default/train/chunk_001.parquet",
            ],
            "num_rows": 3,
        },
        {
            "subset": "default",
            "name": "test",
            "format": "parquet",
            "files": ["data/default/test/chunk_000.parquet"],
            "num_rows": None,
        },
    ]
    with tarfile.open(dataset) as tar:
        assert result["files"] == [
            {"name": entry.name, "size": entry.size} for entry in tar if entry.isfile()
        ]


async def test_inspect_sdk_hf_dataset(api: Api, tmp_path: Path) -> None:
    datasets = pytest.importorskip("datasets")
    path = tmp_path / "weather.luml"
    train = datasets.Dataset.from_dict({"temp": [12, 15, 14]})
    train.info.splits = datasets.SplitDict()
    train.info.splits.add(datasets.SplitInfo(name="train", num_examples=3))
    test = datasets.Dataset.from_dict({"temp": [8]})
    save_hf_dataset(
        {"weather": datasets.DatasetDict({"train": train, "test": test})},
        output_path=str(path),
    )

    result = await api.methods["file.inspect"]({"path": str(path)})
    assert (result["kind"], result["variant"]) == ("dataset", "hf")
    assert result["splits"] == [
        {
            "subset": "weather",
            "name": name,
            "format": "arrow",
            "files": [f"data/weather/{name}/data-00000-of-00001.arrow"],
            "num_rows": count,
        }
        for name, count in [("train", 3), ("test", None)]
    ]


async def test_inspect_sdk_experiment(
    api: Api, tracker: TrackerProvider, tmp_path: Path
) -> None:
    path = tmp_path / "run.luml"
    experiment_id = tracker.start_experiment(name="Weather")
    save_experiment(tracker.tracker, experiment_id, str(path))
    result = await api.methods["file.inspect"]({"path": str(path)})

    assert result["kind"] == "experiment"
    assert result["manifest"]["payload"]["local_experiment_id"] == experiment_id
    assert {entry["name"] for entry in result["files"]} >= {
        "manifest.json",
        "exp.db.zip",
    }


async def test_inspect_sdk_model(
    api: Api, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "predictor.luml"
    PyfuncBuilder(SKlearnPyFunc, model_name="Weather").save(str(path))
    embed_reference_profile(str(path), {"features": {"temp": {"mean": 14}}})
    assert ModelReference(str(path)).validate()
    reads = _record_member_reads(monkeypatch)
    result = await api.methods["file.inspect"]({"path": str(path)})

    assert result["kind"] == "model"
    assert result["manifest"]["name"] == "Weather"
    assert {"variant_artifacts/__pyfunc__.py", "reference_profile.json"} <= {
        entry["name"] for entry in result["files"]
    }
    assert set(reads) == {"manifest.json", "meta.json", "env.json"}


async def test_unreadable_package_is_unknown(api: Api, tmp_path: Path) -> None:
    path = tmp_path / "invalid.luml"
    path.write_text("unknown")
    assert await api.methods["file.inspect"]({"path": str(path)}) == {
        "kind": "unknown",
        "manifest": None,
        "files": [],
    }


def _append_json(path: Path, name: str, value: object) -> None:
    data = json.dumps(value).encode()
    member = tarfile.TarInfo(name)
    member.size = len(data)
    with tarfile.open(path, "a") as tar:
        tar.addfile(member, io.BytesIO(data))


@pytest.mark.parametrize("payload", [None, [], {"subsets": {"default": []}}])
async def test_dataset_with_incomplete_payload_can_still_show_its_manifest(
    api: Api, dataset: Path, payload: object
) -> None:
    manifest = {"artifact_type": "dataset", "variant": "tabular", "payload": payload}
    _append_json(dataset, "manifest.json", manifest)
    result = await api.methods["file.inspect"]({"path": str(dataset)})
    assert (result["kind"], result["manifest"], result["splits"]) == (
        "dataset",
        manifest,
        [],
    )


@pytest.mark.parametrize(
    "counts",
    [None, [], {"train": None}, {"train": []}, {"train": {"num_examples": "3"}}],
)
async def test_invalid_hf_split_metadata_leaves_row_count_unknown(
    api: Api, dataset: Path, counts: object
) -> None:
    manifest = {
        "artifact_type": "dataset",
        "variant": "hf",
        "payload": {
            "subsets": {"default": ["train"]},
            "library_version": "1",
            "data_dir": "data/",
        },
    }
    _append_json(dataset, "manifest.json", manifest)
    _append_json(dataset, "data/default/train/dataset_info.json", {"splits": counts})
    result = await api.methods["file.inspect"]({"path": str(dataset)})
    assert result["splits"] == [
        {
            "subset": "default",
            "name": "train",
            "format": "arrow",
            "files": [],
            "num_rows": None,
        }
    ]


@pytest.mark.parametrize("method", ["file.inspect", "file.publish"])
async def test_only_luml_files_are_accepted(api: Api, tmp_path: Path, method: str):
    path = tmp_path / "notes.txt"
    path.touch()
    with pytest.raises(FlowError, match=r"\.luml"):
        await api.methods[method]({"path": str(path)})


@pytest.mark.parametrize(
    "invalid",
    [
        {"organization_id": []},
        {"artifact": ["name"]},
        {"artifact": {"name": "Weather", "tags": "climate"}},
    ],
)
async def test_invalid_upload_form_is_refused_before_starting_a_job(
    api: Api, dataset: Path, invalid: dict
) -> None:
    params = {
        "path": str(dataset),
        "organization_id": "org",
        "orbit_id": "orbit",
        "collection_id": "collection",
        "artifact": {"name": "Weather"},
    }
    with pytest.raises(FlowError):
        await api.file_publish(params | invalid)
    assert not api._uploads
    assert dataset.is_file()


async def test_publish_uploads_the_dataset_and_preserves_the_source(
    api: Api, dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = Mock()
    get_client = Mock(return_value=client)

    def upload(file_path, **kwargs):
        # Simulate a workspace replacement between registration and transfer.
        source = Path(file_path)
        registered = source.read_bytes()
        replacement = dataset.with_suffix(".new")
        replacement.write_bytes(b"new version")
        replacement.replace(dataset)
        assert source.read_bytes() == registered == original
        return Mock(model_dump=Mock(return_value={"id": "uploaded"}))

    client.artifacts.upload.side_effect = upload
    monkeypatch.setattr(artifact_handler, "_get_luml_client", get_client)
    original = dataset.read_bytes()

    result = await api.methods["file.publish"](
        {
            "path": str(dataset),
            "organization_id": "org",
            "orbit_id": "orbit",
            "collection_id": "collection",
            "artifact": {
                "name": "Weather",
                "description": "Daily",
                "tags": ["climate"],
            },
        }
    )
    await asyncio.gather(*api._uploads)

    job = progress_store.get(result["job_id"])
    assert job is not None
    assert (job.status, job.percent, job.result) == (
        "complete",
        100,
        [{"id": "uploaded"}],
    )
    get_client.assert_called_once_with("org", "orbit")
    client.artifacts.upload.assert_called_once_with(
        file_path=ANY,
        name="Weather",
        description="Daily",
        tags=["climate"],
        collection_id="collection",
        on_progress=ANY,
    )
    assert dataset.read_bytes() == b"new version"
    assert not Path(client.artifacts.upload.call_args.kwargs["file_path"]).exists()
