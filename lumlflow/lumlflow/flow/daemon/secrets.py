"""Where a flow's secrets live — which is nowhere the flow itself can reach.

`ctx.secret("API_KEY")` is a request from the kernel to the daemon, answered from
the OS keychain, or from a private file in the user's state directory where there
is no keychain to ask. The value never enters the store: not the CAS, not a
preview, not a log artifact, and not the journal, which records only that a name
exists so `secrets list` has something true to list.

Scoped to the flow, because the journal that carries the names is the flow's:
a value stored wider than the register of names that go with it would be a
secret one flow could read and no surface could tell you about.

The API never hands a value back either. A caller can set one and see the names;
reading a secret is something only a running cell can do.
"""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import keyring
import keyring.errors

from lumlflow.flow.atomic import atomic_write_bytes
from lumlflow.flow.daemon import workspace
from lumlflow.flow.errors import FlowError
from lumlflow.flow.hashing import hash_bytes
from lumlflow.flow.store.models import SecretRefAdded

if TYPE_CHECKING:
    from lumlflow.flow.daemon.hub import FlowSession

SERVICE = "lumlflow-flow"
FALLBACK_NAME = "secrets.json"

_KEYRING_ERRORS = (keyring.errors.KeyringError, keyring.errors.NoKeyringError)


def set_secret(session: "FlowSession", name: str, value: str, *, actor: str) -> str:
    """Store a value under a name, and journal that the name exists."""
    name = _valid(name)
    _write(session.ref.path, name, value)
    if name not in names(session):
        session.store.commit(
            [SecretRefAdded(name=name)],
            intent=f"added the secret `{name}`",
            actor=actor,
        )
    return name


def names(session: "FlowSession") -> list[str]:
    """The names this flow has been told about — never the values."""
    return sorted(
        {
            op.name
            for entry in session.store.journal.replay()
            for op in entry.ops
            if isinstance(op, SecretRefAdded)
        }
    )


def get(flow_dir: Path, name: str) -> str | None:
    """Answer the kernel's `secret_get`. Values are never logged on the way."""
    try:
        stored = keyring.get_password(SERVICE, _key(flow_dir, name))
    except _KEYRING_ERRORS:
        stored = None
    return stored if stored is not None else _from_file(flow_dir).get(name)


def _write(flow_dir: Path, name: str, value: str) -> None:
    try:
        keyring.set_password(SERVICE, _key(flow_dir, name), value)
        return
    except _KEYRING_ERRORS:
        # A headless box has no keychain to put this in. The state directory is
        # outside the user's repo and readable only by them, which is the next
        # honest place — never the flow store, which is committed and shared.
        pass
    path = _fallback_path(flow_dir)
    secrets = _from_file(flow_dir) | {name: value}
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(path, json.dumps(secrets).encode("utf-8"))
    # Asserted rather than assumed: the atomic write lands a private temp file
    # today, and a secrets file is not the place to find out that changed.
    os.chmod(path, 0o600)


def _from_file(flow_dir: Path) -> dict[str, str]:
    path = _fallback_path(flow_dir)
    try:
        stored = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


def _fallback_path(flow_dir: Path) -> Path:
    stem = workspace.record_path(flow_dir).stem
    return workspace.state_dir() / "secrets" / f"{stem}-{FALLBACK_NAME}"


def _key(flow_dir: Path, name: str) -> str:
    """One flow's secrets are not another's, even under the same name."""
    return f"{hash_bytes(str(flow_dir.resolve()).encode('utf-8'))[:16]}:{name}"


def _valid(name: str) -> str:
    name = name.strip()
    if not name or any(character.isspace() for character in name):
        raise FlowError("a secret's name is one word, and not an empty one")
    return name
