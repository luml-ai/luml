import subprocess
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = {
    "backend": ("backend", ["luml", "utils", "tests"]),
    "extras/python/luml-mlflow": ("luml-mlflow", ["luml_mlflow"]),
    "lumlflow": ("lumlflow", ["lumlflow/flow", "lumlflow_kernel", "lumlflow_typing"]),
    "model_servers/default": (
        "model-server",
        [
            "clients",
            "handlers",
            "services",
            "utils",
            "compute_mode.py",
            "conda_manager.py",
            "conda_worker.py",
            "main.py",
            "openapi_generator.py",
            "server.py",
            "telemetry.py",
            "tests",
        ],
    ),
    "prisma": ("prisma", ["src"]),
    "relay": ("relay", ["luml_relay", "tests"]),
    "satellite/kit": ("satellite-kit", ["luml_satellite", "tests"]),
    "satellite/implementations/docker": (
        "satellite-docker",
        ["luml_satellite_docker", "tests"],
    ),
    "satellite/implementations/kubernetes": (
        "satellite-kubernetes",
        ["luml_satellite_kubernetes", "tests", "e2e"],
    ),
    "sdk/python/api": ("api-client", ["luml_api"]),
    "sdk/python/sdk": ("sdk", ["luml"]),
}


class PythonTypeCheckingTests(unittest.TestCase):
    def test_projects_share_a_locked_checker_and_fail_on_warnings(self):
        pins = set()
        for package, (workflow, targets) in PACKAGES.items():
            project = tomllib.loads((ROOT / package / "pyproject.toml").read_text())
            lock = tomllib.loads((ROOT / package / "uv.lock").read_text())
            dependencies = project["dependency-groups"]["dev"]
            checker = [item for item in dependencies if item.startswith("ty==")]
            with self.subTest(package=package):
                self.assertEqual(len(checker), 1)
                pins.update(checker)
                version = checker[0].removeprefix("ty==")
                self.assertRegex(version, r"^\d+\.\d+\.\d+$")
                self.assertEqual(
                    [
                        item["version"]
                        for item in lock["package"]
                        if item["name"] == "ty"
                    ],
                    [version],
                )
                self.assertEqual(project["tool"]["ty"]["src"]["include"], targets)
                self.assertTrue(project["tool"]["ty"]["terminal"]["error-on-warning"])
                self.assertNotIn("rules", project["tool"]["ty"])
                workflow_text = (
                    ROOT / ".github/workflows" / f"[{workflow}] tests-and-linters.yml"
                ).read_text()
                self.assertIn("run: uv run --frozen ty check\n", workflow_text)
        self.assertEqual(len(pins), 1)

    def test_source_suppressions_name_checker_rules(self):
        files = subprocess.check_output(
            ["git", "ls-files", "*.py"], cwd=ROOT, text=True
        ).splitlines()
        for file in files:
            if not any(file.startswith(package + "/") for package in PACKAGES):
                continue
            for line_number, line in enumerate(
                (ROOT / file).read_text().splitlines(), 1
            ):
                with self.subTest(file=file, line=line_number):
                    self.assertNotRegex(line, r"#\s*type:\s*ignore")
                    if "# ty: ignore" in line:
                        self.assertRegex(line, r"# ty: ignore\[[a-z-]+(?:, [a-z-]+)*\]")

    def test_generated_flow_state_is_excluded(self):
        project = tomllib.loads((ROOT / "lumlflow/pyproject.toml").read_text())
        self.assertIn("**/.flow/**", project["tool"]["ty"]["src"]["exclude"])

    def test_tracking_plugin_enforces_annotations(self):
        project = tomllib.loads(
            (ROOT / "extras/python/luml-mlflow/pyproject.toml").read_text()
        )
        self.assertIn("ANN", project["tool"]["ruff"]["lint"]["select"])


if __name__ == "__main__":
    unittest.main()
