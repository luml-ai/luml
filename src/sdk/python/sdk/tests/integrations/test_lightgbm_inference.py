from typing import Any

from tests.integrations._types import PackagingFixture
from tests.integrations._utils import _get_preds, _run


def _assert_close(preds: Any, expected: list[Any], atol: float = 1e-5) -> None:  # noqa: ANN401
    assert len(preds) == len(expected)
    assert all(abs(p - e) < atol for p, e in zip(preds, expected, strict=False))


def _assert_fixture(f: PackagingFixture) -> None:
    _assert_close(
        _get_preds(_run(f["ref"].path, f["inputs"]), f["preds_key"]), f["expected"]
    )


def test_df_unified(lgb_df_unified: PackagingFixture) -> None:
    _assert_fixture(lgb_df_unified)


def test_ndarray_unified(lgb_ndarray_unified: PackagingFixture) -> None:
    _assert_fixture(lgb_ndarray_unified)


def test_ndarray_native(lgb_ndarray_native: PackagingFixture) -> None:
    _assert_fixture(lgb_ndarray_native)


def test_sparse_native(lgb_sparse_native: PackagingFixture) -> None:
    _assert_fixture(lgb_sparse_native)
