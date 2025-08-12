import json
import tarfile
import tempfile
from pathlib import Path

from dataforce.modelref import DiskArtifact


def generate_index(file: tarfile.TarFile) -> dict[str, tuple[int, int]]:
    index = {}
    for member in file.getmembers():
        name = member.name
        if member.isdir() and not name.endswith("/"):
            name += "/"
        offset = member.offset  # always available, even for dirs
        size = member.size if member.isfile() else 0
        index[name] = (offset, size)
    return index


def create_and_index_tar(source_dir: str | Path) -> tuple[DiskArtifact, DiskArtifact]:
    source_dir = Path(source_dir)
    if not source_dir.is_dir():
        raise ValueError(
            f"Source directory {source_dir} does not exist or is not a directory."
        )

    with tempfile.NamedTemporaryFile(delete=False) as temp_tar:
        tar_path = Path(temp_tar.name)

    with tarfile.open(tar_path, "w") as tar:
        tar.add(source_dir, arcname=source_dir.name)
    with tarfile.open(tar_path, "r") as tar:
        index_data = generate_index(tar)

    artifact = DiskArtifact(tar_path)

    index_path = tar_path.with_suffix(".index.json")
    with open(index_path, "w+") as index_file:
        json.dump(index_data, index_file)

    index_artifact = DiskArtifact(index_path)

    return artifact, index_artifact
