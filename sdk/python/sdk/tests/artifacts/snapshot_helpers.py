import io
import json
import re
import sqlite3
import tarfile
import zipfile
from pathlib import Path
from typing import Any

from luml.utils.tar import generate_index

SNAPSHOT_PAGE_SIZE = 16384
SNAPSHOT_MEMBER = re.compile(
    r"^(meta_artifacts/dataforce\.studio~c~~c~experiment_snapshot~c~v[12]~~et~~[^/]+/)?"
    r"exp\.db(\.zip)?$"
)


def snapshot_member(names: list[str]) -> str:
    """How readers find the database: the member name decides the transport."""
    candidates = [name for name in names if SNAPSHOT_MEMBER.match(name)]
    assert len(candidates) == 1, names
    return candidates[0]


def extract_snapshot_db(artifact: Path, dest: Path) -> str:
    """Writes the artifact's experiment database to `dest` through the tar's file
    index, as a range reader would; returns the member it came from."""
    with tarfile.open(artifact) as tar:
        index = generate_index(tar)
    member = snapshot_member(list(index))
    offset, size = index[member]
    with open(artifact, "rb") as source, open(dest, "wb") as target:
        source.seek(offset)
        if member.endswith(".zip"):
            data = source.read(size)
            target.write(zipfile.ZipFile(io.BytesIO(data)).read("exp.db"))
        else:
            remaining = size
            while remaining:
                chunk = source.read(min(remaining, 1 << 20))
                target.write(chunk)
                remaining -= len(chunk)
    return member


def read_member(artifact: Path, name: str) -> bytes:
    with tarfile.open(artifact) as tar:
        extracted = tar.extractfile(name)
        assert extracted is not None
        return extracted.read()


def read_json_member(artifact: Path, name: str) -> Any:  # noqa: ANN401
    return json.loads(read_member(artifact, name))


def connect_read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.absolute().as_uri()}?mode=ro", uri=True)


def assert_publishable_db(path: Path) -> None:
    """Page size 16384, not WAL, intact."""
    with open(path, "rb") as file:
        header = file.read(100)
    assert header[:16] == b"SQLite format 3\x00"
    assert int.from_bytes(header[16:18], "big") == SNAPSHOT_PAGE_SIZE
    assert (header[18], header[19]) == (1, 1), "the snapshot must not be in WAL mode"
    conn = connect_read_only(path)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert conn.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    finally:
        conn.close()


def table_rows(conn: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    """Every row of every table, in an order independent of the physical layout."""
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    rows: dict[str, list[tuple[Any, ...]]] = {}
    for table in tables:
        width = len(conn.execute(f'SELECT * FROM "{table}" LIMIT 0').description)
        order = ", ".join(str(column) for column in range(1, width + 1))
        rows[table] = conn.execute(
            f'SELECT * FROM "{table}" ORDER BY {order}'
        ).fetchall()
    return rows


def schema_objects(conn: sqlite3.Connection) -> list[tuple[str, str, str | None]]:
    return conn.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_autoindex%' ORDER BY type, name"
    ).fetchall()


def live_database_state(db_path: Path) -> dict[str, Any]:
    """What an export must not change about a live database."""
    with open(db_path, "rb") as file:
        header = file.read(100)
    conn = connect_read_only(db_path)
    try:
        return {
            "schema": schema_objects(conn),
            "page_size": conn.execute("PRAGMA page_size").fetchone()[0],
            "wal_header": (header[18], header[19]),
            "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
            "user_version": conn.execute("PRAGMA user_version").fetchone()[0],
            "rows": table_rows(conn),
        }
    finally:
        conn.close()


def copy_with_layout(db_path: Path, dest: Path) -> Path:
    """A page-for-page copy, so the physical layout of `db_path` can be inspected."""
    source = connect_read_only(db_path)
    target = sqlite3.connect(dest)
    try:
        source.backup(target)
    finally:
        source.close()
        target.close()
    return dest
