from tests.integrations._types import PackagingFixture
from tests.integrations._utils import _assert_fixture


def test_df_unified(xgb_df_unified: PackagingFixture) -> None:
    _assert_fixture(xgb_df_unified)


def test_ndarray_unified(xgb_ndarray_unified: PackagingFixture) -> None:
    _assert_fixture(xgb_ndarray_unified)


def test_ndarray_native(xgb_ndarray_native: PackagingFixture) -> None:
    _assert_fixture(xgb_ndarray_native)


def test_dmatrix_unified(xgb_dmatrix_unified: PackagingFixture) -> None:
    _assert_fixture(xgb_dmatrix_unified)


def test_dmatrix_native(xgb_dmatrix_native: PackagingFixture) -> None:
    _assert_fixture(xgb_dmatrix_native)


def test_sparse_native(xgb_sparse_native: PackagingFixture) -> None:
    _assert_fixture(xgb_sparse_native)
