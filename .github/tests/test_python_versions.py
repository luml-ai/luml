import re
import subprocess
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICES = (
    "backend",
    "satellite/kit",
    "satellite/implementations/docker",
    "satellite/implementations/kubernetes",
    "model_servers/default",
    "wasm/jupyter",
)
PUBLISHED_PACKAGES = {
    "sdk/python/sdk": "[sdk] tests-and-linters.yml",
    "sdk/python/api": "[api-client] tests-and-linters.yml",
    "lumlflow": "[lumlflow] tests-and-linters.yml",
    "prisma": "[prisma] tests-and-linters.yml",
    "extras/python/luml-mlflow": "[luml-mlflow] tests-and-linters.yml",
    "relay": "[relay] tests-and-linters.yml",
}


def load_toml(relative):
    return tomllib.loads((ROOT / relative).read_text())


def minimum_version(requires_python):
    major, minor = re.fullmatch(r">=(\d+)\.(\d+)", requires_python).groups()
    return int(major), int(minor)


def workflow_versions(name):
    text = (ROOT / ".github/workflows" / name).read_text()
    return re.findall(r"python-version:\s*['\"]?(\d+\.\d+)", text)


class PythonVersionTests(unittest.TestCase):
    def test_services_run_python_314(self):
        for package in SERVICES:
            project = load_toml(f"{package}/pyproject.toml")
            lock = load_toml(f"{package}/uv.lock")
            tools = project["tool"]
            with self.subTest(package=package):
                self.assertEqual(project["project"]["requires-python"], ">=3.14")
                self.assertEqual(lock["requires-python"], ">=3.14")
                self.assertEqual(tools["ruff"]["target-version"], "py314")
                if "python_version" in tools.get("mypy", {}):
                    self.assertEqual(tools["mypy"]["python_version"], "3.14")

    def test_images_run_python_314(self):
        dockerfiles = subprocess.check_output(
            ["git", "ls-files", "*Dockerfile"], cwd=ROOT, text=True
        ).splitlines()
        for relative in dockerfiles:
            text = (ROOT / relative).read_text()
            with self.subTest(file=relative):
                for version in re.findall(
                    r"^FROM python:(\d+\.\d+)", text, re.MULTILINE
                ):
                    self.assertEqual(version, "3.14")

    def test_published_packages_keep_supporting_python_312(self):
        for package, workflow in PUBLISHED_PACKAGES.items():
            project = load_toml(f"{package}/pyproject.toml")
            lock = load_toml(f"{package}/uv.lock")
            tools = project["tool"]
            minimum = minimum_version(project["project"]["requires-python"])
            dotted = "%d.%d" % minimum
            with self.subTest(package=package):
                self.assertLessEqual(minimum, (3, 12))
                self.assertEqual(minimum_version(lock["requires-python"]), minimum)
                self.assertEqual(tools["ruff"]["target-version"], "py%d%d" % minimum)
                if "python_version" in tools.get("mypy", {}):
                    self.assertEqual(tools["mypy"]["python_version"], dotted)
                self.assertTrue(workflow_versions(workflow))
                for version in workflow_versions(workflow):
                    self.assertEqual(version, dotted)


if __name__ == "__main__":
    unittest.main()
