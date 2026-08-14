"""The kernel's half of the store's blob areas.

The daemon owns the same layout in `lumlflow.flow.store.cas` and the kernel
cannot import it, so the two are pinned to each other here: same bytes, same
digest, same path — a blob either side writes is a blob either side reads.
"""

from __future__ import annotations

import math

import pytest

from lumlflow_kernel import cas as cas_module
from lumlflow_kernel.cas import Cas, canonical_json, hash_bytes, hash_file


def test_a_blob_is_named_by_its_hash_and_filed_under_a_shard(tmp_path):
    cas = Cas(tmp_path / "values")

    digest = cas.put(b"rows")

    assert digest == hash_bytes(b"rows")
    assert cas.path(digest) == tmp_path / "values" / digest[:2] / digest
    assert cas.get(digest) == b"rows"
    assert cas.exists(digest)


def test_writing_the_same_bytes_twice_costs_one_file(tmp_path):
    cas = Cas(tmp_path / "values")

    first, second = cas.put(b"rows"), cas.put(b"rows")

    assert first == second
    assert len(list((tmp_path / "values" / first[:2]).iterdir())) == 1


def test_a_moved_file_leaves_the_scratch_directory_behind(tmp_path):
    cas = Cas(tmp_path / "values")
    source = tmp_path / "epoch3.pt"
    source.write_bytes(b"weights")

    digest = cas.put_file(source, move=True)

    assert digest == hash_file(cas.path(digest))
    assert not source.exists()


def test_an_install_that_fails_leaves_the_moved_file_where_it_was(
    tmp_path, monkeypatch
):
    """`move=True` is handed the run's own declared output, not a staging copy.
    A `values/` on another filesystem cannot take a rename — and a rename that
    could not happen is no reason to delete the file."""
    cas = Cas(tmp_path / "values")
    source = tmp_path / "epoch3.pt"
    source.write_bytes(b"weights")

    def refuses(*args):
        raise OSError("Invalid cross-device link")

    monkeypatch.setattr(cas_module, "_replace_retry", refuses)

    with pytest.raises(OSError):
        cas.put_file(source, move=True)
    assert source.read_bytes() == b"weights"


def test_a_transient_sharing_violation_is_waited_out_rather_than_raised(
    tmp_path, monkeypatch
):
    """Windows loses the replace to an antivirus or an editor holding the
    target open, which arrives as a `PermissionError` that clears on its own.
    Failing a materialization over one would lose a run to a virus scanner."""
    cas = Cas(tmp_path / "values")
    source = tmp_path / "epoch3.pt"
    source.write_bytes(b"weights")
    replace = cas_module.os.replace
    refusals = [PermissionError(32, "the file is in use by another process")] * 2

    def held(*args):
        if refusals:
            raise refusals.pop()
        return replace(*args)

    monkeypatch.setattr(cas_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(cas_module.os, "replace", held)

    digest = cas.put_file(source, move=True)

    assert refusals == []
    assert cas.get(digest) == b"weights"


def test_a_violation_that_never_clears_is_a_failure_the_cell_hears_about(
    tmp_path, monkeypatch
):
    cas = Cas(tmp_path / "values")
    source = tmp_path / "epoch3.pt"
    source.write_bytes(b"weights")

    def refuses(*args):
        raise PermissionError(32, "the file is in use by another process")

    monkeypatch.setattr(cas_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(cas_module.os, "replace", refuses)

    with pytest.raises(PermissionError):
        cas.put_file(source, move=True)


def test_a_copied_file_is_left_where_the_cell_had_it(tmp_path):
    cas = Cas(tmp_path / "values")
    source = tmp_path / "raw.csv"
    source.write_bytes(b"a,b\n")

    digest = cas.put_file(source, move=False)

    assert cas.get(digest) == b"a,b\n"
    assert source.read_bytes() == b"a,b\n"


def test_ingesting_bytes_already_stored_still_consumes_the_source(tmp_path):
    cas = Cas(tmp_path / "values")
    cas.put(b"weights")
    source = tmp_path / "epoch3.pt"
    source.write_bytes(b"weights")

    cas.put_file(source, move=True)

    assert not source.exists()


def test_the_daemon_reads_back_what_the_kernel_wrote(tmp_path):
    daemon_cas = pytest.importorskip("lumlflow.flow.store.cas")
    root = tmp_path / "values"
    kernel_side = Cas(root)
    daemon_side = daemon_cas.Cas(root)

    digest = kernel_side.put(b"arrow bytes")

    assert daemon_side.path(digest) == kernel_side.path(digest)
    assert daemon_side.get(digest) == b"arrow bytes"
    assert daemon_side.put(b"arrow bytes") == digest


def test_canonical_json_refuses_what_no_reader_could_agree_on():
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    with pytest.raises(ValueError):
        canonical_json({"loss": math.nan})
