def test_df_unified(lgb_df_unified) -> None:
    assert lgb_df_unified["ref"].validate()


def test_ndarray_unified(lgb_ndarray_unified) -> None:
    assert lgb_ndarray_unified["ref"].validate()


def test_ndarray_native(lgb_ndarray_native) -> None:
    assert lgb_ndarray_native["ref"].validate()


def test_sparse_native(lgb_sparse_native) -> None:
    assert lgb_sparse_native["ref"].validate()
