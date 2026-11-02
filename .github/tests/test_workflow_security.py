"""acceptance checks for github actions supply chain hardening.

run with: uv run --with pyyaml python -m unittest discover -s .github/tests
"""

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"


class WorkflowSecurityTests(unittest.TestCase):
    def test_remote_actions_and_reusable_workflows_use_full_commit_shas(self):
        for path in WORKFLOWS.glob("*.y*ml"):
            workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            for name, job in workflow["jobs"].items():
                for action in [job, *job.get("steps", [])]:
                    if "uses" not in action:
                        continue
                    ref = action["uses"]
                    with self.subTest(workflow=path.name, job=name, uses=ref):
                        if ref.startswith("./"):
                            self.assertTrue((ROOT / ref).is_file())
                        else:
                            self.assertRegex(ref, r"^[^@\s]+@[0-9a-f]{40}$")

    def test_workflows_default_to_read_only_contents(self):
        paths = list(WORKFLOWS.glob("*.y*ml"))
        self.assertTrue(paths)
        for path in paths:
            workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            with self.subTest(workflow=path.name):
                self.assertEqual(workflow.get("permissions"), {"contents": "read"})

    def test_registry_publish_jobs_keep_their_required_permissions(self):
        paths = [*WORKFLOWS.glob("publish-*-image.yml")]
        paths.append(WORKFLOWS / "publish-kubernetes-satellite-chart.yml")
        for path in paths:
            workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            job = "publish-chart" if "chart" in path.name else "push-image"
            with self.subTest(workflow=path.name, job=job):
                self.assertEqual(
                    workflow["jobs"][job]["permissions"],
                    {"contents": "read", "packages": "write"},
                )

    def test_dependabot_updates_github_actions(self):
        path = ROOT / ".github/dependabot.yml"
        self.assertTrue(path.is_file())
        config = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(config["version"], "2")
        updates = [
            update
            for update in config["updates"]
            if update["package-ecosystem"] == "github-actions"
        ]
        self.assertTrue(updates)
        self.assertTrue(any(update["directory"] == "/" for update in updates))
        for update in updates:
            self.assertIn(
                update["schedule"]["interval"], {"daily", "weekly", "monthly"}
            )

    def test_migrations_keep_dependencies_locked_and_dsn_scoped(self):
        workflow = yaml.load(
            (WORKFLOWS / "deploy-backend.yml").read_text(), Loader=yaml.BaseLoader
        )
        migrate = workflow["jobs"]["migrate"]
        self.assertNotIn("POSTGRESQL_DSN", workflow.get("env", {}))
        self.assertNotIn("POSTGRESQL_DSN", migrate.get("env", {}))
        steps = {step.get("name"): step for step in migrate["steps"]}
        install = steps["Install dependencies"]
        migrations = steps["Run migrations"]
        for step in (install, migrations):
            self.assertEqual(step["if"], "vars.MIGRATIONS_IN_APP_PLATFORM != 'true'")
        self.assertNotIn("POSTGRESQL_DSN", install.get("env", {}))
        self.assertIn("POSTGRESQL_DSN", migrations["env"])
        self.assertIn("uv sync --locked", install["run"])
        self.assertIn("uv run --locked alembic upgrade head", migrations["run"])
        self.assertIn("uv run --locked alembic current", migrations["run"])


if __name__ == "__main__":
    unittest.main()
