def test_df_unified(xgb_df_unified):
    assert xgb_df_unified["ref"].validate()

def test_ndarray_unified(xgb_ndarray_unified):
    assert xgb_ndarray_unified["ref"].validate()

def test_ndarray_native(xgb_ndarray_native):
    assert xgb_ndarray_native["ref"].validate()

def test_dmatrix_unified(xgb_dmatrix_unified):
    assert xgb_dmatrix_unified["ref"].validate()

def test_dmatrix_native(xgb_dmatrix_native):
    assert xgb_dmatrix_native["ref"].validate()

def test_sparse_native(xgb_sparse_native):
    assert xgb_sparse_native["ref"].validate()
