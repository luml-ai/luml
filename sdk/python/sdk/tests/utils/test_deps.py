"""Dependency auto-detection: what a packaged model declares it needs at runtime."""

import importlib
import sys
from importlib.metadata import version
from pathlib import Path

from luml.utils.deps import _owning_distribution, find_dependencies


class TestFindDependencies:
    def test_a_module_is_attributed_to_the_distribution_that_ships_its_file(
        self,
    ) -> None:
        """Several distributions may fill in one top-level package; the file decides."""
        file_to_dist = {
            str(Path("/site/langgraph/pregel/__init__.py")): "langgraph",
            str(Path("/site/langgraph/prebuilt/__init__.py")): "langgraph-prebuilt",
        }
        module_to_dist = {
            "langgraph": "langgraph-prebuilt"
        }  # what a name-only map ends up with

        core = _owning_distribution(
            Path("/site/langgraph/pregel/__init__.py"),
            "langgraph",
            file_to_dist,
            module_to_dist,
        )
        prebuilt = _owning_distribution(
            Path("/site/langgraph/prebuilt/__init__.py"),
            "langgraph",
            file_to_dist,
            module_to_dist,
        )

        assert core == "langgraph"
        assert prebuilt == "langgraph-prebuilt"

    def test_a_file_the_metadata_does_not_list_falls_back_to_the_package_name(
        self,
    ) -> None:
        """Compiled extensions and the like: the old behaviour, kept as the fallback."""
        found = _owning_distribution(
            Path("/site/numpy/_core/_multiarray_umath.so"),
            "numpy",
            {},
            {"numpy": "numpy"},
        )

        assert found == "numpy"

    def test_every_distribution_of_the_langgraph_namespace_is_declared(self) -> None:
        """The core `langgraph` distribution used to be dropped in favour of a sibling.

        A packaged graph then failed inside its container with
        ``No module named 'langgraph.pregel'`` while `langgraph-prebuilt` was present.
        """
        importlib.import_module("langgraph.pregel")
        importlib.import_module("langgraph.prebuilt")
        assert "langgraph.pregel" in sys.modules

        pip_requirements, _ = find_dependencies()

        names = {req.split("==")[0].lower() for req in pip_requirements}
        assert "langgraph" in names
        assert "langgraph-prebuilt" in names
        assert f"langgraph=={version('langgraph')}" in pip_requirements
