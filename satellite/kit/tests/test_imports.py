import subprocess
import sys

import httpx
import pytest
import respx


def test_core_imports_without_serving_or_monitoring_extras() -> None:
    script = r"""
import builtins
import importlib
import pkgutil

original_import = builtins.__import__

def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "fastapi" or name.startswith("fastapi."):
        raise AssertionError(f"unexpected optional import: {name}")
    if name == "opentelemetry" or name.startswith("opentelemetry."):
        raise AssertionError(f"unexpected optional import: {name}")
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = blocked_import
package = importlib.import_module("luml_satellite")
importlib.import_module("luml_satellite.convergence")
importlib.import_module("luml_satellite.convergence.polling")
importlib.import_module("luml_satellite.convergence.serving")
for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
    importlib.import_module(module.name)
"""
    subprocess.run([sys.executable, "-c", script], check=True)


@pytest.mark.asyncio
async def test_model_server_mock_fixture(mock_model_server: respx.MockRouter) -> None:
    async with httpx.AsyncClient() as client:
        health = await client.get("http://sat-fixture:8000/healthz")
        manifest = await client.get("http://sat-fixture:8000/manifest")
        openapi = await client.get("http://sat-fixture:8000/openapi.json")
        compute = await client.post("http://sat-fixture:8000/compute", json={"value": 1})

    assert health.json() == {"status": "healthy"}
    assert manifest.json() == {"name": "test-model", "version": "1.0"}
    assert openapi.json() == {"openapi": "3.0.0", "paths": {}}
    assert compute.json() == {"prediction": 42}
    mock_model_server.assert_all_called()
