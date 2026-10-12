from functools import partial
from pathlib import Path

import pytest

from luml.experiments.backends.sqlite import SQLiteBackend


@pytest.mark.parametrize("operation", ["read", "write", "tree"])
@pytest.mark.parametrize(
    "name",
    [
        "absolute",
        "../marker.txt",
        "folder/../marker.txt",
        r"C:\marker.txt",
        r"..\marker.txt",
    ],
)
def test_attachment_paths_cannot_escape_store(
    backend_with_experiment: tuple[SQLiteBackend, str],
    tmp_path: Path,
    operation: str,
    name: str,
) -> None:
    backend, experiment_id = backend_with_experiment
    marker = tmp_path / "marker.txt"
    marker.write_bytes(b"outside")
    name = str(marker) if name == "absolute" else name
    actions = {
        "write": partial(backend.log_attachment, experiment_id, name, b"changed", True),
        "read": partial(backend.get_attachment, experiment_id, name),
        "tree": partial(backend.list_attachments_tree, experiment_id, name),
    }
    with pytest.raises(ValueError, match="Attachment path"):
        actions[operation]()
    assert marker.read_bytes() == b"outside"
    assert backend.list_attachments(experiment_id) == []
    assert not (tmp_path / "experiments" / experiment_id / "marker.txt").exists()


@pytest.mark.parametrize("operation", ["read", "write", "tree"])
def test_attachment_symlinks_cannot_escape_store(
    backend_with_experiment: tuple[SQLiteBackend, str],
    tmp_path: Path,
    operation: str,
) -> None:
    backend, experiment_id = backend_with_experiment
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker.txt"
    marker.write_bytes(b"outside")
    attachments = tmp_path / "experiments" / experiment_id / "attachments"
    (attachments / "linked").symlink_to(outside, target_is_directory=True)
    actions = {
        "write": partial(
            backend.log_attachment, experiment_id, "linked/marker.txt", b"changed", True
        ),
        "read": partial(backend.get_attachment, experiment_id, "linked/marker.txt"),
        "tree": partial(backend.list_attachments_tree, experiment_id, "linked"),
    }
    with pytest.raises(ValueError, match="Attachment path"):
        actions[operation]()
    assert marker.read_bytes() == b"outside"


def test_nested_attachments_still_work(
    backend_with_experiment: tuple[SQLiteBackend, str],
) -> None:
    backend, experiment_id = backend_with_experiment
    backend.log_attachment(experiment_id, "nested/report.txt", "hello")
    assert backend.get_attachment(experiment_id, "nested/report.txt") == b"hello"
    nodes = backend.list_attachments_tree(experiment_id, "nested")
    assert [(node.name, node.path) for node in nodes] == [
        ("report.txt", "nested/report.txt")
    ]


@pytest.mark.parametrize("name", ["", ".", "missing.txt", "bad\x00name"])
def test_invalid_attachment_reads_raise_value_error(
    backend_with_experiment: tuple[SQLiteBackend, str], name: str
) -> None:
    backend, experiment_id = backend_with_experiment
    with pytest.raises(ValueError, match="not found|Invalid|embedded null"):
        backend.get_attachment(experiment_id, name)


def test_tree_hides_legacy_unsafe_attachment_names(
    backend_with_experiment: tuple[SQLiteBackend, str],
    tmp_path: Path,
) -> None:
    backend, experiment_id = backend_with_experiment
    connection = backend._get_experiment_connection(experiment_id)
    connection.executemany(
        "INSERT INTO attachments (id, name, file_path, size) VALUES (?, ?, ?, ?)",
        [
            ("absolute", str(tmp_path / "outside.txt"), "", 7),
            ("parent", "../bad", "", 3),
        ],
    )
    connection.commit()
    assert backend.list_attachments_tree(experiment_id) == []
