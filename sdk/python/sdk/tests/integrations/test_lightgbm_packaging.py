from tests.integrations._types import PackagingFixture


def test_df_unified(lgb_df_unified: PackagingFixture) -> None:
    assert lgb_df_unified["ref"].validate()


def test_manifest_tags(lgb_df_unified: PackagingFixture) -> None:
    tags = lgb_df_unified["ref"].get_manifest()["producer_tags"]

    assert "luml.ai::kind_tabular:v1" in tags
    assert not any(
        tag.startswith(("luml.ai::tabular_monitoring:", "luml.ai::llm_monitoring:"))
        for tag in tags
    )


def test_ndarray_unified(lgb_ndarray_unified: PackagingFixture) -> None:
    assert lgb_ndarray_unified["ref"].validate()


def test_ndarray_native(lgb_ndarray_native: PackagingFixture) -> None:
    assert lgb_ndarray_native["ref"].validate()


def test_sparse_native(lgb_sparse_native: PackagingFixture) -> None:
    assert lgb_sparse_native["ref"].validate()
