"""What a run's console is: both streams, one order, bytes as written.

Capture is at the file-descriptor level so a C extension, a progress bar on
stderr, and a subprocess all land in the same record — and so stdin is at EOF
for every one of them.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time

import pytest

from lumlflow_kernel.capture import Capture

DEADLINE_S = 20.0


def test_both_streams_are_captured_and_tagged_in_one_order():
    chunks: list[tuple[str, int, bytes]] = []
    with Capture(_collect(chunks)) as capture:
        print("out first")
        _await(chunks, 1)
        print("err second", file=sys.stderr)
        _await(chunks, 2)

    assert [(stream, seq) for stream, seq, _ in chunks] == [
        ("stdout", 1),
        ("stderr", 2),
    ]
    assert capture.artifact() == b"out first\nerr second\n"


def test_chunks_arrive_while_the_run_is_still_going():
    chunks: list[tuple[str, int, bytes]] = []
    with Capture(_collect(chunks)):
        print("epoch 1")
        _await(chunks, 1)
        seen_live = list(chunks)
        print("epoch 2")
        _await(chunks, 2)

    assert seen_live == [("stdout", 1, b"epoch 1\n")]


def test_ansi_survives_into_the_artifact():
    coloured = "\x1b[31mfailed\x1b[0m"
    with Capture(_ignore) as capture:
        print(coloured)

    assert capture.artifact() == coloured.encode() + b"\n"


def test_a_subprocess_writing_to_the_inherited_descriptor_is_captured():
    with Capture(_ignore) as capture:
        subprocess.run(
            [sys.executable, "-c", "import sys; sys.stdout.write('from a child\\n')"],
            check=True,
        )

    assert b"from a child\n" in capture.artifact()


def test_stdin_is_at_end_of_file_for_the_run_and_its_children():
    with Capture(_ignore):
        with pytest.raises(EOFError):
            input("continue?")
        child = subprocess.run(
            [sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"],
            capture_output=True,
            check=True,
        )

    assert child.stdout.strip() == b"0"


def test_a_flood_keeps_the_head_and_the_tail_and_states_the_gap():
    with Capture(_ignore, cap_bytes=1000) as capture:
        for line in range(500):
            print(f"line {line:04d}")

    artifact = capture.artifact()
    assert capture.truncated
    assert artifact.startswith(b"line 0000\n")
    assert artifact.endswith(b"line 0499\n")
    assert b"bytes of output omitted" in artifact
    assert len(artifact) < 1200


def test_output_below_the_cap_is_kept_whole():
    with Capture(_ignore, cap_bytes=1000) as capture:
        print("a modest amount")

    assert capture.truncated is False
    assert capture.artifact() == b"a modest amount\n"


def test_the_drain_threads_never_outlive_the_interpreter():
    """A cell can leave a child holding the write end, and then the drain never
    sees EOF: `__exit__` gives up on it after a timeout, so the reader must not
    be what keeps a shutting-down kernel alive."""
    with Capture(_ignore):
        readers = [
            thread
            for thread in threading.enumerate()
            if thread.name.startswith("capture-")
        ]

    assert sorted(reader.name for reader in readers) == [
        "capture-stderr",
        "capture-stdout",
    ]
    assert all(reader.daemon for reader in readers)


def test_the_process_streams_are_put_back_afterwards():
    before = (sys.stdin, sys.stdout, sys.stderr)
    fingerprints = [os.fstat(fd) for fd in (0, 1, 2)]
    with Capture(_ignore):
        print("noise")

    assert (sys.stdin, sys.stdout, sys.stderr) == before
    assert [os.fstat(fd) for fd in (0, 1, 2)] == fingerprints


def _collect(chunks: list[tuple[str, int, bytes]]):
    return lambda stream, seq, data: chunks.append((stream, seq, data))


def _ignore(stream: str, seq: int, data: bytes) -> None:
    return None


def _await(chunks: list, count: int) -> None:
    """The drain runs on its own thread; the test waits for it, never sleeps."""
    deadline = time.monotonic() + DEADLINE_S
    while time.monotonic() < deadline:
        if len(chunks) >= count:
            return
        time.sleep(0.005)
    raise AssertionError(f"only {len(chunks)} chunks arrived, wanted {count}")
