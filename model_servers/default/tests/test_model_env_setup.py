"""The conda environment a model container builds for its worker.

The worker (``conda_worker.py``) runs inside the model's environment and needs a few
packages of its own on top of the model's. Adding them must not make the model's own
pins unsatisfiable, and a build that fails must not leave a half-built environment for
the container's next start to trip over.
"""

import logging
import subprocess
from unittest.mock import patch

import pytest

from handlers import model_handler as model_handler_module
from handlers.model_handler import WORKER_PACKAGES, ModelHandler


def _deps(*specs: str) -> list[dict]:
    return [{"package": spec, "extra_pip_args": None, "condition": None} for spec in specs]


def _packages(extra: list[dict]) -> dict[str, str | None]:
    """name -> pinned version, or None when the requirement is left to the resolver."""
    return {
        d["package"].split("==")[0]: (d["package"].split("==")[1] if "==" in d["package"] else None)
        for d in extra
    }


class FakeEnvManager:
    """Stands in for fnnx's CondaLikeEnvManager: the prefix exists, pip failed inside it."""

    _exe = "/usr/local/bin/micromamba"
    env_id = "deadbeef"

    def __init__(self, env_config: dict) -> None:
        self.env_config = env_config

    def ensure(self) -> str:
        raise RuntimeError("Command failed: pip install -r requirements.txt")


class TestModelEnvSetup:
    def test_worker_packages_follow_the_model_pin_of_the_opentelemetry_family(self) -> None:
        """A model that ships one part of OpenTelemetry pins the family for everyone.

        The image's own 1.43 parts next to the model's 1.42 part gave pip no solution;
        the family is released in lockstep, so the worker takes the model's version.
        """
        extra = ModelHandler._worker_dependencies(
            _deps("langgraph==1.2.4", "opentelemetry-exporter-otlp-proto-common==1.42.1")
        )

        packages = _packages(extra)
        assert packages["opentelemetry-api"] == "1.42.1"
        assert packages["opentelemetry-sdk"] == "1.42.1"
        assert packages["opentelemetry-exporter-otlp-proto-grpc"] == "1.42.1"
        assert "uvicorn" in packages  # the image's own version: the model said nothing

    def test_without_a_model_pin_the_image_versions_are_used(self) -> None:
        with patch.object(model_handler_module.importlib_metadata, "version", return_value="9.9.9"):
            extra = ModelHandler._worker_dependencies(_deps("scikit-learn==1.8.0"))

        assert _packages(extra) == dict.fromkeys(WORKER_PACKAGES, "9.9.9")

    def test_packages_the_model_already_ships_are_not_added_twice(self) -> None:
        """Name matching is by distribution, however the model spelled it."""
        with patch.object(
            model_handler_module.importlib_metadata, "version", return_value="1.43.0"
        ):
            extra = ModelHandler._worker_dependencies(
                _deps("Uvicorn==0.30.6", "opentelemetry_api==1.42.1 ; python_version >= '3.10'")
            )

        packages = _packages(extra)
        assert "uvicorn" not in packages  # shipped unconditionally, however spelled
        # mentioned only under a marker: required unconditionally, left to the resolver
        assert packages["opentelemetry-api"] is None
        assert packages["opentelemetry-sdk"] is None

    def test_a_family_floor_without_an_exact_pin_leaves_the_core_to_the_resolver(self) -> None:
        """`>=` is a constraint, not a version: nothing to follow, but something to respect.

        The image's pins might sit inside the floor or not; pip can tell, this code
        cannot. So the worker's parts go in unpinned and the resolver reconciles them
        with the model's constraint.
        """
        with patch.object(
            model_handler_module.importlib_metadata, "version", return_value="1.43.0"
        ):
            extra = ModelHandler._worker_dependencies(_deps("opentelemetry-api>=1.30"))

        packages = _packages(extra)
        assert packages["opentelemetry-sdk"] is None
        assert packages["opentelemetry-exporter-otlp-proto-grpc"] is None
        assert "opentelemetry-api" not in packages  # the model brought it
        assert packages["uvicorn"] == "1.43.0"

    def test_a_worker_package_mentioned_only_under_a_marker_is_still_required(self) -> None:
        """`uvicorn ; python_version < "3.11"` installs nothing on 3.12 — and the worker
        imports uvicorn. A conditional mention is not a guarantee, so an unconditional,
        unpinned line goes in; pip reconciles it with the marked one where that holds."""
        extra = ModelHandler._worker_dependencies(
            _deps(
                'Uvicorn[standard]==0.29.0 ; python_version < "3.11"',
                'opentelemetry-api==1.42.1 ; python_version < "3.11"',
            )
        )

        packages = _packages(extra)
        assert "uvicorn" in packages and packages["uvicorn"] is None
        assert "opentelemetry-api" in packages and packages["opentelemetry-api"] is None
        assert packages["opentelemetry-sdk"] is None  # family mentioned, no core pin

    def test_an_unconditional_line_beside_a_conditional_one_counts_as_shipped(self) -> None:
        extra = ModelHandler._worker_dependencies(
            _deps('uvicorn==0.29.0 ; python_version < "3.11"', "uvicorn==0.30.6")
        )

        assert "uvicorn" not in _packages(extra)

    def test_conditional_pins_are_left_to_the_resolver(self) -> None:
        """Mutually exclusive pins for different Pythons: which one holds inside the
        target environment is the resolver's call, so neither is followed."""
        with patch.object(
            model_handler_module.importlib_metadata, "version", return_value="1.43.0"
        ):
            extra = ModelHandler._worker_dependencies(
                [
                    {"package": 'opentelemetry-api==1.20.0 ; python_version < "3.11"'},
                    {"package": 'opentelemetry-api==1.42.1 ; python_version >= "3.11"'},
                    {
                        "package": "opentelemetry-sdk==1.42.1",
                        "condition": "python_version >= '3.11'",
                    },
                ]
            )

        packages = _packages(extra)
        assert packages["opentelemetry-exporter-otlp-proto-grpc"] is None
        # mentioned only conditionally: required unconditionally, pinned by nobody but pip
        assert packages["opentelemetry-api"] is None and packages["opentelemetry-sdk"] is None

    def test_a_beta_package_of_the_family_does_not_set_the_api_version(self) -> None:
        """semantic-conventions and the instrumentations run a 0.x line of their own.

        Pinning the API/SDK to 0.63b1 would be invalid; the version comes from the
        core parts only, whichever order the model listed them in.
        """
        extra = ModelHandler._worker_dependencies(
            _deps(
                "opentelemetry-semantic-conventions==0.63b1",
                "opentelemetry-instrumentation-httpx==0.63b1",
                "opentelemetry-sdk==1.42.1",
            )
        )

        packages = _packages(extra)
        assert packages["opentelemetry-api"] == "1.42.1"
        assert packages["opentelemetry-exporter-otlp-proto-grpc"] == "1.42.1"

    def test_only_a_beta_package_present_leaves_the_core_to_the_resolver(self) -> None:
        """The SDK pins its own semantic-conventions release exactly (1.43 ↔ 0.64b).

        A model pinning only ``semantic-conventions==0.63b1`` cannot take the image's
        1.43 SDK — the set would be unsatisfiable — and this code does not know which
        SDK release goes with 0.63. pip does: the worker's parts go in unpinned.
        """
        with patch.object(
            model_handler_module.importlib_metadata, "version", return_value="1.43.0"
        ):
            extra = ModelHandler._worker_dependencies(
                _deps("opentelemetry-semantic-conventions==0.63b1")
            )

        packages = _packages(extra)
        assert packages["opentelemetry-api"] is None
        assert packages["opentelemetry-sdk"] is None
        assert packages["opentelemetry-exporter-otlp-proto-grpc"] is None
        assert packages["uvicorn"] == "1.43.0"  # the image's, as before
        assert not any("==1.43" in d["package"] for d in extra if "opentelemetry" in d["package"])

    def test_a_removal_that_fails_is_said_so_and_the_build_error_still_surfaces(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        handler = ModelHandler.__new__(ModelHandler)
        handler._get_env = lambda: {  # type: ignore[method-assign]
            "python3::conda_pip": {"python_version": "3.12", "dependencies": _deps("numpy==2.0")}
        }

        def locked(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="environment is locked")

        with (
            patch.object(model_handler_module, "CondaLikeEnvManager", FakeEnvManager),
            patch.object(model_handler_module, "install_micromamba"),
            patch.object(model_handler_module.importlib_metadata, "version", return_value="1.0"),
            patch.object(model_handler_module.subprocess, "run", locked),
            caplog.at_level(logging.WARNING),
            pytest.raises(RuntimeError, match="pip install"),
        ):
            handler._create_model_env()

        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("Could not discard fnnx-deadbeef" in w and "locked" in w for w in warnings)
        assert not any("Discarded" in r.getMessage() for r in caplog.records)

    def test_a_failed_build_discards_the_half_built_environment(self) -> None:
        """Left behind, the prefix is 'reused' on the container's restart and the worker
        dies on the first missing package — hiding what really failed."""
        handler = ModelHandler.__new__(ModelHandler)
        handler._get_env = lambda: {  # type: ignore[method-assign]
            "python3::conda_pip": {"python_version": "3.12", "dependencies": _deps("numpy==2.0")}
        }
        removed: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
            removed.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        with (
            patch.object(model_handler_module, "CondaLikeEnvManager", FakeEnvManager),
            patch.object(model_handler_module, "install_micromamba"),
            patch.object(model_handler_module.importlib_metadata, "version", return_value="1.0"),
            patch.object(model_handler_module.subprocess, "run", fake_run),
        ):
            try:
                handler._create_model_env()
            except RuntimeError as error:
                assert "pip install" in str(error)  # the real failure, not a follow-on one
            else:
                raise AssertionError("a failed build must raise")

        assert removed == [
            ["/usr/local/bin/micromamba", "env", "remove", "-n", "fnnx-deadbeef", "-y"]
        ]
