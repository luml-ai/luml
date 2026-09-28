import threading

import pytest
from lumlflow.flow.ids import ULID_LENGTH, is_ulid, new_ulid

_CROCKFORD = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


class TestNewUlid:
    def test_shape(self) -> None:
        value = new_ulid()
        assert len(value) == ULID_LENGTH
        assert set(value) <= _CROCKFORD
        assert is_ulid(value)

    def test_ids_are_unique(self) -> None:
        assert len({new_ulid() for _ in range(5000)}) == 5000

    def test_sorts_in_mint_order(self) -> None:
        minted = [new_ulid() for _ in range(1000)]
        assert minted == sorted(minted)

    def test_stays_ordered_within_one_millisecond(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)
        minted = [new_ulid() for _ in range(100)]
        assert minted == sorted(minted)
        assert len(set(minted)) == 100

    def test_mints_uniquely_across_threads(self) -> None:
        minted: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            batch = [new_ulid() for _ in range(200)]
            with lock:
                minted.extend(batch)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(set(minted)) == len(minted) == 1600


class TestIsUlid:
    @pytest.mark.parametrize(
        "value",
        ["", "01J9W3ZK7Q", "01j9w3zk7qabcdef0123456789", "01J9W3ZK7QABCDEF012345678U"],
    )
    def test_rejects_malformed(self, value: str) -> None:
        assert not is_ulid(value)
