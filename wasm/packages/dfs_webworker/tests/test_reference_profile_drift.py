"""Guard against the vendored profile module drifting from the SDK canonical copy.

The reference-profile computation is duplicated by vendoring (one canonical copy in
the SDK, a byte-identical copy here) rather than shared via a third wheel, so a
byte-for-byte check is the only thing keeping the two from diverging.
"""

from pathlib import Path

import pytest

_SDK_RELATIVE = Path("sdk/python/sdk/luml/utils/reference_profile.py")
_VENDORED = (
    Path(__file__).resolve().parent.parent / "dfs_webworker" / "reference_profile.py"
)


def _sdk_canonical_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / _SDK_RELATIVE
        if candidate.exists():
            return candidate
    pytest.skip("SDK canonical reference_profile.py not found in this checkout")


def test_vendored_copy_matches_sdk_byte_for_byte() -> None:
    sdk = _sdk_canonical_path()
    assert _VENDORED.read_bytes() == sdk.read_bytes()


def test_vendored_module_is_dependency_light() -> None:
    """The vendored copy must never reach for luml/fnnx/falcon — that is what lets it
    run unchanged inside the Pyodide worker."""
    source = _VENDORED.read_text()
    for forbidden in ("import luml", "import fnnx", "import falcon"):
        assert forbidden not in source
