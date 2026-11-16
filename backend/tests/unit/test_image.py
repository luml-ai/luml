import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_python_base_is_digest_pinned_and_shared_between_build_and_runtime() -> None:
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text()
    assert re.search(
        r"^FROM python:3\.14-slim-bookworm@sha256:[a-f0-9]{64} AS base$",
        dockerfile,
        re.MULTILINE,
    )
    assert "FROM base AS builder" in dockerfile
    assert "FROM base AS runtime" in dockerfile
