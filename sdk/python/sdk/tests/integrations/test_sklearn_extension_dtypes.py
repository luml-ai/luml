from pathlib import Path

import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor

from luml.integrations.sklearn import save_sklearn


@pytest.mark.parametrize(
    ("dtype", "values", "expected"),
    [
        ("Int64", [1, 2, 3, 4], "int"),
        ("Float64", [1.0, 2.0, 3.0, 4.0], "float"),
        ("string", ["a", "b", "a", "b"], "str"),
        ("category", ["a", "b", "a", "b"], "str"),
    ],
)
def test_save_sklearn_extension_dtypes(
    tmp_path: Path, dtype: str, values: list, expected: str
) -> None:
    frame = pd.DataFrame({"feature": pd.Series(values, dtype=dtype)})
    model = DummyRegressor().fit(frame, [1, 2, 3, 4])
    reference = save_sklearn(model, frame, path=str(tmp_path / "model.luml"))
    manifest = reference.get_manifest()
    assert manifest["inputs"][0]["dtype"] == f"Array[{expected}]"
