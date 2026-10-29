"""acceptance checks for test-gated deployments and image publishing.

run with: uv run --with pyyaml python -m unittest discover -s .github/tests
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
BRANCHES = {"main", "staging", "production"}
RELEASES = {
    "deploy-backend.yml": {"tests": "[backend] tests-and-linters.yml"},
    "deploy-frontend.yml": {
        "tests": "[frontend] tests-and-linters.yml",
        "flow-tests": "[lumlflow] tests-and-linters.yml",
    },
    "deploy-docs.yml": {"tests": None},
    "publish-satellite-agent-image.yml": {
        "tests": "[satellite-docker] tests-and-linters.yml",
        "kit-tests": "[satellite-kit] tests-and-linters.yml",
    },
    "publish-kubernetes-satellite-image.yml": {
        "tests": "[satellite-kubernetes] tests-and-linters.yml",
        "kit-tests": "[satellite-kit] tests-and-linters.yml",
    },
    "publish-model-server-image.yml": {"tests": "[model-server] tests-and-linters.yml"},
    "publish-monitoring-image.yml": {
        "tests": "[satellite-kit] tests-and-linters.yml",
        "ui-tests": "[satellite-monitoring-ui] tests-and-linters.yml",
    },
    "publish-relay-image.yml": {"tests": "[relay] tests-and-linters.yml"},
    "publish-serving-image.yml": {"tests": "[satellite-kit] tests-and-linters.yml"},
}
IMAGE_TAGS = {
    "publish-satellite-agent-image.yml": "satellite/agent/v*",
    "publish-kubernetes-satellite-image.yml": "satellite/kubernetes/v*",
    "publish-model-server-image.yml": "satellite/model-server/v*",
    "publish-monitoring-image.yml": "satellite/monitoring/v*",
    "publish-serving-image.yml": "satellite/serving/v*",
    "publish-relay-image.yml": "luml-relay/image/v*",
}
RELEASE_COVERED_SUITES = {
    "[backend] tests-and-linters.yml",
    "[satellite-kit] tests-and-linters.yml",
}
SUITE_TESTS = {
    "[backend] tests-and-linters.yml": (
        "pytest tests/unit",
        "pytest tests/integration",
    ),
    "[frontend] tests-and-linters.yml": ("npm run test:ci", "npm run test:integration"),
    "[lumlflow] tests-and-linters.yml": ("npm run test:ci", "vite build"),
    "[satellite-monitoring-ui] tests-and-linters.yml": ("npm test", "npm run build"),
}


def load(name):
    return yaml.load((WORKFLOWS / name).read_text(), Loader=yaml.BaseLoader)


def dependencies(jobs, name):
    needs = jobs[name].get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    return set(needs)


def ancestors(jobs, name):
    result = dependencies(jobs, name)
    for parent in tuple(result):
        result |= ancestors(jobs, parent)
    return result


class ReleaseGateTests(unittest.TestCase):
    def test_checks_run_on_all_release_branches(self):
        paths = list(WORKFLOWS.glob("*tests-and-linters.yml"))
        paths.append(WORKFLOWS / "[satellite-kubernetes] end-to-end.yml")
        paths.append(WORKFLOWS / "[sdk] tests.yml")
        paths.append(WORKFLOWS / "[sdk] linters.yml")
        for path in paths:
            workflow = load(path.name)
            with self.subTest(workflow=path.name, event="pull_request"):
                self.assertEqual(
                    set(workflow["on"]["pull_request"]["branches"]), BRANCHES
                )
            with self.subTest(workflow=path.name, event="push"):
                if path.name in RELEASE_COVERED_SUITES:
                    self.assertNotIn("push", workflow["on"])
                else:
                    self.assertEqual(set(workflow["on"]["push"]["branches"]), BRANCHES)

    def test_release_covered_suites_are_gates_with_matching_paths(self):
        callers = {}
        for name, required in RELEASES.items():
            for suite in required.values():
                if suite:
                    callers.setdefault(suite, []).append(name)
        for suite in RELEASE_COVERED_SUITES:
            with self.subTest(suite=suite):
                self.assertIn(suite, callers)
                suite_paths = set(load(suite)["on"]["pull_request"]["paths"])
                suite_paths -= {
                    path for path in suite_paths if path.startswith(".github/")
                }
                covered = set()
                for name in callers[suite]:
                    covered |= set(load(name)["on"]["push"]["paths"])
                self.assertTrue(suite_paths <= covered, suite_paths - covered)

    def test_releases_require_the_relevant_checks(self):
        for name, required in RELEASES.items():
            jobs = load(name)["jobs"]
            with self.subTest(workflow=name):
                for gate, suite in required.items():
                    self.assertIn(gate, jobs)
                    self.assertNotIn("if", jobs[gate])
                    self.assertNotIn("continue-on-error", jobs[gate])
                    if suite:
                        self.assertEqual(
                            jobs[gate]["uses"], f"./.github/workflows/{suite}"
                        )
                        self.assertIn("workflow_call", load(suite)["on"])
                        commands = "\n".join(
                            step.get("run", "")
                            for check in load(suite)["jobs"].values()
                            for step in check["steps"]
                        )
                        for command in SUITE_TESTS.get(suite, ("uv run pytest",)):
                            self.assertIn(command, commands)
                        for check in load(suite)["jobs"].values():
                            self.assertNotIn("if", check)
                            self.assertNotIn("continue-on-error", check)
                            for step in check["steps"]:
                                if any(
                                    command in step.get("run", "")
                                    for command in (
                                        "pytest",
                                        "npm run test",
                                        "npm run build",
                                        "vite build",
                                    )
                                ):
                                    self.assertNotIn("if", step)
                                    self.assertNotIn("continue-on-error", step)
                                if step.get("uses", "").startswith("actions/checkout@"):
                                    self.assertNotIn("ref", step.get("with", {}))
                mutations = {"deploy", "migrate"} & jobs.keys()
                mutations |= {"push-image"} & jobs.keys()
                self.assertTrue(mutations)
                for mutation in mutations:
                    self.assertTrue(set(required) <= ancestors(jobs, mutation))

    def test_failed_cancelled_and_skipped_checks_cannot_release(self):
        # github skips jobs when any needed job did not succeed, unless if overrides it
        for name, required in RELEASES.items():
            jobs = load(name)["jobs"]
            for mutation in {"deploy", "migrate", "push-image"} & jobs.keys():
                for gate in required:
                    with self.subTest(workflow=name, job=mutation, gate=gate):
                        self.assertIn(gate, ancestors(jobs, mutation))
                        for job in ancestors(jobs, mutation) | {mutation}:
                            self.assertIn(
                                jobs[job].get("if", "success()"),
                                ("success()", "${{ success() }}"),
                            )
                            self.assertNotIn("continue-on-error", jobs[job])

    def test_tags_and_manual_runs_use_the_same_gates_and_revision(self):
        for name in RELEASES:
            workflow = load(name)
            with self.subTest(workflow=name):
                self.assertIn("workflow_dispatch", workflow["on"])
                self.assertEqual(set(workflow["on"]["push"]["branches"]), BRANCHES)
                self.assertNotIn("workflow_run", workflow["on"])
                if name in IMAGE_TAGS:
                    self.assertIn(IMAGE_TAGS[name], workflow["on"]["push"]["tags"])
                    publish = workflow["jobs"]["push-image"]
                    checkouts = [
                        step
                        for step in publish["steps"]
                        if step.get("uses", "").startswith("actions/checkout@")
                    ]
                    self.assertEqual(len(checkouts), 1)
                    self.assertNotIn("ref", checkouts[0].get("with", {}))
                    builds = [
                        step
                        for step in publish["steps"]
                        if step.get("uses", "").startswith("docker/build-push-action@")
                    ]
                    self.assertEqual(len(builds), 1)
                    self.assertEqual(builds[0]["with"]["push"], "true")
                    self.assertIn("${{ github.sha }}", builds[0]["with"]["tags"])
                    self.assertIn(
                        "${{ needs.resolve-image-tag.outputs.image_tag }}",
                        builds[0]["with"]["tags"],
                    )

    def test_docs_checks_validate_the_production_build(self):
        jobs = load("deploy-docs.yml")["jobs"]
        self.assertIn("tests", jobs)
        tests = jobs["tests"]
        self.assertEqual(tests["defaults"]["run"]["working-directory"], "docs")
        commands = "\n".join(step.get("run", "") for step in tests["steps"])
        for command in ("npm ci", "npm run build"):
            self.assertIn(command, commands)
        for step in tests["steps"]:
            self.assertNotIn("if", step)
            self.assertNotIn("continue-on-error", step)

    def test_image_tag_resolution_preserves_branch_and_release_tags(self):
        for name, pattern in IMAGE_TAGS.items():
            cases = [
                ("branch", "main", "dev"),
                ("branch", "staging", "staging"),
                ("branch", "production", "latest"),
                ("tag", pattern.replace("*", "1.2.3"), "v1.2.3"),
                ("tag", pattern.replace("*", "1.2.3-rc.1"), "v1.2.3-rc.1"),
                ("branch", "feature/unapproved", None),
                ("tag", pattern.replace("*", "invalid"), None),
                ("tag", "unrelated/v1.2.3", None),
            ]
            command = load(name)["jobs"]["resolve-image-tag"]["steps"][0]["run"]
            for event in ("push", "workflow_dispatch"):
                for ref_type, ref_name, expected in cases:
                    with self.subTest(workflow=name, event=event, ref=ref_name):
                        script = command.replace(
                            "${{ github.ref_type }}", ref_type
                        ).replace("${{ github.ref_name }}", ref_name)
                        with tempfile.TemporaryDirectory() as directory:
                            output = Path(directory) / "output"
                            result = subprocess.run(
                                ["bash", "-e", "-c", script],
                                env={
                                    **os.environ,
                                    "GITHUB_OUTPUT": str(output),
                                    "GITHUB_EVENT_NAME": event,
                                },
                                capture_output=True,
                                text=True,
                                check=False,
                            )
                            if expected is None:
                                self.assertNotEqual(result.returncode, 0)
                                self.assertFalse(output.exists())
                            else:
                                self.assertEqual(result.returncode, 0, result.stderr)
                                self.assertEqual(
                                    output.read_text().strip(), f"image_tag={expected}"
                                )

    def test_flow_frontend_gate_builds_the_bundle(self):
        workflow = load("[lumlflow] tests-and-linters.yml")
        for event in ("push", "pull_request"):
            self.assertIn("lumlflow/frontend/**", workflow["on"][event]["paths"])
        steps = workflow["jobs"]["unit"]["steps"]
        self.assertTrue(
            any(
                step.get("working-directory") == "lumlflow/frontend"
                and "vite build" in step.get("run", "")
                for step in steps
            )
        )

    def test_gate_acceptance_checks_run_in_ci(self):
        jobs = load("[repo] root-artifacts.yml")["jobs"]
        commands = "\n".join(
            step.get("run", "") for job in jobs.values() for step in job["steps"]
        )
        self.assertIn("python -m unittest discover -s .github/tests", commands)


if __name__ == "__main__":
    unittest.main()
