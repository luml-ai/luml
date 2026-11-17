"""Search fixture files for local identity strings: raw bytes plus every nested layer.

Layers: the outer tar, each member, the inflated exp.db, and the inner attachments.tar.
Usage: privacy_grep.py <fixture_dir> <pattern> [<pattern> ...]
"""

import io
import sys
import tarfile
import zipfile
from pathlib import Path


def layers(path: Path) -> list[tuple[str, bytes]]:
    raw = path.read_bytes()
    found = [(str(path.name), raw)]
    if path.suffix != ".tar":
        return found
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            data = tar.extractfile(member).read()  # type: ignore[union-attr]
            found.append((f"{path.name}:{member.name}", data))
            if member.name.endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    for name in archive.namelist():
                        found.append(
                            (f"{path.name}:{member.name}:{name}", archive.read(name))
                        )
            if member.name.endswith("attachments.tar"):
                with tarfile.open(fileobj=io.BytesIO(data)) as inner:
                    for item in inner.getmembers():
                        header = (
                            f"{item.uname} {item.gname} {item.uid} {item.gid}".encode()
                        )
                        found.append(
                            (f"{path.name}:{member.name}:{item.name}:header", header)
                        )
    return found


fixture_dir = Path(sys.argv[1])
patterns = [pattern.encode() for pattern in sys.argv[2:]]
hits = 0
scanned = 0
files = sorted(path for path in fixture_dir.rglob("*") if path.is_file())
for path in files:
    for label, data in layers(path):
        scanned += 1
        for pattern in patterns:
            if pattern.lower() in data.lower():
                hits += 1
                sys.stdout.write(f"HIT {pattern.decode()} in {label}\n")
sys.stdout.write(f"scanned {scanned} layers of {len(files)} files, {hits} hits\n")
