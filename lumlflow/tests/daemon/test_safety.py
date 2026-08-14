"""Safety modes and sandbox profiles: what is enforced, and what is claimed.

The two halves are held to different standards. Paranoid mode has to actually
catch the mutation it exists for, end to end through a real kernel. The sandbox
has to be honest — every platform gets the profile it can afford and `status`
says which one that came to, because a confinement nobody can see the absence
of is worth less than none at all.
"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from lumlflow.flow import render
from lumlflow.flow.daemon import sandbox, secrets
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.store.cas import Cas
from lumlflow.flow.store.flowstore import store_dir

from tests.daemon.helpers import (
    daemon_api,
    flow_kernel,
    flow_named,
    make_workspace,
    run_request,
    transactions,
    write_cell,
)

SOCKET = "/w/churn.flow/.lumlflow/kernel/kernel.sock"
WRAPPED = "LUMLFLOW_WRAPPED"

ROWS_CELL = """
class Rows:
    \"\"\"A value a consumer could change under the store.\"\"\"
    produces = {"rows": "asset"}

    def materialize(self, ctx):
        return {"rows": [1, 2, 3]}
"""

MUTATES_CELL = """
class Summarize:
    \"\"\"Changes what it was given, which is the thing cells may not do.\"\"\"
    consumes = {"rows": "rows.rows"}
    produces = {"total": "asset"}

    def materialize(self, ctx, rows):
        rows.append(4)
        return {"total": sum(rows)}
"""

WRAPPED_CELL = """
class Wrapped:
    \"\"\"Reports whether the kernel around it was started under the profile.\"\"\"

    def materialize(self, ctx):
        import os

        under = os.environ.get("LUMLFLOW_WRAPPED") == "yes"
        return {"summary": {"wrapped": int(under)}}
"""

USES_SECRET_CELL = """
class Caller:
    \"\"\"Reads a secret and keeps nothing but its shape.\"\"\"
    produces = {"length": "asset"}

    def materialize(self, ctx):
        key = ctx.secret("API_KEY")
        print("calling with a key of", len(key), "characters")
        return {"length": {"characters": len(key)}}
"""


@pytest.fixture(autouse=True)
def unprobed():
    """Whether this machine grants a network namespace is cached, because
    `status` asks as often as anyone types it. No test inherits that answer."""
    sandbox._namespace_command.cache_clear()
    yield
    sandbox._namespace_command.cache_clear()


class TestProfileResolution:
    """Which profile each platform affords, and what it says it does."""

    def test_macos_denies_the_network_and_confines_writes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _platform(monkeypatch, "Darwin", tools={"sandbox-exec"})

        profile = _resolve(tmp_path)

        assert profile.name == sandbox.SEATBELT
        assert (profile.network_denied, profile.writes_confined) == (True, True)
        assert profile.command[:2] == (sandbox.SEATBELT, "-p")
        text = profile.command[2]
        assert "(deny network*)" in text and "(deny file-write*)" in text
        # The one hole in the network denial is the link the daemon is on the
        # other end of: a kernel that cannot reach it is not sandboxed, it is
        # broken.
        assert f'(allow network-outbound (literal "{SOCKET}"))' in text
        assert f'(subpath "{tmp_path}")' in text

    def test_a_macos_without_the_tool_says_so_rather_than_claiming_a_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _platform(monkeypatch, "Darwin", tools=set())

        profile = _resolve(tmp_path)

        assert (profile.name, profile.command) == (sandbox.NONE, ())
        assert "sandbox-exec" in profile.reason

    def test_linux_takes_the_network_namespace_it_can_get(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _platform(monkeypatch, "Linux", tools={"unshare"})
        _probes(monkeypatch, {("unshare", "--net", "--map-current-user")})

        profile = _resolve(tmp_path)

        assert profile.name == sandbox.NETWORK_NAMESPACE
        assert profile.command == ("unshare", "--net", "--map-current-user")
        # Honest about the half it does not do: a namespace is not an allowlist.
        assert (profile.network_denied, profile.writes_confined) == (True, False)

    def test_an_older_unshare_falls_back_to_the_spelling_it_has(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _platform(monkeypatch, "Linux", tools={"unshare"})
        _probes(monkeypatch, {("unshare", "--net", "--map-root-user")})

        assert _resolve(tmp_path).command == ("unshare", "--net", "--map-root-user")

    def test_a_linux_that_refuses_namespaces_reports_no_sandbox(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _platform(monkeypatch, "Linux", tools={"unshare"})
        _probes(monkeypatch, set())

        profile = _resolve(tmp_path)

        assert (profile.name, profile.command) == (sandbox.NONE, ())
        assert "network namespaces" in profile.reason

    def test_windows_gets_plain_process_isolation_and_names_the_platform(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _platform(monkeypatch, "Windows", tools={"unshare", "sandbox-exec"})

        profile = _resolve(tmp_path)

        assert (profile.name, profile.command) == (sandbox.NONE, ())
        assert "Windows" in profile.reason

    def test_a_flow_that_turns_the_sandbox_off_gets_no_profile_anywhere(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _platform(monkeypatch, "Darwin", tools={"sandbox-exec"})

        profile = _resolve(tmp_path, setting="off")

        assert (profile.name, profile.command) == (sandbox.NONE, ())
        assert "off" in profile.reason

    def test_a_loopback_link_is_never_sandboxed_out_of_reaching_its_daemon(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Where the kernel dials over loopback — Windows, or a socket path too
        long to bind — a no-network profile would cut the link it was spawned
        to speak on. The honest answer is no sandbox, with the reason."""
        _platform(monkeypatch, "Linux", tools={"unshare"})
        _probes(monkeypatch, {("unshare", "--net", "--map-current-user")})

        profile = _resolve(tmp_path, socket_path=None)

        assert (profile.name, profile.command) == (sandbox.NONE, ())
        assert "loopback" in profile.reason


class TestProfileReporting:
    async def test_status_carries_the_profile_and_prints_its_reason(
        self, tmp_path: Path
    ):
        root = make_workspace(tmp_path / "project")

        async with daemon_api(root) as api:
            status = await api.status({})

        profile = flow_named(status, "churn")["kernel"]["sandbox"]
        assert set(profile) == {
            "profile",
            "network_denied",
            "writes_confined",
            "reason",
        }
        assert profile["reason"]
        assert profile["reason"] in "\n".join(render.status(status))

    def test_an_unconfined_kernel_is_printed_as_plainly_as_a_confined_one(self):
        plain = _rendered(
            {"network_denied": False, "writes_confined": False, "reason": "no unshare"}
        )
        confined = _rendered(
            {"network_denied": True, "writes_confined": False, "reason": "no network"}
        )

        assert "not sandboxed · no unshare" in plain
        assert "sandboxed · no network" in confined


class TestProfileApplication:
    """A profile is a command the kernel is spawned under, not a claim about
    one — so what `resolve` answers has to reach the process."""

    @pytest.mark.skipif(
        sys.platform == "win32", reason="`env` is the wrapper this borrows"
    )
    async def test_the_profile_it_resolved_wraps_the_process_it_spawns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """`env` stands in for the real profiles: neither the seatbelt nor a
        network namespace is available on every box this runs on, and what is
        under test is the spawn rather than the confinement."""
        monkeypatch.setattr(sandbox, "resolve", _wrapping_profile)
        root = make_workspace(tmp_path / "project")

        async with flow_kernel(root) as kernel:
            result = await kernel.run(run_request("wrapped", WRAPPED_CELL))

        values = Cas(store_dir(root / "churn.flow") / "values")
        stored = json.loads(values.get(str(result.outputs["summary"].value_ref)))
        assert stored == {"wrapped": 1}

    async def test_a_flow_that_turns_the_sandbox_off_reaches_its_kernel_that_way(
        self, tmp_path: Path
    ):
        """The setting is read off the flow's own `flow.yaml` by the kernel the
        daemon built for it — what `status` reports is what that kernel
        resolved, never a default assumed above it."""
        root = make_workspace(tmp_path / "project")
        async with daemon_api(root) as api:
            await api.flow_open({"flow": "churn"})
        _setting(root / "churn.flow", "sandbox", "off")

        async with daemon_api(root) as api:
            status = await api.status({})

        profile = flow_named(status, "churn")["kernel"]["sandbox"]
        assert profile["profile"] == sandbox.NONE
        assert "off" in profile["reason"]


class TestParanoidMode:
    async def test_a_cell_that_changed_its_input_fails_and_the_value_survives(
        self, tmp_path: Path
    ):
        """The scenario, through a real kernel and the setting a user types:
        the post-run re-hash mismatches, the run fails naming the cell and the
        input, and the stored value is the one the producer wrote."""
        root = make_workspace(tmp_path / "project")
        write_cell(root / "churn.flow", "rows", ROWS_CELL)
        write_cell(root / "churn.flow", "summarize", MUTATES_CELL)
        async with daemon_api(root) as api:
            await api.flow_open({"flow": "churn"})
        _setting(root / "churn.flow", "paranoid", True)

        async with daemon_api(root) as api:
            outcome = await api.run({"flow": "churn", "target": "summarize"})
            shown = await api.cells_show({"flow": "churn", "slug": "summarize"})
            after = await api.eval({"flow": "churn", "code": "rows"})

        assert outcome["failed"] == "summarize"
        assert "`summarize`" in shown["error"] and "`rows`" in shown["error"]
        assert after["repr"] == "[1, 2, 3]"

    async def test_the_same_run_stands_when_the_mode_is_off(self, tmp_path: Path):
        """Off is the default, and the default costs nothing: no input is
        re-hashed and the run is recorded like any other."""
        root = make_workspace(tmp_path / "project")
        write_cell(root / "churn.flow", "rows", ROWS_CELL)
        write_cell(root / "churn.flow", "summarize", MUTATES_CELL)

        async with daemon_api(root) as api:
            outcome = await api.run({"flow": "churn", "target": "summarize"})

        assert outcome["executed"] == ["rows", "summarize"]
        assert outcome["failed"] is None


class TestSecrets:
    async def test_a_secret_reaches_the_cell_and_no_surface_that_keeps_anything(
        self, tmp_path: Path
    ):
        """The scenario: the value is in no CAS entry, preview, journal line,
        log artifact, or `--json` response — while the cell that asked for it
        got the real thing."""
        secret = "sk-live-DEADBEEF"
        root = make_workspace(tmp_path / "project")
        write_cell(root / "churn.flow", "caller", USES_SECRET_CELL)

        async with daemon_api(root) as api:
            session = api.hub.session("churn")
            secrets.set_secret(session, "API_KEY", secret, actor="user")
            outcome = await api.run({"flow": "churn", "target": "caller"})
            served = await _every_read(api)
            lines = [entry.model_dump_json() for entry in transactions(session)]
            stored = _store_bytes(root / "churn.flow")

        assert outcome["executed"] == ["caller"]
        # The cell was handed the real value: the length is the proof, and the
        # only thing about the secret anything downstream knows.
        assert json.loads(served["asset"])["preview"]["blocks"] == [
            {"block": "kv", "entries": {"characters": len(secret)}}
        ]
        assert secret not in json.dumps(served)
        assert not [line for line in lines if secret in line]
        assert not [blob for blob in stored if secret.encode() in blob]
        assert "API_KEY" in served["secrets"]


def _setting(flow_dir: Path, name: str, value: Any) -> None:
    """Change a safety setting where a user does: the flow's own `flow.yaml`."""
    path = flow_dir / "flow.yaml"
    manifest = yaml.safe_load(path.read_text("utf-8"))
    manifest["settings"][name] = value
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")


def _wrapping_profile(*_: Any, **__: Any) -> sandbox.Profile:
    """A profile whose command the spawned process can prove it ran under."""
    return sandbox.Profile(
        name="probe",
        network_denied=False,
        writes_confined=False,
        reason="a stand-in for the profiles this box may not have",
        command=("env", f"{WRAPPED}=yes"),
    )


def _resolve(
    workspace_dir: Path,
    *,
    setting: Any = "auto",
    socket_path: str | None = SOCKET,
) -> sandbox.Profile:
    return sandbox.resolve(
        setting,
        workspace_dir=workspace_dir,
        python=Path("/usr/bin/python3"),
        socket_path=socket_path,
    )


def _platform(monkeypatch: pytest.MonkeyPatch, system: str, *, tools: set[str]) -> None:
    """A platform, and which of the sandbox tools it has on PATH."""
    monkeypatch.setattr(sandbox.platform, "system", lambda: system)
    monkeypatch.setattr(
        sandbox.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in tools else None,
    )


def _probes(monkeypatch: pytest.MonkeyPatch, accepted: set[tuple[str, ...]]) -> None:
    """Which `unshare` spellings this box would accept."""
    monkeypatch.setattr(sandbox, "_probe", lambda command: command[:3] in accepted)


def _rendered(profile: dict[str, Any]) -> str:
    return "\n".join(
        render.status(
            {
                "workspace": "/w",
                "flows": [
                    {
                        "flow": "churn",
                        "branch": "main",
                        "kernel": {"state": "running", "sandbox": profile},
                    }
                ],
            }
        )
    )


async def _every_read(api: Api) -> dict[str, str]:
    """Every `--json` surface that could carry a run's leavings."""
    reads = {
        "status": await api.status({}),
        "context": await api.context({"flow": "churn"}),
        "cells": await api.cells_list({"flow": "churn"}),
        "show": await api.cells_show({"flow": "churn", "slug": "caller"}),
        "asset": await api.asset_preview({"flow": "churn", "target": "caller.length"}),
        "secrets": await api.secrets_list({"flow": "churn"}),
        "journal": await api.journal_since({"flow": "churn", "cursor": 0}),
    }
    return {name: json.dumps(payload) for name, payload in reads.items()}


def _store_bytes(flow_dir: Path) -> list[bytes]:
    """Everything the flow wrote down — values, previews, logs, journal, index."""
    store = flow_dir / ".lumlflow"
    return [
        path.read_bytes()
        for path in sorted(store.rglob("*"))
        if path.is_file() and path.parent.name != "tmp"
    ]
