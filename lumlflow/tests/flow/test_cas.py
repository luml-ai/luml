import os
from pathlib import Path

import pytest
from lumlflow.flow.hashing import hash_bytes
from lumlflow.flow.store.cas import Cas


@pytest.fixture
def cas(tmp_path: Path) -> Cas:
    area = Cas(tmp_path / "values")
    area.ensure()
    return area


class TestPut:
    def test_round_trips_bytes_under_their_sha256(self, cas: Cas) -> None:
        digest = cas.put(b"rows,go,here")
        assert digest == hash_bytes(b"rows,go,here")
        assert cas.get(digest) == b"rows,go,here"
        assert cas.exists(digest)

    def test_shards_by_the_first_two_characters(self, cas: Cas) -> None:
        digest = cas.put(b"rows")
        assert cas.path(digest) == cas.root / digest[:2] / digest
        assert cas.path(digest).is_file()

    def test_identical_bytes_cost_one_file(self, cas: Cas) -> None:
        first = cas.put(b"rows")
        second = cas.put(b"rows")
        assert first == second
        assert list((cas.root / first[:2]).iterdir()) == [cas.path(first)]

    def test_leaves_no_staging_files(self, cas: Cas) -> None:
        cas.put(b"rows")
        cas.put(b"other rows")
        assert list((cas.root / "tmp").iterdir()) == []

    def test_stores_empty_content(self, cas: Cas) -> None:
        assert cas.get(cas.put(b"")) == b""


class TestPutFile:
    def test_copies_by_default(self, cas: Cas, tmp_path: Path) -> None:
        source = tmp_path / "epoch3.pt"
        source.write_bytes(b"weights")
        digest = cas.put_file(source)
        assert cas.get(digest) == b"weights"
        assert source.exists()

    def test_move_consumes_the_source(self, cas: Cas, tmp_path: Path) -> None:
        source = tmp_path / "epoch3.pt"
        source.write_bytes(b"weights")
        digest = cas.put_file(source, move=True)
        assert cas.get(digest) == b"weights"
        assert not source.exists()

    def test_move_consumes_the_source_even_when_already_stored(
        self, cas: Cas, tmp_path: Path
    ) -> None:
        cas.put(b"weights")
        source = tmp_path / "epoch3.pt"
        source.write_bytes(b"weights")
        cas.put_file(source, move=True)
        assert not source.exists()

    def test_every_ingest_path_flushes_the_blob_before_installing_it(
        self, cas: Cas, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_fsync, real_replace = os.fsync, os.replace
        order: list[str] = []

        def recording_fsync(fd: int) -> None:
            order.append("fsync")
            real_fsync(fd)

        def recording_replace(source: object, target: object) -> None:
            order.append("replace")
            real_replace(source, target)  # type: ignore[arg-type]

        monkeypatch.setattr(os, "fsync", recording_fsync)
        monkeypatch.setattr(os, "replace", recording_replace)
        for name, ingest in (
            ("bytes", lambda path: cas.put(path.read_bytes())),
            ("copy", lambda path: cas.put_file(path)),
            ("move", lambda path: cas.put_file(path, move=True)),
        ):
            order.clear()
            source = tmp_path / f"{name}.pt"
            source.write_bytes(f"weights via {name}".encode())
            ingest(source)
            assert order.index("fsync") < order.index("replace"), name

    def test_ingests_content_larger_than_one_chunk(
        self, cas: Cas, tmp_path: Path
    ) -> None:
        payload = b"z" * (2 * (1 << 20) + 5)
        source = tmp_path / "big.bin"
        source.write_bytes(payload)
        assert cas.get(cas.put_file(source)) == payload
        assert list((cas.root / "tmp").iterdir()) == []


class TestDigestValidation:
    @pytest.mark.parametrize(
        "digest",
        [
            "../../../etc/passwd",
            "",
            "abc",
            "g" * 64,
            "A" * 64,
            "a" * 63,
            "a" * 64 + "/x",
        ],
    )
    def test_refuses_anything_that_is_not_a_content_hash(
        self, cas: Cas, digest: str
    ) -> None:
        with pytest.raises(ValueError):
            cas.path(digest)

    def test_missing_blob_reads_as_a_missing_file(self, cas: Cas) -> None:
        with pytest.raises(FileNotFoundError):
            cas.get("f" * 64)
