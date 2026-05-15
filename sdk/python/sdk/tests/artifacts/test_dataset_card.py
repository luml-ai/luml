from __future__ import annotations

import io
import re
import tarfile
import zipfile
from pathlib import Path

import pytest

from luml import CardBuilder, DatasetReference, save_tabular_dataset


def _make_dataset_tar(tar_path: Path) -> DatasetReference:
    import pandas as pd

    return save_tabular_dataset(
        pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}),
        name="test-ds",
        output_path=str(tar_path),
    )


_CARD_PATH_RE = re.compile(
    r"meta_artifacts/dataforce\.studio~c~~c~dataset_card~c~v1~~et~~.*/dataset_card\.zip"
)


class TestAddDatasetCardWithBuilder:
    def test_zip_at_expected_tar_path(self, tmp_path: Path) -> None:
        ref = _make_dataset_tar(tmp_path / "ds.tar")
        builder = CardBuilder(title="Test Dataset")
        builder.write("# Dataset Info")
        ref.add_dataset_card(builder)

        with tarfile.open(ref.path, "r") as tar:
            names = tar.getnames()
            assert any(_CARD_PATH_RE.match(n) for n in names)

    def test_index_html_has_correct_content(self, tmp_path: Path) -> None:
        ref = _make_dataset_tar(tmp_path / "ds.tar")
        builder = CardBuilder(title="Test Dataset")
        builder.write("# Dataset Info")
        expected_html = builder.build()
        ref.add_dataset_card(builder)

        with tarfile.open(ref.path, "r") as tar:
            zip_name = next(n for n in tar.getnames() if _CARD_PATH_RE.match(n))
            zip_data = tar.extractfile(zip_name)
            assert zip_data is not None
            with zipfile.ZipFile(io.BytesIO(zip_data.read())) as zf:
                assert zf.read("index.html").decode("utf-8") == expected_html


class TestAddDatasetCardWithString:
    def test_zip_at_expected_tar_path(self, tmp_path: Path) -> None:
        ref = _make_dataset_tar(tmp_path / "ds.tar")
        ref.add_dataset_card("<html><body>Dataset docs</body></html>")

        with tarfile.open(ref.path, "r") as tar:
            names = tar.getnames()
            assert any(_CARD_PATH_RE.match(n) for n in names)

    def test_index_html_has_correct_content(self, tmp_path: Path) -> None:
        html = "<html><body>Dataset docs</body></html>"
        ref = _make_dataset_tar(tmp_path / "ds.tar")
        ref.add_dataset_card(html)

        with tarfile.open(ref.path, "r") as tar:
            zip_name = next(n for n in tar.getnames() if _CARD_PATH_RE.match(n))
            zip_data = tar.extractfile(zip_name)
            assert zip_data is not None
            with zipfile.ZipFile(io.BytesIO(zip_data.read())) as zf:
                assert zf.read("index.html").decode("utf-8") == html


class TestAddDatasetCardInvalidType:
    def test_raises_type_error(self, tmp_path: Path) -> None:
        ref = _make_dataset_tar(tmp_path / "ds.tar")
        with pytest.raises(TypeError, match="must be a string or CardBuilder instance"):
            ref.add_dataset_card(12345)  # type: ignore[arg-type]


class TestDatasetReferenceValidateAfterCard:
    def test_validate_returns_true(self, tmp_path: Path) -> None:
        ref = _make_dataset_tar(tmp_path / "ds.tar")
        ref.add_dataset_card("<html><body>Card</body></html>")
        assert ref.validate() is True
