"""acceptance checks for dependency locks and local development bindings."""

import ipaddress
import re
import tomllib
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def project_file(relative):
    return tomllib.loads((ROOT / relative).read_text())


class DependencyHygieneTests(unittest.TestCase):
    def test_development_ports_only_publish_on_loopback(self):
        for relative in ("backend/docker-compose.yml", "dev/docker-compose.yml"):
            config = yaml.safe_load((ROOT / relative).read_text())
            ports = [
                port
                for service in config["services"].values()
                for port in service.get("ports", [])
            ]
            self.assertTrue(ports)
            for port in ports:
                with self.subTest(file=relative, port=port):
                    if isinstance(port, dict):
                        host = port.get("host_ip", "0.0.0.0")
                    else:
                        parts = port.rsplit(":", 2)
                        self.assertEqual(
                            len(parts), 3, "loopback host must be explicit"
                        )
                        host = parts[0].strip("[]")
                    self.assertTrue(ipaddress.ip_address(host).is_loopback)

    def test_sdk_excludes_vulnerable_arrow_versions_and_locks_resolution(self):
        sdk = "sdk/python/sdk"
        project = project_file(f"{sdk}/pyproject.toml")
        for group, floor in (
            (project["project"]["optional-dependencies"]["datasets"], (17, 0, 0)),
            (project["dependency-groups"]["dev"], (23, 0, 1)),
        ):
            requirement = next(item for item in group if item.startswith("pyarrow"))
            minimum = re.search(r">=\s*(\d+\.\d+\.\d+)", requirement)
            self.assertIsNotNone(minimum)
            self.assertGreaterEqual(tuple(map(int, minimum[1].split("."))), floor)
        lock = project_file(f"{sdk}/uv.lock")
        arrow = next(p for p in lock["package"] if p["name"] == "pyarrow")
        self.assertGreaterEqual(
            tuple(map(int, arrow["version"].split("."))), (23, 0, 1)
        )
        self.assertTrue(arrow["wheels"])
        ignored = (ROOT / sdk / ".gitignore").read_text().splitlines()
        self.assertNotIn("uv.lock", ignored)

    def test_backend_locks_patched_starlette_and_opentelemetry(self):
        lock = project_file("backend/uv.lock")
        packages = {package["name"]: package for package in lock["package"]}
        self.assertGreaterEqual(
            tuple(map(int, packages["starlette"]["version"].split("."))), (1, 3, 1)
        )
        telemetry = [
            p for p in lock["package"] if p["name"].startswith("opentelemetry-")
        ]
        self.assertTrue(telemetry)
        for package in telemetry:
            with self.subTest(package=package["name"]):
                version = package["version"]
                if "b" in version:
                    self.assertGreaterEqual(
                        tuple(map(int, re.findall(r"\d+", version))), (0, 66, 1)
                    )
                else:
                    self.assertGreaterEqual(
                        tuple(map(int, version.split("."))), (1, 45, 1)
                    )

    def test_jupyter_locks_patched_lite_packages(self):
        lock = project_file("wasm/jupyter/uv.lock")
        packages = {package["name"]: package for package in lock["package"]}
        for name in ("jupyterlite", "jupyterlite-core"):
            with self.subTest(package=name):
                self.assertGreaterEqual(
                    tuple(map(int, packages[name]["version"].split("."))), (0, 8, 4)
                )

    def test_jupyter_image_uses_complete_lock_with_patched_starlette(self):
        jupyter = "wasm/jupyter"
        lock = project_file(f"{jupyter}/uv.lock")
        packages = {package["name"]: package for package in lock["package"]}
        self.assertGreaterEqual(
            tuple(map(int, packages["starlette"]["version"].split("."))), (1, 3, 1)
        )
        for name in ("fastapi", "uvicorn", "jupyterlite", "jupyterlite-pyodide-kernel"):
            self.assertIn(name, packages)
        dockerfile = (ROOT / jupyter / "Dockerfile").read_text()
        self.assertRegex(dockerfile, r"COPY [^\n]*pyproject\.toml[^\n]*uv\.lock")
        self.assertRegex(dockerfile, r"RUN uv sync --frozen --no-dev")
        self.assertNotIn("pip install", dockerfile)


if __name__ == "__main__":
    unittest.main()
