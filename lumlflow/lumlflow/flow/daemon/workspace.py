import ipaddress
import json
import os
import platform
import re
import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

from lumlflow import __version__
from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.daemon.files import entry_path
from lumlflow.flow.dsl.tree import EXCLUDED_DIRS
from lumlflow.flow.errors import FlowAmbiguous, FlowError, FlowNotFound, OsError
from lumlflow.flow.store.flowstore import FLOW_SUFFIX, STORE_DIRNAME, store_dir

STATE_DIR_ENV = "LUMLFLOW_STATE_DIR"
LOGS_DIRNAME = "logs"
RECORD_NAME = "daemon.json"
LOCK_NAME = "daemon.lock"
LOG_NAME = "daemon.log"
NON_LOOPBACK_WARNING = (
    "The tracker API on this port is unauthenticated on a non-loopback bind."
)

_NETWORK_FILESYSTEMS = frozenset(
    {
        "9p",
        "afs",
        "cifs",
        "fuse.sshfs",
        "ncpfs",
        "nfs",
        "nfs4",
        "smbfs",
    }
)
_MOUNT_ESCAPE = re.compile(r"\\([0-7]{3})")


@dataclass(frozen=True)
class FlowRef:
    name: str
    path: Path
    relpath: str

    @property
    def address(self) -> str:
        return str(self.path)

    @property
    def has_store(self) -> bool:
        return store_dir(self.path).is_dir()


@dataclass(frozen=True)
class DaemonRecord:
    pid: int
    instance_id: str
    port: int
    token: str
    web_host: str
    web_port: int
    tracker_store: str
    version: str

    def to_json(self) -> bytes:
        return json.dumps(self.__dict__, sort_keys=True).encode("utf-8")


def entry_row(path: Path, *, file: bool) -> dict[str, Any] | None:
    try:
        info = path.lstat()
        link = stat.S_ISLNK(info.st_mode)
        size: int | None = info.st_size
        if link:
            try:
                info = path.stat()
                size = info.st_size
            except OSError:
                size = None
    except FileNotFoundError:
        return None  # Removed between the scan and reading this page.
    except OSError as failure:
        raise OsError(failure.strerror or str(failure)) from failure
    row: dict[str, Any] = {
        "name": path.name,
        "path": str(path),
        "modified_at": datetime.fromtimestamp(info.st_mtime, UTC).isoformat(),
        "is_symlink": link,
    }
    if file:
        row["size"] = size
    return row


@dataclass(frozen=True)
class DirectoryListing:
    flows: list[FlowRef]
    folders: list[Path]
    files: list[Path]


def list_directory(root: Path, *, show_hidden: bool = False) -> DirectoryListing:
    root = root.resolve()
    if root.name.endswith(FLOW_SUFFIX) and root.is_dir():
        return DirectoryListing(
            flows=[
                FlowRef(name=root.name[: -len(FLOW_SUFFIX)], path=root, relpath=".")
            ],
            folders=[],
            files=[],
        )
    try:
        with os.scandir(root) as scan:
            entries = sorted(scan, key=lambda e: (e.name.casefold(), e.name))
    except (FileNotFoundError, NotADirectoryError):
        raise FlowError(f"there is no directory `{root}`") from None
    except OSError as failure:
        raise OsError(f"cannot read `{root}`: {failure.strerror}") from failure
    flows: list[FlowRef] = []
    folders: list[Path] = []
    files: list[Path] = []
    for entry in entries:
        name = entry.name
        if name == STORE_DIRNAME or (
            not show_hidden and (name.startswith(".") or name in EXCLUDED_DIRS)
        ):
            continue
        path = Path(entry.path)
        try:
            if entry.is_dir():
                target = path.resolve() if entry.is_symlink() else path
                if target.name.endswith(FLOW_SUFFIX):
                    flows.append(FlowRef(name.removesuffix(FLOW_SUFFIX), path, name))
                else:
                    folders.append(path)
            elif entry.is_symlink() or entry.is_file():
                files.append(path)
        except OSError:
            if entry.is_symlink():
                files.append(path)  # An inaccessible or looping link.
    flows.sort(key=lambda ref: (ref.name.casefold(), ref.name))
    return DirectoryListing(flows=flows, folders=folders, files=files)


Lister = Callable[[Path], DirectoryListing]


def select_flow(
    root: Path,
    *,
    name: str | None = None,
    cwd: Path | None = None,
    lister: Lister | None = None,
) -> FlowRef:
    root = root.resolve()
    lister = lister or partial(list_directory, show_hidden=True)
    if name is not None:
        return _addressed(root, name, lister)
    standing = _standing_flow(cwd or root)
    if standing is not None:
        return standing
    flows = lister(root).flows
    if not flows:
        raise FlowNotFound(f"no flow in {root}. create one with `lumlflow init`")
    if len(flows) > 1:
        raise FlowAmbiguous(f"which flow? {_candidates(flows)}. name one with `--flow`")
    return flows[0]


class WorkspaceLock:
    def __init__(self) -> None:
        self.path = lock_path()
        self._handle: int | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.set_inheritable(handle, False)
        if not _lock(handle):
            os.close(handle)
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        _unlock(handle)
        os.close(handle)


def state_dir() -> Path:
    override = os.environ.get(STATE_DIR_ENV)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or "~/AppData/Local"
        return Path(base).expanduser() / "lumlflow"
    if platform.system() == "Darwin":
        return Path("~/Library/Application Support/lumlflow").expanduser()
    base = os.environ.get("XDG_STATE_HOME") or "~/.local/state"
    return Path(base).expanduser() / "lumlflow"


def record_path() -> Path:
    return state_dir() / RECORD_NAME


def lock_path() -> Path:
    return state_dir() / LOCK_NAME


def log_path() -> Path:
    return state_dir() / LOGS_DIRNAME / LOG_NAME


def read_record() -> DaemonRecord | None:
    path = record_path()
    try:
        body = json.loads(path.read_bytes())
        return DaemonRecord(**body)
    except (OSError, ValueError, TypeError):
        return None


def write_record(record: DaemonRecord) -> None:
    atomic_write_bytes(record_path(), record.to_json())
    record_path().chmod(0o600)


def clear_record(*, instance_id: str | None = None) -> None:
    record = read_record()
    if record is None or instance_id is None or record.instance_id == instance_id:
        record_path().unlink(missing_ok=True)


def new_record(
    *,
    instance_id: str,
    port: int,
    token: str,
    web_host: str,
    web_port: int,
    tracker_store: str,
) -> DaemonRecord:
    return DaemonRecord(
        pid=os.getpid(),
        instance_id=instance_id,
        port=port,
        token=token,
        web_host=web_host,
        web_port=web_port,
        tracker_store=tracker_store,
        version=__version__,
    )


def lock_held() -> bool:
    probe = WorkspaceLock()
    if not probe.acquire():
        return True
    probe.release()
    return False


def state_dir_is_local(directory: Path | None = None) -> bool:
    path = (directory or state_dir()).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32" and str(path.resolve()).startswith("\\\\"):
        return False
    filesystem = _filesystem_type(path.resolve())
    return filesystem is None or filesystem.casefold() not in _NETWORK_FILESYSTEMS


def network_filesystem_warning(directory: Path | None = None) -> str | None:
    path = (directory or state_dir()).expanduser().resolve()
    if state_dir_is_local(path):
        return None
    return (
        f"warning: {path} is on a network filesystem; file locks are unreliable there"
    )


def is_loopback_host(host: str) -> bool:
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _filesystem_type(path: Path) -> str | None:
    mountinfo = Path("/proc/self/mountinfo")
    try:
        lines = mountinfo.read_text("utf-8").splitlines()
    except OSError:
        return None
    matches: list[tuple[int, str]] = []
    for line in lines:
        before, separator, after = line.partition(" - ")
        if not separator:
            continue
        fields = before.split()
        trailing = after.split()
        if len(fields) < 5 or not trailing:
            continue
        mount = Path(_unescape_mount(fields[4]))
        if path == mount or path.is_relative_to(mount):
            matches.append((len(mount.parts), trailing[0]))
    return max(matches, default=(0, None))[1]


def _unescape_mount(value: str) -> str:
    return _MOUNT_ESCAPE.sub(lambda match: chr(int(match.group(1), 8)), value)


def _lock(handle: int) -> bool:
    try:
        if sys.platform == "win32":
            msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle: int) -> None:
    try:
        if sys.platform == "win32":
            os.lseek(handle, 0, os.SEEK_SET)
            msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_UN)
    except OSError:
        pass


def _addressed(root: Path, name: str, lister: Lister) -> FlowRef:
    if Path(name).is_absolute():
        return _at_path(root, entry_path(Path(name), strict=False))
    wanted = name.strip("/")
    if ".." in Path(wanted).parts:
        raise FlowError(f"`{name}` is not a path a flow can be named by")
    if len(Path(wanted).parts) > 1:
        if not wanted.endswith(FLOW_SUFFIX):
            wanted += FLOW_SUFFIX
        path = root / wanted
        return _at_path(root, entry_path(path, strict=False))
    bare = wanted.removesuffix(FLOW_SUFFIX)
    standing = _standing_flow(root)
    if standing is not None and bare == standing.name:
        return standing
    path = root / f"{bare}{FLOW_SUFFIX}"
    if bare and path.is_dir() and path.resolve().name.endswith(FLOW_SUFFIX):
        return FlowRef(name=bare, path=path, relpath=path.name)
    raise _missing(root, name, lister)


def _missing(root: Path, name: str, lister: Lister) -> FlowNotFound:
    listing = lister(root)
    has = (
        f"this directory has {', '.join(f'`{flow.name}`' for flow in listing.flows)}"
        if listing.flows
        else "this directory has no flows"
    )
    if listing.folders:
        bare = name.strip("/").removesuffix(FLOW_SUFFIX)
        hint = (
            f". name a nested flow by its path, like `{listing.folders[0].name}/{bare}`"
        )
    else:
        hint = ""
    return FlowNotFound(f"no flow called `{name}` in `{root}`. {has}{hint}")


def _at_path(root: Path, path: Path) -> FlowRef:
    if not path.is_dir() or not path.resolve().name.endswith(FLOW_SUFFIX):
        raise FlowNotFound(f"there is no flow at `{path}`")
    if path == root:
        relative = path.name
    elif path.is_relative_to(root):
        relpath = path.relative_to(root)
        if any(p.name.endswith(FLOW_SUFFIX) for p in relpath.parents):
            raise FlowNotFound(f"there is no flow at `{path}`")
        relative = relpath.as_posix()
    else:
        relative = path.as_posix()
    return FlowRef(path.name.removesuffix(FLOW_SUFFIX), path, relative)


def _standing_flow(directory: Path) -> FlowRef | None:
    here = directory.resolve()
    path = next(
        (
            candidate
            for candidate in (here, *here.parents)
            if candidate.name.endswith(FLOW_SUFFIX) and candidate.is_dir()
        ),
        None,
    )
    if path is None:
        return None
    return FlowRef(
        name=path.name[: -len(FLOW_SUFFIX)],
        path=path,
        relpath=path.name,
    )


def _candidates(flows: list[FlowRef]) -> str:
    return ", ".join(f"`{flow.name}` (`{flow.address}`)" for flow in flows)
