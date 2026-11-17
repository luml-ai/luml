"""Derive raw-transport fixtures (uncompressed exp.db) from generation 1 fixtures.

Usage: fakeroot python -I gen_raw.py [<fixture_dir>]
<fixture_dir> defaults to the directory that contains this generators directory.

Each derived artifact keeps every member and tar header of its source, except that the
zipped DB becomes a raw `exp.db` (PRAGMA page_size = 16384; VACUUM INTO) and the v1
snapshot names and producer tags become v2. The DBs stay at their source revision, which
is a valid combination: transport and revision are independent.
"""

import io
import json
import sqlite3
import struct
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent
PAGE_SIZE = 16384

DERIVED = [
    ("d_sdk_0_5_0", "g_raw_sdk_0_5_0"),
    ("f_model_sdk_0_5_0", "h_raw_model_sdk_0_5_0"),
]

RENAMES = [
    (b"experiment_snapshot~c~v1~~", b"experiment_snapshot~c~v2~~"),
    (b"experiment_snapshot:v1", b"experiment_snapshot:v2"),
]


def to_v2(data: bytes) -> bytes:
    for old, new in RENAMES:
        data = data.replace(old, new)
    return data


def raw_db(zip_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "source.db"
        target = Path(tmp) / "exp.db"
        source.write_bytes(zipfile.ZipFile(io.BytesIO(zip_bytes)).read("exp.db"))
        connection = sqlite3.connect(source)
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
        connection.execute(f"PRAGMA page_size = {PAGE_SIZE}")
        connection.execute("VACUUM INTO ?", (str(target),))
        connection.close()
        data = target.read_bytes()
    check = sqlite3.connect(":memory:")
    check.deserialize(data)
    assert check.execute("PRAGMA user_version").fetchone()[0] == user_version
    assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    check.close()
    assert struct.unpack(">H", data[16:18])[0] == PAGE_SIZE
    assert data[18] == 1, "derived DB must not be in WAL mode"
    assert data[19] == 1, "derived DB must not be in WAL mode"
    return data


def derive_tar(source: Path, target: Path) -> str:
    snapshot_member = ""
    with (
        tarfile.open(source) as archive,
        tarfile.open(target, "w", format=archive.format) as output,
    ):
        for member in archive.getmembers():
            data = archive.extractfile(member).read() if member.isfile() else b""  # type: ignore[union-attr]
            info = tarfile.TarInfo(to_v2(member.name.encode()).decode())
            info.mode, info.mtime, info.type = member.mode, member.mtime, member.type
            info.uid, info.gid, info.uname, info.gname = 0, 0, "", ""
            if member.name.endswith("exp.db.zip"):
                data = raw_db(data)
                info.name = info.name.removesuffix(".zip")
                snapshot_member = info.name
            elif member.name.endswith(".json"):
                data = to_v2(data)
            info.size = len(data)
            output.addfile(info, io.BytesIO(data))
    return snapshot_member


for source_name, name in DERIVED:
    snapshot_member = derive_tar(DEST / f"{source_name}.tar", DEST / f"{name}.tar")
    description = json.loads((DEST / f"{source_name}.json").read_text(encoding="utf-8"))
    description.update(
        artifact=f"{name}.tar",
        snapshot_member=snapshot_member,
        transport="raw",
        derived_from=f"{source_name}.tar",
    )
    text = json.dumps(description, indent=2, ensure_ascii=False, allow_nan=False)
    (DEST / f"{name}.json").write_text(text + "\n", encoding="utf-8")
