"""acceptance checks for frontend CI coverage and blocking checks.

run with: uv run --with pyyaml python -m unittest discover -s .github/tests
"""

import fnmatch
import json
import re
import unittest

from test_release_gates import ROOT, WORKFLOWS, load

PLAYWRIGHT_IMAGE = r"mcr\.microsoft\.com/playwright:v(?P<version>\d+\.\d+\.\d+)-noble@sha256:[0-9a-f]{64}"


class FrontendCITests(unittest.TestCase):
    def test_shared_sources_and_dependency_manifests_trigger_checks_and_deploy(self):
        workflows = {
            "[frontend] tests-and-linters.yml": ("pull_request",),
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

    def test_workspace_package_checks_run_once_outside_the_frontend_suite(self):
        commands = "\n".join(
            step.get("run", "")
            for job in load("[frontend] tests-and-linters.yml")["jobs"].values()
            for step in job["steps"]
        )
        self.assertNotIn("test:ci --workspace=", commands)
        job = load("[extras-js] tests-and-linters.yml")["jobs"]["checks"]
        self.assertEqual(
            set(job["strategy"]["matrix"]["package"]), {"attachments", "experiments"}
        )

    def test_extras_checks_trigger_on_workspace_sources_and_manifests(self):
        workflow = load("[extras-js] tests-and-linters.yml")
        for event in ("pull_request",):
            paths = workflow["on"][event]["paths"]
            for changed in (
                "extras/js/packages/attachments/src/index.ts",
                "extras/js/packages/experiments/src/index.ts",
                "extras/js/packages/new-package/src/index.ts",
                "package.json",
                "package-lock.json",
            ):
                with self.subTest(event=event, changed=changed):
                    self.assertTrue(
                        any(fnmatch.fnmatchcase(changed, path) for path in paths)
                    )

    def test_extras_eslint_does_not_autofix_in_ci(self):
        steps = load("[extras-js] tests-and-linters.yml")["jobs"]["checks"]["steps"]
        lint_steps = [step for step in steps if step.get("name") == "ESLint"]
        self.assertEqual(len(lint_steps), 1)
        self.assertNotIn("--fix", lint_steps[0]["run"])
        self.assertNotIn("npm run lint", lint_steps[0]["run"])
        self.assertNotIn("continue-on-error", lint_steps[0])

    def test_browser_test_jobs_run_in_the_playwright_image(self):
        # The full image holds chromium, firefox and webkit with their system
        # packages, so these jobs neither install browsers nor touch apt.
        for workflow, name in (
            ("[frontend] tests-and-linters.yml", "integration"),
            ("[extras-js] tests-and-linters.yml", "checks"),
        ):
            job = load(workflow)["jobs"][name]
            commands = [step.get("run", "") for step in job["steps"]]
            with self.subTest(workflow=workflow, job=name):
                self.assertRegex(job["container"]["image"], f"^{PLAYWRIGHT_IMAGE}$")
                self.assertIn("--user 1001", job["container"]["options"])
                self.assertIn("--ipc=host", job["container"]["options"])
                self.assertFalse(any("playwright install" in c for c in commands))

    def test_playwright_images_match_the_locked_playwright_version(self):
        lock = json.loads((ROOT / "package-lock.json").read_text())["packages"]
        locked = {
            lock[f"node_modules/{package}"]["version"]
            for package in ("@playwright/test", "playwright", "playwright-core")
        }
        self.assertEqual(len(locked), 1)
        found = 0
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for name, job in load(path.name)["jobs"].items():
                image = job.get("container", {}).get("image", "")
                if "playwright" not in image:
                    continue
                found += 1
                with self.subTest(workflow=path.name, job=name):
                    match = re.fullmatch(PLAYWRIGHT_IMAGE, image)
                    self.assertIsNotNone(match, image)
                    self.assertEqual({match["version"]}, locked)
        self.assertGreaterEqual(found, 2)

    def test_jobs_that_install_playwright_browsers_pin_the_runner_image(self):
        # Playwright ships browser builds per Ubuntu release, so a moving image
        # breaks the install on the first browser cache miss.
        found = 0
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for name, job in load(path.name)["jobs"].items():
                commands = [step.get("run", "") for step in job.get("steps", [])]
                if not any("playwright install" in command for command in commands):
                    continue
                found += 1
                with self.subTest(workflow=path.name, job=name):
                    self.assertRegex(job["runs-on"], r"^ubuntu-\d+\.\d+$")
        self.assertGreaterEqual(found, 1)

    def test_test_jobs_use_optional_dependencies_without_mutating_the_lockfile(self):
        jobs = {
            ("[frontend] tests-and-linters.yml", "unit"),
            ("[frontend] tests-and-linters.yml", "integration"),
            ("[extras-js] tests-and-linters.yml", "checks"),
        }
        for workflow, name in jobs:
            steps = load(workflow)["jobs"][name]["steps"]
            commands = [step.get("run", "") for step in steps]
            with self.subTest(workflow=workflow, job=name):
                self.assertIn("npm ci --include=optional", commands)
                self.assertFalse(any("npm install" in command for command in commands))


if __name__ == "__main__":
    unittest.main()
