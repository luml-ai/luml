"""Read the experiment snapshot DB out of a published artifact (stdlib only)."""

import io
import re
import sqlite3
import tarfile
import tempfile
import zipfile

SNAPSHOT_RE = re.compile(
    r"meta_artifacts/dataforce\.studio~c~~c~experiment_snapshot~c~v1~~et~~[^/]+/exp\.db\.zip$|^exp\.db\.zip$"
)


def load_snapshot(path: str) -> tuple[str, bytes, list[str]]:
    with tarfile.open(path) as tar:
        names = tar.getnames()
        name = next(n for n in names if SNAPSHOT_RE.search(n))
        data = tar.extractfile(name).read()  # type: ignore[union-attr]
    return name, data, names


def open_db(
    zip_bytes: bytes,
) -> tuple[sqlite3.Connection, list[zipfile.ZipInfo], bytes]:
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    db_bytes = zf.read("exp.db")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(db_bytes)
    return (
        sqlite3.connect(f"file:{tmp.name}?mode=ro", uri=True),
        zf.infolist(),
        db_bytes,
    )
