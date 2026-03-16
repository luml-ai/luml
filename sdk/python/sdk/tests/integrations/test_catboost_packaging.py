def test_classifier_df_unified(ctb_classifier_df_unified):
    assert ctb_classifier_df_unified["ref"].validate()

def test_classifier_ndarray_unified(ctb_classifier_ndarray_unified):
    assert ctb_classifier_ndarray_unified["ref"].validate()

def test_classifier_ndarray_native(ctb_classifier_ndarray_native):
    assert ctb_classifier_ndarray_native["ref"].validate()

def test_classifier_sparse_native(ctb_classifier_sparse_native):
    assert ctb_classifier_sparse_native["ref"].validate()

def test_regressor_df_unified(ctb_regressor_df_unified):
    assert ctb_regressor_df_unified["ref"].validate()

def test_regressor_ndarray_unified(ctb_regressor_ndarray_unified):
    assert ctb_regressor_ndarray_unified["ref"].validate()

def test_regressor_ndarray_native(ctb_regressor_ndarray_native):
    assert ctb_regressor_ndarray_native["ref"].validate()

def test_regressor_sparse_native(ctb_regressor_sparse_native):
    assert ctb_regressor_sparse_native["ref"].validate()
