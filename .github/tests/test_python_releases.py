"""acceptance checks for locked, test-gated Python package releases."""

import re
import subprocess
import unittest

from test_release_gates import ROOT, WORKFLOWS, dependencies, load

PACKAGES = {
    "sdk-python/api/v": (
        "sdk/python/api",
        {"api-tests": "[api-client] tests-and-linters.yml"},
    ),
    "sdk-python/sdk/v": (
        "sdk/python/sdk",
        {"sdk-tests": "[sdk] tests.yml", "sdk-linters": "[sdk] linters.yml"},
    ),
    "lumlflow/v": (
        "lumlflow",
        {
            "flow-tests": "[lumlflow-python] tests-and-linters.yml",
            "flow-ui-tests": "[lumlflow] tests-and-linters.yml",
        },
    ),
    "luml-prisma/v": ("prisma", {"prisma-tests": "[prisma] tests-and-linters.yml"}),
    "luml-mlflow/v": (
        "extras/python/luml-mlflow",
        {"mlflow-tests": "[luml-mlflow] tests-and-linters.yml"},
    ),
    "luml-relay/v": ("relay", {"relay-tests": "[relay] tests-and-linters.yml"}),
}


def condition_matches(condition, tag, results):
    expression = condition.removeprefix("${{").removesuffix("}}").strip()
    expression = expression.replace("!cancelled()", "True")
    expression = expression.replace("&&", " and ").replace("||", " or ")
    expression = expression.replace("github.ref_name", repr(tag))
    expression = re.sub(
        r"needs\.([\w-]+)\.result", lambda match: repr(results[match[1]]), expression
    )
    return eval(expression, {"__builtins__": {}, "startsWith": str.startswith})


class PythonReleaseTests(unittest.TestCase):
    def test_published_packages_have_committed_nonignored_lockfiles(self):
        for directory, _ in PACKAGES.values():
            lock = f"{directory}/uv.lock"
            with self.subTest(lock=lock):
                self.assertTrue((ROOT / lock).is_file())
                tracked = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", lock],
                    cwd=ROOT,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(tracked.returncode, 0)
                ignored = subprocess.run(
                    ["git", "check-ignore", "--no-index", lock],
                    cwd=ROOT,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(ignored.returncode, 1)

    def test_workflows_never_resolve_project_dependencies_implicitly(self):
        for path in WORKFLOWS.glob("*.yml"):
            for line in path.read_text().splitlines():
                if "uv sync" in line or (
                    "uv run" in line and "--with pyyaml" not in line
                ):
                    with self.subTest(workflow=path.name, command=line):
                        self.assertIn("--locked", line)
                        self.assertNotIn("--frozen", line)

    def test_package_suites_are_reusable_and_run_the_real_tests(self):
        jobs = load("publish-sdk-python.yml")["jobs"]
        required = set()
        for prefix, (directory, gates) in PACKAGES.items():
            for gate, suite in gates.items():
                required.add(gate)
                with self.subTest(package=directory, gate=gate):
                    self.assertEqual(jobs[gate]["uses"], f"./.github/workflows/{suite}")
                    self.assertNotIn("continue-on-error", jobs[gate])
                    self.assertTrue(
                        condition_matches(jobs[gate]["if"], prefix + "1.2.3", {})
                    )
                    self.assertFalse(
                        condition_matches(jobs[gate]["if"], "unrelated/v1.2.3", {})
                    )
                    workflow = load(suite)
                    self.assertIn("workflow_call", workflow["on"])
                    commands = "\n".join(
                        step.get("run", "")
                        for job in workflow["jobs"].values()
                        for step in job["steps"]
                    )
                    if gate == "flow-ui-tests":
                        self.assertIn("npm run test:ci", commands)
                    elif gate != "sdk-linters":
                        self.assertIn("pytest", commands)
                    for job in workflow["jobs"].values():
                        self.assertNotIn("if", job)
                        self.assertNotIn("continue-on-error", job)
                        for step in job["steps"]:
                            if "pytest" in step.get("run", ""):
                                self.assertNotIn("if", step)
                                self.assertNotIn("continue-on-error", step)
                            if step.get("uses", "").startswith("actions/checkout@"):
                                self.assertNotIn("ref", step.get("with", {}))
        self.assertTrue(required <= dependencies(jobs, "publish"))

    def test_failed_cancelled_or_skipped_package_checks_block_publish(self):
        jobs = load("publish-sdk-python.yml")["jobs"]
        condition = jobs["publish"]["if"]
        for prefix, (_, gates) in PACKAGES.items():
            tag = prefix + "1.2.3"
            results = {name: "skipped" for name in dependencies(jobs, "publish")}
            results.update({gate: "success" for gate in gates})
            with self.subTest(tag=tag):
                self.assertTrue(condition_matches(condition, tag, results))
                for gate in gates:
                    for status in ("failure", "cancelled", "skipped"):
                        self.assertFalse(
                            condition_matches(condition, tag, {**results, gate: status})
                        )
        self.assertFalse(condition_matches(condition, "unrelated/v1.2.3", results))
        self.assertIn("!cancelled()", condition)

    def test_publish_validates_lock_before_rewriting_version(self):
        steps = load("publish-sdk-python.yml")["jobs"]["publish"]["steps"]
        sync = next(
            i
            for i, step in enumerate(steps)
            if "uv sync --locked" in step.get("run", "")
        )
        version = next(
            i for i, step in enumerate(steps) if "sed -i" in step.get("run", "")
        )
        build = next(
            i for i, step in enumerate(steps) if "uv build" in step.get("run", "")
        )
        self.assertLess(sync, version)
        self.assertLess(version, build)
        self.assertFalse(any("uv lock" in step.get("run", "") for step in steps))
        for step in steps:
            if step.get("uses", "").startswith("actions/checkout@"):
                self.assertNotIn("ref", step.get("with", {}))


if __name__ == "__main__":
    unittest.main()
