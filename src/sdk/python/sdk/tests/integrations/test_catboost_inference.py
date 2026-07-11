from tests.integrations._types import PackagingFixture
from tests.integrations._utils import _assert_fixture


def test_classifier_df_unified(ctb_classifier_df_unified: PackagingFixture) -> None:
    _assert_fixture(ctb_classifier_df_unified)


def test_classifier_ndarray_unified(
    ctb_classifier_ndarray_unified: PackagingFixture,
) -> None:
    _assert_fixture(ctb_classifier_ndarray_unified)


def test_classifier_ndarray_native(
    ctb_classifier_ndarray_native: PackagingFixture,
) -> None:
    _assert_fixture(ctb_classifier_ndarray_native)


def test_classifier_sparse_native(
    ctb_classifier_sparse_native: PackagingFixture,
) -> None:
    _assert_fixture(ctb_classifier_sparse_native)


def test_regressor_df_unified(ctb_regressor_df_unified: PackagingFixture) -> None:
    _assert_fixture(ctb_regressor_df_unified)


def test_regressor_ndarray_unified(
    ctb_regressor_ndarray_unified: PackagingFixture,
) -> None:
    _assert_fixture(ctb_regressor_ndarray_unified)


def test_regressor_ndarray_native(
    ctb_regressor_ndarray_native: PackagingFixture,
) -> None:
    _assert_fixture(ctb_regressor_ndarray_native)


def test_regressor_sparse_native(ctb_regressor_sparse_native: PackagingFixture) -> None:
    _assert_fixture(ctb_regressor_sparse_native)
