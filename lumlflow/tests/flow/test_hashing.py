import hashlib
from pathlib import Path

import pytest
from lumlflow.flow.hashing import canonical_json, hash_bytes, hash_file, hash_json


class TestCanonicalJson:
    def test_key_order_does_not_change_the_encoding(self) -> None:
        assert canonical_json({"b": 1, "a": {"d": 2, "c": 3}}) == canonical_json(
            {"a": {"c": 3, "d": 2}, "b": 1}
        )

    def test_has_no_insignificant_whitespace(self) -> None:
        assert canonical_json({"a": 1, "b": [1, 2]}) == b'{"a":1,"b":[1,2]}'

    def test_keeps_non_ascii_readable(self) -> None:
        assert canonical_json({"name": "café"}) == '{"name":"café"}'.encode()

    def test_escapes_newlines_so_a_journal_line_stays_one_line(self) -> None:
        assert b"\n" not in canonical_json({"intent": "fixed\nthe cell"})

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_refuses_values_json_cannot_represent(self, value: float) -> None:
        with pytest.raises(ValueError):
            canonical_json({"metric": value})


class TestHashes:
    def test_json_hash_is_the_hash_of_the_canonical_encoding(self) -> None:
        payload = {"b": 1, "a": 2}
        assert hash_json(payload) == hash_bytes(canonical_json(payload))

    def test_json_hash_ignores_key_order(self) -> None:
        assert hash_json({"a": 1, "b": 2}) == hash_json({"b": 2, "a": 1})

    def test_bytes_hash_is_sha256(self) -> None:
        assert hash_bytes(b"rows") == hashlib.sha256(b"rows").hexdigest()

    def test_file_hash_matches_the_bytes_hash(self, tmp_path: Path) -> None:
        payload = b"x" * (3 * (1 << 20) + 17)
        target = tmp_path / "big.bin"
        target.write_bytes(payload)
        assert hash_file(target) == hash_bytes(payload)

    def test_empty_file_hashes(self, tmp_path: Path) -> None:
        target = tmp_path / "empty.bin"
        target.write_bytes(b"")
        assert hash_file(target) == hash_bytes(b"")
