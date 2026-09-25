"""The scratch REPL: copies out, nothing in.

What is pinned here is the promise the surface rests on — code typed at a
branch's values cannot change them. The mutation lands on a copy, the store's
bytes are what the next reader gets, and no version, value or log comes of an
expression. The rest is REPL manners: only what is mentioned is read, a
trailing expression answers, prints come back as text, and an unknown name is a
`NameError` rather than a runtime the author has to decode.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from lumlflow_kernel.kernel import Kernel
from tests.kernel.helpers import make_kernel, run, store_blobs

MISSING_REF = "0" * 64


def test_a_mutation_in_the_repl_lands_on_a_copy(tmp_path: Path):
    """The scenario: mutate a name, and the branch's value is unchanged.

    Within one evaluation the mutation is visible — that is what makes it a
    REPL — and the next one starts from the store again.
    """
    kernel, names = _kernel_with(tmp_path, rows=[1, 2, 3])
    before = store_blobs(kernel)

    mutated = _eval(kernel, names, "rows.append(4); len(rows)")
    again = _eval(kernel, names, "len(rows)")

    assert mutated["repr"] == "4"
    assert again["repr"] == "3"
    assert "mutated" not in mutated
    assert store_blobs(kernel) == before


def test_the_repl_writes_no_asset_no_preview_and_no_log(tmp_path: Path):
    kernel, names = _kernel_with(tmp_path, rows=[1, 2, 3])
    before = store_blobs(kernel)

    answered = _eval(kernel, names, "print('working'); sum(rows)")

    assert answered["repr"] == "6"
    assert "working" in answered["output"]
    assert store_blobs(kernel) == before


def test_output_and_result_are_clipped_to_64_kib_with_the_omitted_size(
    tmp_path: Path,
) -> None:
    kernel, names = _kernel_with(tmp_path, rows=[1, 2, 3])
    characters = 70 * 1024

    printed = _eval(kernel, names, f"print('å' * {characters}, end='')")["output"]
    represented = _eval(kernel, names, f"'å' * {characters}")["repr"]

    for clipped, original_bytes in (
        (printed, characters * 2),
        (represented, characters * 2 + 2),
    ):
        assert isinstance(clipped, str)
        prefix, marker = clipped.rsplit("\n… ", 1)
        omitted = int(marker.removesuffix(" bytes omitted"))
        assert len(clipped.encode("utf-8")) <= 64 * 1024
        assert len(prefix.encode("utf-8")) + omitted == original_bytes


def test_only_the_names_the_code_mentions_are_read(tmp_path: Path):
    """Hydration is lazy, and the proof is a name that could not be read.

    `never` points at bytes the store does not hold: an evaluation that
    prepared the whole slice up front would fail on it.
    """
    kernel, names = _kernel_with(tmp_path, rows=[1, 2, 3])
    names["never"] = {"value_ref": MISSING_REF, "kind": "pickle"}

    answered = _eval(kernel, names, "len(rows)")

    assert answered["error"] is None
    assert answered["names"] == ["rows"]


def test_a_name_the_branch_does_not_carry_reads_as_a_name(tmp_path: Path):
    kernel, names = _kernel_with(tmp_path, rows=[1, 2, 3])

    answered = _eval(kernel, names, "missing_cell")

    assert answered["error"]["type"] == "NameError"
    assert "missing_cell" in answered["error"]["message"]


def test_names_resolve_inside_functions_too(tmp_path: Path):
    """A lambda reaches the slice through the global path, not the local one."""
    kernel, names = _kernel_with(tmp_path, rows=[1, 2, 3])

    answered = _eval(kernel, names, "(lambda: sum(rows))()")

    assert answered["repr"] == "6"


def test_a_statement_answers_nothing_and_an_assignment_holds(tmp_path: Path):
    kernel, names = _kernel_with(tmp_path, rows=[1, 2, 3])

    silent = _eval(kernel, names, "doubled = [n * 2 for n in rows]")
    answered = _eval(kernel, names, "total = sum(rows)\ntotal * 10")

    assert silent["repr"] is None
    assert silent["error"] is None
    assert answered["repr"] == "60"


def test_a_failure_comes_back_as_a_traceback_starting_at_the_typed_line(
    tmp_path: Path,
):
    kernel, names = _kernel_with(tmp_path, rows=[1, 2, 3])

    answered = _eval(kernel, names, "rows[0] / 0")

    assert answered["error"]["type"] == "ZeroDivisionError"
    assert "<eval>" in answered["error"]["traceback"]
    assert "repl.py" not in answered["error"]["traceback"]


def test_unreadable_code_answers_with_the_syntax_error(tmp_path: Path):
    kernel, names = _kernel_with(tmp_path, rows=[1, 2, 3])

    answered = _eval(kernel, names, "len(rows")

    assert answered["error"]["type"] == "SyntaxError"


def test_the_repl_is_the_one_surface_stdin_still_reaches(tmp_path: Path):
    """A cell reads `/dev/null` and fails on `input()`; an evaluation does not.

    The REPL is the surface a person types at, so the capture that makes a run
    non-interactive leaves descriptor 0 where it found it — and a regression
    that took stdin away would pass every other test here.
    """
    kernel, names = _kernel_with(tmp_path, rows=[1, 2, 3])

    with _stdin_holding(b"typed"):
        answered = _eval(kernel, names, "import os; os.read(0, 5)")

    assert answered["repr"] == repr(b"typed")


def _kernel_with(
    tmp_path: Path, **values: Any
) -> tuple[Kernel, dict[str, dict[str, str]]]:
    """A kernel holding one materialized cell per named value."""
    kernel, _ = make_kernel(tmp_path)
    names = {}
    for name, value in values.items():
        record = run(
            kernel,
            f"def materialize(self, ctx):\n    return {{'{name}': {value!r}}}",
            run_id=f"run-{name}",
            produces={name: "asset"},
        )
        output = record["outputs"][name]
        names[name] = {
            "value_ref": output["value_ref"],
            "kind": output["kind"],
        }
    return kernel, names


@contextlib.contextmanager
def _stdin_holding(data: bytes) -> Iterator[None]:
    """Descriptor 0 on a pipe holding `data`, put back afterwards."""
    read_fd, write_fd = os.pipe()
    os.write(write_fd, data)
    os.close(write_fd)
    saved = os.dup(0)
    try:
        os.dup2(read_fd, 0)
        yield
    finally:
        os.dup2(saved, 0)
        os.close(saved)
        os.close(read_fd)


def _eval(
    kernel: Kernel,
    names: dict[str, dict[str, str]],
    code: str,
) -> dict[str, Any]:
    return kernel.eval({"slice": names, "code": code})
