"""acceptance checks for dependency locks and local development bindings."""

import ipaddress
import re
import shlex
import subprocess
import tomllib
import unittest
from pathlib import Path

import yaml
from test_release_gates import load

ROOT = Path(__file__).resolve().parents[2]


def project_file(relative):
    return tomllib.loads((ROOT / relative).read_text())


class DependencyHygieneTests(unittest.TestCase):
    def test_lumlflow_commits_a_complete_dependency_lock(self):
        lock = project_file("lumlflow/uv.lock")
        packages = {package["name"]: package for package in lock["package"]}
        for name in ("lumlflow", "luml-sdk", "luml-api", "pytest", "ruff", "pyarrow"):
            with self.subTest(package=name):
                self.assertIn(name, packages)
        self.assertTrue(packages["pyarrow"]["wheels"])
        self.assertNotIn(
            "uv.lock", (ROOT / "lumlflow/.gitignore").read_text().splitlines()
        )
        ignored = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", "lumlflow/uv.lock"],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(ignored.returncode, 1)

    def test_lumlflow_direct_dependencies_have_upper_bounds(self):
        project = project_file("lumlflow/pyproject.toml")
        groups = [project["project"]["dependencies"]]
        groups.extend(project["project"]["optional-dependencies"].values())
        groups.extend(project["dependency-groups"].values())
        for group in groups:
            for requirement in group:
                with self.subTest(requirement=requirement):
                    self.assertRegex(requirement, r"<\s*\d")

    def test_lumlflow_workflow_freezes_all_uv_commands(self):
        jobs = load("[lumlflow] tests-and-linters.yml")["jobs"]
        commands = []
        for name, job in jobs.items():
            for step in job["steps"]:
                for line in step.get("run", "").splitlines():
                    words = shlex.split(line)
                    if words[:2] in (["uv", "sync"], ["uv", "run"]):
                        commands.append(words)
                        with self.subTest(job=name, command=line):
                            self.assertIn("--frozen", words[2:])
        self.assertTrue(commands)

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
