"""The file `cells new` writes: wired to what it comes after, and checkable.

The conformance footer is only worth emitting if it passes, so the type check is
the test — a scaffold that reddens an author's editor the moment it is created
would teach everyone to delete the footer.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from lumlflow.flow.dsl import loader, scaffold

PROJECT = Path(__file__).resolve().parents[2]


def test_a_source_cell_scaffolds_with_no_inputs():
    source = scaffold.cell_source("score", docstring="The headline metric.")
    cell = loader.parse(source).cell

    assert cell is not None
    assert cell.name == "Score"
    assert cell.docstring == "The headline metric."
    assert cell.consumes == {}
    assert list(cell.produces) == ["result"]
    assert "def materialize(self, ctx):" in source


def test_after_prefills_the_wiring_and_the_matching_signature():
    source = scaffold.cell_source(
        "report", producer="score", outputs=["summary", "rows"]
    )
    cell = loader.parse(source).cell

    assert cell is not None
    assert cell.consumes == {"summary": "score.summary", "rows": "score.rows"}
    assert "def materialize(self, ctx, summary, rows):" in source


def test_a_placeholder_name_does_not_become_the_class_name():
    # Otherwise the daemon would suggest renaming the new cell to `untitled_3`,
    # which is the name it was just given for want of a better one.
    assert scaffold.class_name("untitled_3") == "Untitled"
    assert scaffold.class_name("train_model") == "TrainModel"


@pytest.mark.parametrize("producer", [None, "score"])
def test_what_is_scaffolded_passes_the_type_check_its_footer_asks_for(
    tmp_path: Path, producer: str | None
):
    pytest.importorskip("mypy")
    written = tmp_path / "report.py"
    written.write_text(
        scaffold.cell_source(
            "report", producer=producer, outputs=["summary"] if producer else ()
        ),
        encoding="utf-8",
    )

    checked = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-incremental", str(written)],
        cwd=PROJECT,
        capture_output=True,
        text=True,
    )

    assert checked.returncode == 0, checked.stdout + checked.stderr
