"""Flow discovery and the one per-user daemon record."""

import ipaddress
import json
import os
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

from lumlflow import __version__
from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.dsl.tree import EXCLUDED_DIRS
from lumlflow.flow.errors import FlowAmbiguous, FlowNotFound
from lumlflow.flow.store.flowstore import FLOW_SUFFIX, store_dir

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
    """A discovered flow and its path relative to the directory searched."""

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


def find_flows(root: Path) -> list[FlowRef]:
    """Every flow under the workspace, nested ones included, in path order."""
    root = root.resolve()
    found: list[FlowRef] = []
    for dirpath, dirnames, _ in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_DIRS)
        flows = [name for name in dirnames if name.endswith(FLOW_SUFFIX)]
        # A flow is monolithic: the walk stops at its door rather than
        # descending into cells and the store.
        dirnames[:] = [name for name in dirnames if name not in flows]
        for name in flows:
            path = here / name
            found.append(
                FlowRef(
                    name=name[: -len(FLOW_SUFFIX)],
                    path=path,
                    relpath=path.relative_to(root).as_posix(),
                )
            )
    return found


def select_flow(
    root: Path, *, name: str | None = None, cwd: Path | None = None
) -> FlowRef:
    """Which flow a flow-scoped verb means.

    Named wins — by name, by path under the workspace, or by its own absolute
    path for a flow the workspace does not contain; else the flow the caller is
    standing in; else the workspace's only flow. Anything else is a question,
    and the answer names the candidates rather than guessing at one.
    """
    if name is not None:
        return _addressed(root, name)
    standing = _standing_flow(cwd or root)
    if standing is not None:
        return standing
    flows = find_flows(root)
    inside = _containing_flow(flows, cwd) if cwd is not None else None
    if inside is not None:
        return inside
    if not flows:
        raise FlowNotFound(f"no flow in {root}. create one with `lumlflow init`")
    if len(flows) > 1:
        raise FlowAmbiguous(f"which flow? {_candidates(flows)}. name one with `--flow`")
    return flows[0]


def flow_here(root: Path, cwd: Path) -> FlowRef | None:
    """The flow a caller is standing in — how a verb addresses one unasked."""
    return _standing_flow(cwd) or _containing_flow(find_flows(root), cwd)


class WorkspaceLock:
    """The OS-released lock held by the daemon for its entire lifetime."""

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
    """Where the daemon's records live, per platform, overridable for tests."""
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
    """The daemon registered for this user, if the record is readable."""
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
    """Deregister only the daemon instance that asked, or a known stale row."""
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
    """Whether the OS says a daemon owns the singleton lock."""
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
    """The Linux mount type for a path; unknown platforms are treated as local."""
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


def _named(flows: list[FlowRef], name: str) -> FlowRef:
    wanted = name.removesuffix(FLOW_SUFFIX).strip("/")
    matches = [
        flow
        for flow in flows
        if wanted in (flow.name, flow.relpath, flow.relpath.removesuffix(FLOW_SUFFIX))
    ]
    if not matches:
        raise FlowNotFound(
            f"no flow called `{name}`"
            + (f". this workspace has {_candidates(flows)}" if flows else "")
        )
    if len(matches) > 1:
        raise FlowAmbiguous(
            f"`{name}` names more than one flow: {_paths(matches)}. "
            "use the path to say which"
        )
    return matches[0]


def _containing_flow(flows: list[FlowRef], cwd: Path) -> FlowRef | None:
    here = cwd.resolve()
    return next(
        (flow for flow in flows if here == flow.path or here.is_relative_to(flow.path)),
        None,
    )


def _addressed(root: Path, name: str) -> FlowRef:
    """A flow by name, by path under the workspace, or by its own absolute path.

    The absolute spelling is how the browser opens a flow from above the launch
    directory: it addresses the flow itself, so nothing has to invent a
    root-relative name for a directory the workspace does not contain.
    """
    asked = Path(name)
    if not asked.is_absolute():
        standing = _standing_flow(root)
        if standing is not None and name.removesuffix(FLOW_SUFFIX) == standing.name:
            return standing
        return _named(find_flows(root), name)
    path = asked.resolve()
    if path == root and path.name.endswith(FLOW_SUFFIX):
        if not path.is_dir():
            raise FlowNotFound(f"there is no flow at `{path}`")
        return FlowRef(
            name=path.name[: -len(FLOW_SUFFIX)],
            path=path,
            relpath=path.name,
        )
    if path.is_relative_to(root):
        return _named(find_flows(root), path.relative_to(root).as_posix())
    return _outside_flow(path)


def _outside_flow(path: Path) -> FlowRef:
    """A flow that lives outside the workspace, addressed by where it is."""
    if not (path.is_dir() and path.name.endswith(FLOW_SUFFIX)):
        raise FlowNotFound(f"there is no flow at `{path}`")
    return FlowRef(
        name=path.name[: -len(FLOW_SUFFIX)], path=path, relpath=path.as_posix()
    )


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


def _paths(flows: list[FlowRef]) -> str:
    return ", ".join(f"`{flow.address}`" for flow in flows)
