"""acceptance checks for the native Python interpreter baseline."""

import re
import subprocess
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BROWSER_PACKAGES = {
    "wasm/packages/dfs_webworker",
    "wasm/packages/promptopt",
}


class PythonVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = subprocess.check_output(
            ["git", "ls-files"], cwd=ROOT, text=True
        ).splitlines()

    def test_native_packages_and_locks_require_python_314(self):
        for relative in self.files:
            path = Path(relative)
            if path.name not in {"pyproject.toml", "uv.lock"}:
                continue
            if str(path.parent) in BROWSER_PACKAGES:
                continue
            config = tomllib.loads((ROOT / path).read_text())
            with self.subTest(file=relative):
                if path.name == "uv.lock":
                    self.assertEqual(config["requires-python"], ">=3.14")
                    continue
                self.assertEqual(config["project"]["requires-python"], ">=3.14")
                tools = config.get("tool", {})
                if "target-version" in tools.get("ruff", {}):
                    self.assertEqual(tools["ruff"]["target-version"], "py314")
                if "python_version" in tools.get("mypy", {}):
                    self.assertEqual(tools["mypy"]["python_version"], "3.14")

    def test_interpreter_pins_use_python_314(self):
        for relative in self.files:
            path = ROOT / relative
            with self.subTest(file=relative):
                if path.name == ".python-version":
                    self.assertEqual(path.read_text().strip(), "3.14")
                if path.name == "Dockerfile":
                    for version in re.findall(
                        r"^FROM python:(\d+\.\d+)", path.read_text(), re.MULTILINE
                    ):
                        self.assertEqual(version, "3.14")
                if relative.startswith(".github/workflows/"):
                    for version in re.findall(
                        r"python-version:\s*['\"]?(\d+\.\d+)", path.read_text()
                    ):
                        self.assertEqual(version, "3.14")

    def test_browser_packages_keep_compatible_metadata(self):
        for relative in BROWSER_PACKAGES:
            config = tomllib.loads((ROOT / relative / "pyproject.toml").read_text())
            with self.subTest(package=relative):
                self.assertEqual(config["project"]["requires-python"], ">=3.10")
        workflow = (
            ROOT / ".github/workflows/[lumlflow] tests-and-linters.yml"
        ).read_text()
        self.assertIn("--python 3.10 --no-project", workflow)
        project = tomllib.loads((ROOT / "lumlflow/pyproject.toml").read_text())
        targets = project["tool"]["ruff"]["per-file-target-version"]
        for pattern in (
            "lumlflow_kernel/**/*.py",
            "tests/unit/kernel/**/*.py",
            "tests/integration/kernel/**/*.py",
        ):
            self.assertEqual(targets[pattern], "py310")

    def test_release_smoke_check_and_docs_generator_use_python_314(self):
        workflow = (ROOT / ".github/workflows/publish-sdk-python.yml").read_text()
        self.assertIn("uv venv --python 3.14", workflow)
        self.assertNotIn("uv venv --python 3.12", workflow)
        generator = (ROOT / "docs/generate_docs.py").read_text()
        self.assertIn('# requires-python = ">=3.14"', generator)

    def test_integration_tutorials_document_python_314(self):
        for tutorial in ("sdk", "mlflow", "langgraph"):
            text = (
                ROOT / f"docs/docs/guides/Integrations/{tutorial}_tutorial.md"
            ).read_text()
            with self.subTest(tutorial=tutorial):
                self.assertIn("Python 3.14 or later", text)
                self.assertNotIn("Python 3.12 or later", text)


if __name__ == "__main__":
    unittest.main()
