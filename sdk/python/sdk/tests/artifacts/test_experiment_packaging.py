import errno
import io
import os
import stat
import sys
import tarfile
from pathlib import Path

import pytest

from luml import (
    ExperimentReference,
    save_experiment,
)
from luml.artifacts._base import ArtifactManifest, DiskFile
from luml.artifacts._helpers import add_bytes_to_tar
from luml.experiments.tracker import ExperimentTracker

# Windows has no `geteuid`.
IS_ROOT = getattr(os, "geteuid", lambda: -1)() == 0


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def experiment_with_data(
    tracker: ExperimentTracker,
) -> tuple[ExperimentTracker, str]:
    exp_id = tracker.start_experiment(name="test-exp", tags=["test", "unit"])
    tracker.log_static("learning_rate", 0.001, experiment_id=exp_id)
    tracker.log_dynamic("loss", 0.5, step=0, experiment_id=exp_id)
    tracker.log_dynamic("loss", 0.3, step=1, experiment_id=exp_id)
    tracker.log_attachment("config.json", '{"key": "value"}', experiment_id=exp_id)
    tracker.end_experiment(exp_id)
    return tracker, exp_id


def test_save_experiment_returns_reference(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    assert isinstance(ref, ExperimentReference)
    assert Path(ref.path).exists()


def test_save_experiment_auto_path(
    experiment_with_data: tuple[ExperimentTracker, str],
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id)
    assert Path(ref.path).exists()
    Path(ref.path).unlink()


def test_tar_contains_expected_files(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    files = ref.list_files()
    assert "manifest.json" in files
    assert "exp.db" in files
    assert "attachments.tar" in files
    assert "attachments.index.json" in files


def test_exp_db_is_an_uncompressed_sqlite_database(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    assert ref.extract_file("exp.db").startswith(b"SQLite format 3\x00")


def test_manifest_content(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    manifest = ref.get_manifest()
    assert isinstance(manifest, ArtifactManifest)
    assert manifest.artifact_type == "experiment"
    assert isinstance(manifest.name, str)
    assert len(manifest.name) > 0
    assert manifest.payload.local_experiment_id == exp_id
    assert manifest.payload.tags == ["test", "unit"]


def test_reference_validates(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    assert ref.validate() is True


def test_save_without_attachments(tracker: ExperimentTracker, tmp_path: Path) -> None:
    exp_id = tracker.start_experiment()
    tracker.log_static("key", "value", experiment_id=exp_id)
    tracker.end_experiment(exp_id)

    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))
    assert ref.validate() is True
    assert "manifest.json" in ref.list_files()
    assert "exp.db" in ref.list_files()


@pytest.mark.skipif(IS_ROOT, reason="root ignores file modes")
def test_an_export_refused_by_a_read_only_target_keeps_the_earlier_export(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    output = tmp_path / "out" / "exp.tar"
    output.parent.mkdir()
    tracker.export(str(output), experiment_id=exp_id)
    earlier = output.read_bytes()
    output.chmod(0o444)

    with pytest.raises(PermissionError):
        tracker.export(str(output), experiment_id=exp_id)

    assert output.read_bytes() == earlier
    assert [path.name for path in output.parent.iterdir()] == ["exp.tar"]


def test_an_export_failing_midway_keeps_the_earlier_export(
    experiment_with_data: tuple[ExperimentTracker, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker, exp_id = experiment_with_data
    output = tmp_path / "out" / "exp.tar"
    output.parent.mkdir()
    tracker.export(str(output), experiment_id=exp_id)
    earlier = output.read_bytes()

    def failing_add_to_tar(self: DiskFile, tar: tarfile.TarFile, name: str) -> None:
        add_bytes_to_tar(tar, name, b"partial")
        raise OSError("disk failed")

    monkeypatch.setattr(DiskFile, "add_to_tar", failing_add_to_tar)
    with pytest.raises(OSError, match="disk failed"):
        tracker.export(str(output), experiment_id=exp_id)

    assert output.read_bytes() == earlier
    assert [path.name for path in output.parent.iterdir()] == ["exp.tar"]


def test_a_new_export_replaces_the_earlier_one(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    output = tmp_path / "out" / "exp.tar"
    output.parent.mkdir()
    tracker.export(str(output), experiment_id=exp_id)
    earlier = output.read_bytes()
    tracker.log_static("epochs", 3, experiment_id=exp_id)

    ref = tracker.export(str(output), experiment_id=exp_id)

    assert output.read_bytes() != earlier
    assert ref.validate() is True
    probe = output.parent / "probe"
    probe.write_bytes(b"")
    assert output.stat().st_mode == probe.stat().st_mode
    assert sorted(path.name for path in output.parent.iterdir()) == [
        "exp.tar",
        "probe",
    ]


@pytest.mark.skipif(IS_ROOT, reason="root ignores file modes")
def test_an_export_into_a_read_only_directory_writes_the_target_in_place(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    output = tmp_path / "out" / "exp.tar"
    output.parent.mkdir()
    tracker.export(str(output), experiment_id=exp_id)
    earlier = output.read_bytes()
    tracker.log_static("epochs", 3, experiment_id=exp_id)
    output.parent.chmod(0o555)
    try:
        ref = tracker.export(str(output), experiment_id=exp_id)
    finally:
        output.parent.chmod(0o755)

    assert output.read_bytes() != earlier
    assert ref.validate() is True
    assert [path.name for path in output.parent.iterdir()] == ["exp.tar"]


def test_an_export_onto_a_target_that_cannot_be_renamed_onto_writes_it_in_place(
    experiment_with_data: tuple[ExperimentTracker, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker, exp_id = experiment_with_data
    output = tmp_path / "out" / "exp.tar"
    output.parent.mkdir()
    tracker.export(str(output), experiment_id=exp_id)
    earlier = output.read_bytes()
    tracker.log_static("epochs", 3, experiment_id=exp_id)
    replace = os.replace

    def replace_across_devices(source: str | Path, target: str | Path) -> None:
        if Path(target) == output:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        replace(source, target)

    monkeypatch.setattr(os, "replace", replace_across_devices)
    ref = tracker.export(str(output), experiment_id=exp_id)

    assert output.read_bytes() != earlier
    assert ref.validate() is True
    assert [path.name for path in output.parent.iterdir()] == ["exp.tar"]


@pytest.mark.skipif(
    not Path("/dev/null").is_char_device(), reason="needs a device node"
)
def test_an_export_to_a_device_node_writes_through_it(
    experiment_with_data: tuple[ExperimentTracker, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker, exp_id = experiment_with_data
    real_open = os.open

    def open_without_siblings(
        path: str | Path, flags: int, *args: int, **kwargs: int
    ) -> int:
        # A sibling renamed onto the device would replace it with a regular file.
        assert not str(path).endswith(".partial")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", open_without_siblings)
    tracker.export("/dev/null", experiment_id=exp_id)

    assert Path("/dev/null").is_char_device()


def test_an_export_keeps_line_feed_bytes_as_they_are(
    tracker: ExperimentTracker, tmp_path: Path
) -> None:
    exp_id = tracker.start_experiment()
    payload = b"\n\r\n\x00\n" * 64
    tracker.log_attachment("lines.bin", payload, binary=True, experiment_id=exp_id)
    tracker.end_experiment(exp_id)

    ref = save_experiment(tracker, exp_id, output_path=str(tmp_path / "exp.tar"))

    archive = io.BytesIO(ref.extract_file("attachments.tar"))
    with tarfile.open(fileobj=archive) as nested:
        members = [member for member in nested.getmembers() if member.isfile()]
        extracted = nested.extractfile(members[0])
        assert extracted is not None
        assert extracted.read() == payload
    assert ref.extract_file("exp.db").startswith(b"SQLite format 3\x00")


def test_the_partial_export_is_opened_in_binary_mode(
    experiment_with_data: tuple[ExperimentTracker, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker, exp_id = experiment_with_data
    real_flag: int | None = getattr(os, "O_BINARY", None)
    binary_flag = real_flag if real_flag is not None else 1 << 30
    monkeypatch.setattr(os, "O_BINARY", binary_flag, raising=False)
    partial_flags: list[int] = []
    real_open = os.open

    def recording_open(path: str | Path, flags: int, *args: int, **kwargs: int) -> int:
        if str(path).endswith(".partial"):
            partial_flags.append(flags)
        # Only a made-up flag is kept from the real call; Windows needs its own.
        passed = flags if real_flag is not None else flags & ~binary_flag
        return real_open(path, passed, *args, **kwargs)

    monkeypatch.setattr(os, "open", recording_open)
    tracker.export(str(tmp_path / "exp.tar"), experiment_id=exp_id)

    assert partial_flags
    assert all(flags & binary_flag for flags in partial_flags)


def test_an_export_that_cannot_create_its_partial_file_keeps_the_earlier_export(
    experiment_with_data: tuple[ExperimentTracker, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker, exp_id = experiment_with_data
    output = tmp_path / "out" / "exp.tar"
    output.parent.mkdir()
    tracker.export(str(output), experiment_id=exp_id)
    earlier = output.read_bytes()
    real_open = os.open

    def open_without_inodes(
        path: str | Path, flags: int, *args: int, **kwargs: int
    ) -> int:
        if str(path).endswith(".partial"):
            raise OSError(errno.ENOSPC, "No space left on device")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", open_without_inodes)
    with pytest.raises(OSError, match="No space left"):
        tracker.export(str(output), experiment_id=exp_id)

    assert output.read_bytes() == earlier
    assert [path.name for path in output.parent.iterdir()] == ["exp.tar"]


@pytest.mark.skipif(sys.platform == "win32", reason="needs 255-byte names")
def test_an_export_to_a_long_file_name_still_replaces_the_target(
    experiment_with_data: tuple[ExperimentTracker, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker, exp_id = experiment_with_data
    output = tmp_path / ("e" * 251 + ".tar")
    replaced: list[Path] = []
    real_replace = os.replace

    def recording_replace(source: str | Path, target: str | Path) -> None:
        replaced.append(Path(target))
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", recording_replace)
    ref = tracker.export(str(output), experiment_id=exp_id)

    assert replaced == [output]
    assert ref.validate() is True


@pytest.mark.skipif(sys.platform == "win32", reason="needs POSIX file modes")
def test_a_replaced_export_keeps_the_earlier_file_mode(
    experiment_with_data: tuple[ExperimentTracker, str], tmp_path: Path
) -> None:
    tracker, exp_id = experiment_with_data
    output = tmp_path / "out" / "exp.tar"
    output.parent.mkdir()
    tracker.export(str(output), experiment_id=exp_id)
    output.chmod(0o604)
    tracker.log_static("epochs", 3, experiment_id=exp_id)

    tracker.export(str(output), experiment_id=exp_id)

    assert stat.S_IMODE(output.stat().st_mode) == 0o604
    assert [path.name for path in output.parent.iterdir()] == ["exp.tar"]
