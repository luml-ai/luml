import os
from pathlib import Path

import pytest
from lumlflow.flow.atomic import atomic_write_bytes, replace_retry, unlink_retry


class TestAtomicWriteBytes:
    def test_creates_missing_parents(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "deeper" / "flow.yaml"
        atomic_write_bytes(target, b"name: churn\n")
        assert target.read_bytes() == b"name: churn\n"

    def test_replaces_existing_content(self, tmp_path: Path) -> None:
        target = tmp_path / "flow.yaml"
        atomic_write_bytes(target, b"first")
        atomic_write_bytes(target, b"second")
        assert target.read_bytes() == b"second"

    def test_leaves_no_temp_files_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "flow.yaml"
        atomic_write_bytes(target, b"body")
        assert list(tmp_path.iterdir()) == [target]

    def test_cleans_up_its_temp_when_the_replace_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "flow.yaml"
        atomic_write_bytes(target, b"original")
        monkeypatch.setattr(
            "lumlflow.flow.atomic.replace_retry",
            lambda source, destination: (_ for _ in ()).throw(OSError("disk full")),
        )

        with pytest.raises(OSError, match="disk full"):
            atomic_write_bytes(target, b"replacement")

        assert list(tmp_path.iterdir()) == [target]
        assert target.read_bytes() == b"original"


class TestReplaceRetry:
    def test_retries_a_transient_sharing_violation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "incoming"
        source.write_bytes(b"new")
        target = tmp_path / "held-open-by-a-virus-scanner"
        target.write_bytes(b"old")
        real_replace = os.replace
        attempts = {"count": 0}

        def flaky(src: object, dst: object) -> None:
            attempts["count"] += 1
            if attempts["count"] <= 2:
                raise PermissionError(32, "The process cannot access the file")
            real_replace(src, dst)  # type: ignore[arg-type]

        monkeypatch.setattr(os, "replace", flaky)
        replace_retry(source, target)

        assert attempts["count"] == 3
        assert target.read_bytes() == b"new"
        assert not source.exists()

    def test_surfaces_a_violation_that_never_clears(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("lumlflow.flow.atomic.time.sleep", lambda _seconds: None)

        def always_locked(src: object, dst: object) -> None:
            raise PermissionError(32, "The process cannot access the file")

        monkeypatch.setattr(os, "replace", always_locked)

        with pytest.raises(PermissionError):
            replace_retry(tmp_path / "incoming", tmp_path / "target")


class TestUnlinkRetry:
    def test_waits_out_whoever_is_holding_the_file_open(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A projected cell an editor still has open is the Windows case: the
        removal is refused for a moment, never for good."""
        monkeypatch.setattr("lumlflow.flow.atomic.time.sleep", lambda _seconds: None)
        target = tmp_path / "features.py"
        target.write_bytes(b"class Features: ...")
        real_unlink = Path.unlink
        attempts = {"count": 0}

        def flaky(self: Path, **kwargs: object) -> None:
            attempts["count"] += 1
            if attempts["count"] <= 2:
                raise PermissionError(32, "The process cannot access the file")
            real_unlink(self, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "unlink", flaky)
        unlink_retry(target)

        assert attempts["count"] == 3
        assert not target.exists()

    def test_a_file_already_gone_is_not_a_failure(self, tmp_path: Path) -> None:
        unlink_retry(tmp_path / "never-existed.py")

    def test_surfaces_a_hold_that_never_clears(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("lumlflow.flow.atomic.time.sleep", lambda _seconds: None)

        def always_locked(self: Path, **kwargs: object) -> None:
            raise PermissionError(32, "The process cannot access the file")

        monkeypatch.setattr(Path, "unlink", always_locked)

        with pytest.raises(PermissionError):
            unlink_retry(tmp_path / "held.py")
