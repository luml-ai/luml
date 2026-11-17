"""acceptance checks for github actions supply chain hardening.

run with: uv run --with pyyaml python -m unittest discover -s .github/tests
"""

import re
import subprocess
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
                self.assertIn(workflow.get("permissions"), ({}, {"contents": "read"}))

    def test_registry_publish_jobs_keep_their_required_permissions(self):
        jobs = {
            path.name: "push-image" for path in WORKFLOWS.glob("publish-*-image*.yml")
        }
        jobs["publish-kubernetes-satellite-chart.yml"] = "publish-chart"
        jobs["promote-images.yml"] = "promote"
        self.assertIn("publish-satellite-images.yml", jobs)
        for name, job in jobs.items():
            workflow = yaml.load((WORKFLOWS / name).read_text(), Loader=yaml.BaseLoader)
            with self.subTest(workflow=name, job=job):
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

    def test_dependabot_updates_every_directory_with_a_dockerfile(self):
        config = yaml.load(
            (ROOT / ".github/dependabot.yml").read_text(), Loader=yaml.BaseLoader
        )
        covered = {
            directory
            for update in config["updates"]
            if update["package-ecosystem"] == "docker"
            for directory in update.get("directories", [update.get("directory")])
        }
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        dockerfiles = [
            Path(name)
            for name in tracked
            if re.search("dockerfile|containerfile", Path(name).name, re.IGNORECASE)
        ]
        self.assertTrue(dockerfiles)
        for dockerfile in dockerfiles:
            with self.subTest(dockerfile=str(dockerfile)):
                self.assertIn(f"/{dockerfile.parent.as_posix()}", covered)

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
