"""Keep the luml-api skill true to the installed client.

Every `client.<resource>.<method>(...)` and `monitoring.<method>(...)` call in
the skill's code blocks must exist and accept the keywords used, and every
`luml_api` import must resolve.
"""

import ast
import importlib
import inspect
import re
from collections.abc import Callable, Iterator
from functools import cached_property
from pathlib import Path

import pytest

from luml_api import AsyncLumlClient, LumlClient
from luml_api.resources.monitoring import DeploymentMonitoring

SKILL_DIR = Path(__file__).resolve().parents[2] / "luml_api/skills/luml-api"
PYTHON_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _sync_resource_class(attribute: str) -> type:
    """`client.tracks` is the `TrackResource` defined in `luml_api.resources.tracks`."""
    module = importlib.import_module(f"luml_api.resources.{attribute}")
    (resource,) = [
        value
        for name, value in vars(module).items()
        if inspect.isclass(value)
        and value.__module__ == module.__name__
        and name.endswith("Resource")
        and not name.startswith("Async")
    ]
    return resource


RESOURCES: dict[str, type] = {
    name: _sync_resource_class(name)
    for name in dir(LumlClient)
    if isinstance(getattr(LumlClient, name, None), cached_property)
}


def _all_blocks() -> Iterator[tuple[str, str]]:
    for path in sorted(SKILL_DIR.rglob("*.md")):
        for index, block in enumerate(PYTHON_BLOCK.findall(path.read_text())):
            yield f"{path.relative_to(SKILL_DIR)}#{index}", block


BLOCKS = list(_all_blocks())
IDS = [where for where, _ in BLOCKS]


def _parse(block: str) -> ast.Module:
    return ast.parse(block.replace("await ", ""))


@pytest.mark.parametrize(("where", "block"), BLOCKS, ids=IDS)
def test_block_parses(where: str, block: str) -> None:
    _parse(block)


@pytest.mark.parametrize(("where", "block"), BLOCKS, ids=IDS)
def test_luml_api_imports_exist(where: str, block: str) -> None:
    for node in ast.walk(_parse(block)):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "luml_api"
        ):
            module = importlib.import_module(node.module or "")
            for alias in node.names:
                assert hasattr(module, alias.name), f"{node.module}.{alias.name}"


def _client_calls(block: str) -> Iterator[tuple[type, str, ast.Call]]:
    for node in ast.walk(_parse(block)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        owner = node.func.value
        if (
            isinstance(owner, ast.Attribute)
            and isinstance(owner.value, ast.Name)
            and owner.value.id == "client"
        ):
            assert owner.attr in RESOURCES, f"client.{owner.attr}"
            yield RESOURCES[owner.attr], node.func.attr, node
        elif isinstance(owner, ast.Name) and owner.id == "monitoring":
            yield DeploymentMonitoring, node.func.attr, node
        elif isinstance(owner, ast.Name) and owner.id == "client":
            is_async = "AsyncLumlClient(" in block
            yield AsyncLumlClient if is_async else LumlClient, node.func.attr, node


def _assert_keywords_accepted(method: Callable, call: ast.Call, name: str) -> None:
    parameters = inspect.signature(method).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
        return
    for keyword in call.keywords:
        if keyword.arg is not None:
            assert keyword.arg in parameters, f"{name}(... {keyword.arg}=)"


@pytest.mark.parametrize(("where", "block"), BLOCKS, ids=IDS)
def test_client_methods_and_keywords_exist(where: str, block: str) -> None:
    for owner, method_name, call in _client_calls(block):
        method = getattr(owner, method_name, None)
        assert method is not None, f"{owner.__name__}.{method_name}"
        _assert_keywords_accepted(method, call, f"{owner.__name__}.{method_name}")


def test_skill_calls_some_client_methods() -> None:
    calls = [call for _, block in BLOCKS for call in _client_calls(block)]
    assert len(calls) > 30


def test_client_defaults_are_settable() -> None:
    for name in ("organization", "orbit", "collection"):
        assert isinstance(getattr(LumlClient, name), property)
        assert getattr(LumlClient, name).fset is not None


def test_platform_reference_names_every_status_and_collection_type() -> None:
    from luml_api import ArtifactStatus, CollectionType

    text = (SKILL_DIR / "references/platform.md").read_text()
    for value in [*ArtifactStatus, *CollectionType]:
        assert f"`{value.value}`" in text, value.value
