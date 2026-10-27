import os
import tempfile

import pytest

from dfs_webworker.store import Store


def test_delete_ignores_missing_keys():
    Store.delete("missing")


def test_pop_returns_none_for_missing_keys():
    assert Store.pop("missing") is None


def test_pop_removes_saved_value():
    model_id = Store.save({"model": True})
    assert Store.pop(model_id) == {"model": True}
    assert model_id not in Store._store


def test_pyfunc_deinit_succeeds_for_unknown_model():
    pyfunc = pytest.importorskip("dfs_webworker.pyfunc")
    assert pyfunc.pyfunc_deinit("missing") == {"status": "success"}


def test_pyfunc_deinit_removes_model_file_and_store_entry():
    pyfunc = pytest.importorskip("dfs_webworker.pyfunc")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pyfnx") as temp_file:
        temp_path = temp_file.name
    model_id = Store.save(pyfunc.FnnxPyFunc(model_path=temp_path))
    assert pyfunc.pyfunc_deinit(model_id) == {"status": "success"}
    assert model_id not in Store._store
    assert not os.path.exists(temp_path)
    assert pyfunc.pyfunc_deinit(model_id) == {"status": "success"}
