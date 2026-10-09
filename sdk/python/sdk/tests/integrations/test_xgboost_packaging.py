from tests.integrations._types import PackagingFixture


def test_df_unified(xgb_df_unified: PackagingFixture) -> None:
    assert xgb_df_unified["ref"].validate()


def test_manifest_tags(xgb_df_unified: PackagingFixture) -> None:
    tags = xgb_df_unified["ref"].get_manifest()["producer_tags"]

    assert "luml.ai::kind_tabular:v1" in tags
    assert not any(
        tag.startswith(("luml.ai::tabular_monitoring:", "luml.ai::llm_monitoring:"))
        for tag in tags
    )


def test_ndarray_unified(xgb_ndarray_unified: PackagingFixture) -> None:
    assert xgb_ndarray_unified["ref"].validate()


def test_ndarray_native(xgb_ndarray_native: PackagingFixture) -> None:
    assert xgb_ndarray_native["ref"].validate()


def test_dmatrix_unified(xgb_dmatrix_unified: PackagingFixture) -> None:
    assert xgb_dmatrix_unified["ref"].validate()


def test_dmatrix_native(xgb_dmatrix_native: PackagingFixture) -> None:
    assert xgb_dmatrix_native["ref"].validate()


def test_sparse_native(xgb_sparse_native: PackagingFixture) -> None:
    assert xgb_sparse_native["ref"].validate()
