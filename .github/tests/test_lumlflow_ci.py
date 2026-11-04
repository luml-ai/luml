"""acceptance checks for lumlflow CI coverage and blocking checks.

run with: uv run --with pyyaml python -m unittest discover -s .github/tests
"""

import fnmatch
import unittest

from test_release_gates import load


class LumlflowCITests(unittest.TestCase):
    def test_shared_sources_and_dependency_manifests_trigger_checks(self):
        workflow = load("[lumlflow] tests-and-linters.yml")
        for event in ("push", "pull_request"):
            paths = workflow["on"][event]["paths"]
            for changed in (
                "lumlflow/frontend/src/App.vue",
                "extras/js/packages/attachments/src/index.ts",
                "extras/js/packages/experiments/src/index.ts",
                "extras/js/shared-config.ts",
                "extras/js/packages/new-package/src/index.ts",
                "package.json",
                "package-lock.json",
            ):
                with self.subTest(event=event, changed=changed):
                    self.assertTrue(
                        any(fnmatch.fnmatchcase(changed, path) for path in paths)
                    )

    def test_eslint_checks_without_autofix_and_blocks_on_errors(self):
        job = load("[lumlflow] tests-and-linters.yml")["jobs"]["lint"]
        self.assertNotIn("continue-on-error", job)
        self.assertNotIn("if", job)
        lint_steps = [step for step in job["steps"] if step.get("name") == "ESLint"]
        self.assertEqual(len(lint_steps), 1)
        self.assertEqual(lint_steps[0]["working-directory"], "lumlflow/frontend")
        self.assertEqual(lint_steps[0]["run"], "npx eslint .")
        self.assertNotIn("continue-on-error", lint_steps[0])
        self.assertNotIn("if", lint_steps[0])

    def test_jobs_install_from_the_lockfile_without_extra_installs(self):
        jobs = load("[lumlflow] tests-and-linters.yml")["jobs"]
        node_jobs = {
            name: job
            for name, job in jobs.items()
            if any(
                step.get("uses", "").startswith("actions/setup-node")
                for step in job["steps"]
            )
        }
        self.assertLessEqual({"lint", "unit"}, set(node_jobs))
        for name, job in jobs.items():
            commands = [step.get("run", "") for step in job["steps"]]
            with self.subTest(job=name):
                self.assertFalse(any("npm install" in command for command in commands))
                if name in node_jobs:
                    self.assertTrue(
                        any(command.startswith("npm ci") for command in commands)
                    )
        unit_commands = [step.get("run", "") for step in jobs["unit"]["steps"]]
        self.assertIn("npm ci --include=optional", unit_commands)


if __name__ == "__main__":
    unittest.main()
