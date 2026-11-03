"""acceptance checks for frontend CI coverage and blocking checks.

run with: uv run --with pyyaml python -m unittest discover -s .github/tests
"""

import fnmatch
import unittest

from test_release_gates import load


class FrontendCITests(unittest.TestCase):
    def test_shared_sources_and_dependency_manifests_trigger_checks_and_deploy(self):
        workflows = {
            "[frontend] tests-and-linters.yml": ("push", "pull_request"),
            "deploy-frontend.yml": ("push",),
        }
        for name, events in workflows.items():
            for event in events:
                paths = load(name)["on"][event]["paths"]
                for changed in (
                    "frontend/src/App.vue",
                    "extras/js/packages/attachments/src/index.ts",
                    "extras/js/packages/experiments/src/index.ts",
                    "extras/js/shared-config.ts",
                    "extras/js/packages/new-package/src/index.ts",
                    "package.json",
                    "package-lock.json",
                ):
                    with self.subTest(workflow=name, event=event, changed=changed):
                        self.assertTrue(
                            any(fnmatch.fnmatchcase(changed, path) for path in paths)
                        )

    def test_flow_only_changes_do_not_trigger_frontend_deploy(self):
        paths = load("deploy-frontend.yml")["on"]["push"]["paths"]
        self.assertFalse(
            any(
                fnmatch.fnmatchcase("lumlflow/frontend/src/App.vue", path)
                for path in paths
            )
        )

    def test_eslint_failure_blocks_the_job(self):
        job = load("[frontend] tests-and-linters.yml")["jobs"]["lint"]
        self.assertNotIn("continue-on-error", job)
        self.assertNotIn("if", job)
        lint_steps = [
            step for step in job["steps"] if step.get("run") == "npm run lint"
        ]
        self.assertEqual(len(lint_steps), 1)
        self.assertNotIn("continue-on-error", lint_steps[0])
        self.assertNotIn("if", lint_steps[0])

    def test_experiments_tests_run_as_a_blocking_frontend_check(self):
        job = load("[frontend] tests-and-linters.yml")["jobs"]["unit"]
        self.assertNotIn("continue-on-error", job)
        self.assertNotIn("if", job)
        test_steps = [
            step
            for step in job["steps"]
            if "npm run test:ci --workspace=@luml/experiments"
            in step.get("run", "")
        ]
        self.assertEqual(len(test_steps), 1)
        self.assertNotIn("continue-on-error", test_steps[0])
        self.assertNotIn("if", test_steps[0])

    def test_test_jobs_use_optional_dependencies_without_mutating_the_lockfile(self):
        jobs = load("[frontend] tests-and-linters.yml")["jobs"]
        for name in ("unit", "integration"):
            commands = [step.get("run", "") for step in jobs[name]["steps"]]
            with self.subTest(job=name):
                self.assertIn("npm ci --include=optional", commands)
                self.assertFalse(any("npm install" in command for command in commands))


if __name__ == "__main__":
    unittest.main()
