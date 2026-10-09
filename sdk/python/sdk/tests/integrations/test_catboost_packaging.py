from tests.integrations._types import PackagingFixture


def test_classifier_df_unified(ctb_classifier_df_unified: PackagingFixture) -> None:
    assert ctb_classifier_df_unified["ref"].validate()


def test_manifest_tags(ctb_classifier_df_unified: PackagingFixture) -> None:
    tags = ctb_classifier_df_unified["ref"].get_manifest()["producer_tags"]

    assert "luml.ai::kind_tabular:v1" in tags
    assert not any(
        tag.startswith(("luml.ai::tabular_monitoring:", "luml.ai::llm_monitoring:"))
        for tag in tags
    )


def test_classifier_ndarray_unified(
    ctb_classifier_ndarray_unified: PackagingFixture,
) -> None:
    assert ctb_classifier_ndarray_unified["ref"].validate()


def test_classifier_ndarray_native(
    ctb_classifier_ndarray_native: PackagingFixture,
) -> None:
    assert ctb_classifier_ndarray_native["ref"].validate()


def test_classifier_sparse_native(
    ctb_classifier_sparse_native: PackagingFixture,
) -> None:
    assert ctb_classifier_sparse_native["ref"].validate()


def test_regressor_df_unified(ctb_regressor_df_unified: PackagingFixture) -> None:
    assert ctb_regressor_df_unified["ref"].validate()


def test_regressor_ndarray_unified(
    ctb_regressor_ndarray_unified: PackagingFixture,
) -> None:
    assert ctb_regressor_ndarray_unified["ref"].validate()


def test_regressor_ndarray_native(
    ctb_regressor_ndarray_native: PackagingFixture,
) -> None:
    assert ctb_regressor_ndarray_native["ref"].validate()


def test_regressor_sparse_native(ctb_regressor_sparse_native: PackagingFixture) -> None:
    assert ctb_regressor_sparse_native["ref"].validate()
