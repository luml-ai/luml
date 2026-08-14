"""What a kernel runs under, and what that is honestly worth.

The profile is applied where the OS makes it cheap — a seatbelt profile on
macOS, a network namespace on Linux — and nowhere else. What matters more than
the confinement is the reporting: a profile that could not be applied says so
in `lumlflow status`, naming the reason, because a sandbox nobody can see the
absence of is worse than none at all.

Two things are confined, and only two. Network access is denied, which costs
the flow nothing: native outputs are uploaded by the daemon from staged bytes,
so a kernel with no route out never strands one. Writes are confined to the
workspace and the temporary directories — reads stay open, because the
interpreter, its packages and the user's data files are scattered across the
disk and an allowlist over them would be a list of everything. In-process
Python cannot be fully sandboxed; this raises the floor, and paranoid mode
catches what gets past it.
"""

import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from lumlflow.flow.store.models import SandboxSetting

NONE = "none"
SEATBELT = "sandbox-exec"
NETWORK_NAMESPACE = "network-namespace"

# One `unshare` of a program that exits at once. Whether an unprivileged
# network namespace is available is a question about the kernel, the
# distribution's policy, and this util-linux — cheaper to ask than to predict.
_PROBE_TIMEOUT_S = 10.0
_USER_MAPPINGS = ("--map-current-user", "--map-root-user")


@dataclass(frozen=True)
class Profile:
    """A resolved sandbox: what it denies, why, and how to spawn under it."""

    name: str
    network_denied: bool
    writes_confined: bool
    reason: str
    command: tuple[str, ...] = ()

    def report(self) -> dict[str, Any]:
        return {
            "profile": self.name,
            "network_denied": self.network_denied,
            "writes_confined": self.writes_confined,
            "reason": self.reason,
        }


def resolve(
    setting: SandboxSetting,
    *,
    workspace_dir: Path,
    python: Path,
    socket_path: str | None,
) -> Profile:
    """The profile this kernel will start under.

    `socket_path` is the unix socket the kernel dials, or None where the link
    runs over loopback — which a no-network profile would cut, so there the
    honest answer is no sandbox rather than a kernel that cannot reach the
    daemon that spawned it.
    """
    if setting == "off":
        return _plain("this flow turns the sandbox off")
    system = platform.system()
    if system not in ("Darwin", "Linux"):
        return _plain(f"{system or 'this platform'} has no sandbox lumlflow applies")
    if socket_path is None:
        return _plain("the kernel link runs over loopback, which no-network would cut")
    if system == "Darwin":
        return _seatbelt(workspace_dir, socket_path)
    return _namespace(python)


def _plain(reason: str) -> Profile:
    """No profile — the kernel is an ordinary child process, and status says so."""
    return Profile(
        name=NONE, network_denied=False, writes_confined=False, reason=reason
    )


def _seatbelt(workspace_dir: Path, socket_path: str) -> Profile:
    if shutil.which(SEATBELT) is None:
        return _plain("this macOS has no `sandbox-exec`")
    return Profile(
        name=SEATBELT,
        network_denied=True,
        writes_confined=True,
        reason="no network, and writes only under the workspace and temp",
        command=(SEATBELT, "-p", seatbelt_profile(workspace_dir, socket_path)),
    )


def _namespace(python: Path) -> Profile:
    if shutil.which("unshare") is None:
        return _plain("this Linux has no `unshare`")
    command = _namespace_command(str(python))
    if command is None:
        return _plain("unprivileged network namespaces are not available here")
    return Profile(
        name=NETWORK_NAMESPACE,
        network_denied=True,
        writes_confined=False,
        reason="no network. writes are not confined on Linux",
        command=command,
    )


@cache
def _namespace_command(python: str) -> tuple[str, ...] | None:
    """The `unshare` spelling this box accepts, or None if none of them do.

    Cached: the answer is a property of the machine, and `status` asks it as
    often as anyone types the verb. `--map-current-user` needs util-linux 2.38;
    mapping to root inside the namespace is the older spelling of the same
    thing, and both leave files owned by the user outside it.
    """
    for mapping in _USER_MAPPINGS:
        command = ("unshare", "--net", mapping)
        if _probe((*command, python, "-c", "")):
            return command
    return None


def _probe(command: tuple[str, ...]) -> bool:
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=_PROBE_TIMEOUT_S
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def seatbelt_profile(workspace_dir: Path, socket_path: str) -> str:
    """A seatbelt profile: allow by default, then take two things away.

    Denying by default would mean enumerating every mach service, sysctl and
    ioctl arbitrary numerical code reaches for — a list that is wrong the first
    time somebody imports a library we have not seen. Denying the two things
    this sandbox is actually about is a claim we can keep.
    """
    writable = " ".join(
        f"(subpath {_quoted(path)})" for path in _writable(workspace_dir)
    )
    return "\n".join(
        [
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            f"(allow network-outbound (literal {_quoted(socket_path)}))",
            "(deny file-write*)",
            f"(allow file-write* {writable})",
            "(allow file-write-data "
            '(literal "/dev/null") (literal "/dev/zero") (literal "/dev/random") '
            '(literal "/dev/urandom") (literal "/dev/dtracehelper"))',
        ]
    )


def _writable(workspace_dir: Path) -> list[str]:
    """The workspace — flow stores and scratch live under it — plus temp.

    A cell writing to the workspace is a supported thing to do: `ctx.branch`
    prefixing an export path is in the spec. What the sandbox stops is a write
    somewhere else on the disk.
    """
    paths = [workspace_dir, Path(tempfile.gettempdir()), Path("/tmp")]
    spellings: list[str] = []
    for path in paths:
        # Both spellings, in a fixed order: the profile text is an argument to
        # a subprocess, and one that varies between spawns is one nobody can
        # compare against what they read in `status`.
        for spelling in (str(path), str(_resolved(path))):
            if spelling not in spellings:
                spellings.append(spelling)
    return spellings


def _resolved(path: Path) -> Path:
    """macOS temp lives under a symlink; the sandbox matches the real path."""
    try:
        return path.resolve()
    except OSError:
        return path


def _quoted(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
