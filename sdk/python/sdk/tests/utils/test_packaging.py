from typing import Any

import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from luml.utils.packaging import normalize_inputs, resolve_dtype


@pytest.mark.parametrize(
    ("dtype", "expected"),
    [
        (pd.Int64Dtype(), "int"),
        (pd.UInt32Dtype(), "int"),
        (pd.Float64Dtype(), "float"),
        (pd.StringDtype(), "str"),
        (pd.CategoricalDtype([1, 2]), "str"),
        (pd.BooleanDtype(), "str"),
        (pd.DatetimeTZDtype(tz="UTC"), "str"),
        (np.dtype("float32"), "float"),
        (np.dtype("int32"), "int"),
        (np.dtype("object"), "str"),
    ],
)
def test_resolve_dtype(dtype: Any, expected: str) -> None:  # noqa: ANN401
    assert resolve_dtype(dtype) == expected


def test_normalize_sparse_inputs() -> None:
    matrix = sparse.csr_matrix([[1, 0], [0, 2]])
    result, names, categories = normalize_inputs(matrix, "native")
    assert result is matrix
    assert names == ["x0", "x1"]
    assert categories == {}
    with pytest.raises(ValueError, match="Sparse requires"):
        normalize_inputs(matrix, "unified")
