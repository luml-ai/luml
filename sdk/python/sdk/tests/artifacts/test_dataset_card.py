from __future__ import annotations

import io
import re
import tarfile
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from luml import CardBuilder, DatasetReference, save_tabular_dataset


@pytest.fixture
def dataset_ref(tmp_path: Path) -> DatasetReference:
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    return save_tabular_dataset(
        df,
        name="test-ds",
        output_path=str(tmp_path / "ds.tar"),
    )


CARD_PATH_RE = re.compile(
    r"meta_artifacts/dataforce\.studio~c~~c~dataset_card~c~v1~~et~~.+/dataset_card\.zip$"
)


def test_add_dataset_card_with_builder(dataset_ref: DatasetReference) -> None:
    builder = CardBuilder(title="Test Dataset")
    builder.write("# Dataset Info")
    dataset_ref.add_dataset_card(builder)

    with tarfile.open(dataset_ref.path, "r") as tar:
        names = tar.getnames()
        matches = [n for n in names if CARD_PATH_RE.match(n)]
        assert len(matches) == 1

        zip_data = tar.extractfile(tar.getmember(matches[0]))
        assert zip_data is not None
        with zipfile.ZipFile(io.BytesIO(zip_data.read())) as zf:
            html = zf.read("index.html").decode("utf-8")
            assert "Test Dataset" in html


def test_add_dataset_card_with_html_string(dataset_ref: DatasetReference) -> None:
    html_content = "<html><body>Dataset docs</body></html>"
    dataset_ref.add_dataset_card(html_content)

    with tarfile.open(dataset_ref.path, "r") as tar:
        names = tar.getnames()
        matches = [n for n in names if CARD_PATH_RE.match(n)]
        assert len(matches) == 1

        zip_data = tar.extractfile(tar.getmember(matches[0]))
        assert zip_data is not None
        with zipfile.ZipFile(io.BytesIO(zip_data.read())) as zf:
            html = zf.read("index.html").decode("utf-8")
            assert html == html_content


def test_add_dataset_card_invalid_type(dataset_ref: DatasetReference) -> None:
    with pytest.raises(TypeError, match="must be a string or CardBuilder instance"):
        dataset_ref.add_dataset_card(12345)  # type: ignore[arg-type]


def test_validate_after_adding_card(dataset_ref: DatasetReference) -> None:
    builder = CardBuilder(title="Card")
    builder.write("content")
    dataset_ref.add_dataset_card(builder)
    assert dataset_ref.validate() is True
