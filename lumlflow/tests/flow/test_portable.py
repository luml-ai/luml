"""The single-file format, read and written.

What the round trip has to promise is byte fidelity of the part a hash is taken
over: whatever whitespace lands between two blocks belongs to the format, and a
cell that goes out has to come back the same cell.
"""

import pytest
from lumlflow.flow.dsl import portable
from lumlflow.flow.dsl.portable import PortableCell
from lumlflow.flow.errors import FlowError

SCORE = 'class Score:\n    """The headline metric."""\n    uid = "01J"\n'
REPORT = 'class Report:\n    consumes = {"summary": "score.summary"}\n'


def test_what_goes_out_comes_back_the_same_cells():
    cells = [PortableCell("score", SCORE), PortableCell("report", REPORT)]

    text = portable.render(cells, flow="churn", branch="main")

    assert portable.read(text) == cells


def test_the_same_cells_render_the_same_bytes():
    cells = [PortableCell("score", SCORE)]

    assert portable.render(cells, flow="churn", branch="main") == portable.render(
        cells, flow="churn", branch="main"
    )


def test_the_header_says_it_is_a_file_export():
    text = portable.render([PortableCell("score", SCORE)], flow="churn", branch="main")

    assert text.startswith("# lumlflow file export · flow `churn` · branch `main`")
    assert "1 cell\n" in text
    assert "a file export, not the flow itself" in text.lower()


def test_a_file_written_on_windows_reads_the_same():
    cells = [PortableCell("score", SCORE)]
    text = portable.render(cells, flow="churn", branch="main")

    assert portable.read(text.replace("\n", "\r\n")) == cells


def test_an_export_of_nothing_is_an_export_holding_nothing():
    empty = portable.render([], flow="churn", branch="main")

    assert portable.read(empty) == []


def test_a_file_that_is_not_an_export_says_what_writes_one():
    with pytest.raises(FlowError, match="not a lumlflow export"):
        portable.read("class Score:\n    pass\n")


@pytest.mark.parametrize(
    "name", ["../../escape", "sub/score", "sub\\score", ".hidden", "", "sco\x00re"]
)
def test_a_name_that_could_be_a_path_is_refused(name: str):
    """The file came from outside the workspace, and the name in it becomes a
    filename under `cells/`."""
    with pytest.raises(FlowError, match="not a name a cell can have"):
        portable.read(f"{portable.MARKER}{name}\n{SCORE}")


def test_case_is_left_to_acceptance_to_lowercase_and_flag():
    read = portable.read(f"{portable.MARKER}Score\n{SCORE}")

    assert [cell.slug for cell in read] == ["Score"]
