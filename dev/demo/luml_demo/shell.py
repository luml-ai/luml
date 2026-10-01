"""Subprocess, Docker Compose and polling helpers."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path


def say(message: str) -> None:
    print(f"[luml-demo] {message}", flush=True)


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    say("$ " + " ".join(command))
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        check=check,
        text=True,
        capture_output=capture,
        stdout=None if capture else sys.stdout,
        stderr=None if capture else sys.stderr,
    )


def compose(project: str, files: Sequence[Path], *args: str, cwd: Path | None = None,
            check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    command = ["docker", "compose", "-p", project]
    for file in files:
        command += ["-f", str(file)]
    return run([*command, *args], cwd=cwd, check=check, capture=capture)


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.3)
        return probe.connect_ex((host, port)) != 0


def wait_for(
    description: str,
    probe: Callable[[], bool],
    *,
    timeout: float,
    interval: float = 2.0,
) -> None:
    deadline = time.monotonic() + timeout
    say(f"waiting for {description} (up to {int(timeout)}s)")
    while True:
        try:
            if probe():
                return
        except Exception as error:  # noqa: BLE001 — probes fail until the target is up
            last = f"{type(error).__name__}: {error}"
        else:
            last = "not ready"
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out waiting for {description}: {last}")
        time.sleep(interval)
