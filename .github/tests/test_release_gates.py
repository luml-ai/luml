"""acceptance checks for test-gated deployments, image publishing and promotion.

run with: uv run --with pyyaml python -m unittest discover -s .github/tests
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
BRANCHES = {"main", "staging", "production"}
PROMOTION_BRANCHES = {"staging", "production"}
DEPLOYS = {
    "deploy-backend.yml": {"tests": "[backend] tests-and-linters.yml"},
    "deploy-frontend.yml": {
        "tests": "[frontend] tests-and-linters.yml",
        "extras-tests": "[extras-js] tests-and-linters.yml",
    },
    "deploy-docs.yml": {"tests": None},
}
PUBLISHERS = {
    "publish-satellite-images.yml": {
        "kit-tests": "[satellite-kit] tests-and-linters.yml",
        "docker-tests": "[satellite-docker] tests-and-linters.yml",
        "kubernetes-tests": "[satellite-kubernetes] tests-and-linters.yml",
        "ui-tests": "[satellite-monitoring-ui] tests-and-linters.yml",
    },
    "publish-relay-image.yml": {"tests": "[relay] tests-and-linters.yml"},
    "publish-model-server-image.yml": {"tests": "[model-server] tests-and-linters.yml"},
}
RELEASES = {**DEPLOYS, **PUBLISHERS}
IMAGE_TAGS = {
    "publish-satellite-images.yml": {
        "satellite/agent/v*": "luml-satellite-agent",
        "satellite/kubernetes/v*": "luml-satellite-kubernetes",
        "satellite/monitoring/v*": "luml-satellite-monitoring",
        "satellite/serving/v*": "luml-satellite-serving",
    },
    "publish-relay-image.yml": {"luml-relay/image/v*": "luml-relay"},
    "publish-model-server-image.yml": {
        "satellite/model-server/v*": "luml-model-server"
    },
}
PROMOTION = "promote-images.yml"
PACKAGE_GATES = {
    "sdk-python/api/v*": {"api-client-tests": "[api-client] tests-and-linters.yml"},
    "sdk-python/sdk/v*": {"sdk-tests": "[sdk] tests-and-linters.yml"},
    "lumlflow/v*": {
        "lumlflow-tests": "[lumlflow] tests-and-linters.yml",
        "lumlflow-frontend-tests": "[lumlflow-frontend] tests-and-linters.yml",
    },
    "luml-prisma/v*": {"prisma-tests": "[prisma] tests-and-linters.yml"},
    "luml-mlflow/v*": {"luml-mlflow-tests": "[luml-mlflow] tests-and-linters.yml"},
    "luml-relay/v*": {"relay-tests": "[relay] tests-and-linters.yml"},
}
CHART_GATES = {
    "tests": "[satellite-kubernetes] tests-and-linters.yml",
    "end-to-end": "[satellite-kubernetes] end-to-end.yml",
}
RELEASE_COVERED_SUITES = {
    "[backend] tests-and-linters.yml",
    "[frontend] tests-and-linters.yml",
    "[extras-js] tests-and-linters.yml",
    "[satellite-kit] tests-and-linters.yml",
    "[satellite-docker] tests-and-linters.yml",
    "[satellite-kubernetes] tests-and-linters.yml",
    "[satellite-monitoring-ui] tests-and-linters.yml",
    "[model-server] tests-and-linters.yml",
    "[relay] tests-and-linters.yml",
}
SUITE_TESTS = {
    "[backend] tests-and-linters.yml": (
        "pytest tests/unit",
        "pytest tests/integration",
    ),
    "[frontend] tests-and-linters.yml": ("npm run test:ci", "npm run test:integration"),
    "[lumlflow] tests-and-linters.yml": (
        "pytest tests/unit",
        "pytest tests/integration",
    ),
    "[lumlflow-frontend] tests-and-linters.yml": ("npm run test:ci", "vite build"),
    "[extras-js] tests-and-linters.yml": ("npm run test:ci", "npm run build-only"),
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


def run_step(script, env, cwd=None):
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "output"
        summary = Path(directory) / "summary"
        result = subprocess.run(
            ["bash", "-e", "-c", script],
            env={
                **os.environ,
                "GITHUB_OUTPUT": str(output),
                "GITHUB_STEP_SUMMARY": str(summary),
                **env,
            },
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        values = {}
        if output.exists():
            for line in output.read_text().splitlines():
                key, _, value = line.partition("=")
                values[key] = value
        return result, values


def named_step(job, name):
    steps = [step for step in job["steps"] if step.get("name") == name]
    assert len(steps) == 1, name
    return steps[0]


def resolve_script(name):
    return load(name)["jobs"]["resolve-image-tag"]["steps"][0]["run"]


def render(script, ref_type, ref_name):
    return script.replace("${{ github.ref_type }}", ref_type).replace(
        "${{ github.ref_name }}", ref_name
    )


def git(cwd, *args):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "ci",
            "GIT_AUTHOR_EMAIL": "ci@example.com",
            "GIT_COMMITTER_NAME": "ci",
            "GIT_COMMITTER_EMAIL": "ci@example.com",
        },
    ).stdout.strip()


class ReleaseGateTests(unittest.TestCase):
    def test_checks_run_on_pull_requests_to_every_release_branch(self):
        paths = list(WORKFLOWS.glob("*tests-and-linters.yml"))
        paths.append(WORKFLOWS / "[satellite-kubernetes] end-to-end.yml")
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
                    self.assertEqual(set(workflow["on"]["push"]["branches"]), {"main"})

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

    def test_deploys_run_on_every_release_branch(self):
        for name in DEPLOYS:
            workflow = load(name)
            with self.subTest(workflow=name):
                self.assertIn("workflow_dispatch", workflow["on"])
                self.assertNotIn("workflow_run", workflow["on"])
                self.assertEqual(set(workflow["on"]["push"]["branches"]), BRANCHES)

    def test_images_are_built_once_on_main_and_on_release_tags(self):
        for name, tags in IMAGE_TAGS.items():
            workflow = load(name)
            with self.subTest(workflow=name):
                self.assertIn(name, PUBLISHERS)
                self.assertIn("workflow_dispatch", workflow["on"])
                self.assertNotIn("workflow_run", workflow["on"])
                self.assertEqual(set(workflow["on"]["push"]["branches"]), {"main"})
                self.assertEqual(set(workflow["on"]["push"]["tags"]), set(tags))
                self.assertIn(
                    f".github/workflows/{name}", workflow["on"]["push"]["paths"]
                )
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

    def test_image_tag_resolution_builds_main_and_release_tags_only(self):
        for name, tags in IMAGE_TAGS.items():
            script = resolve_script(name)
            cases = [
                ("branch", "main", "dev", set(tags.values())),
                ("branch", "staging", None, None),
                ("branch", "production", None, None),
                ("branch", "feature/unapproved", None, None),
                ("tag", "unrelated/v1.2.3", None, None),
            ]
            for pattern, image in tags.items():
                cases += [
                    ("tag", pattern.replace("*", "1.2.3"), "v1.2.3", {image}),
                    ("tag", pattern.replace("*", "1.2.3-rc.1"), "v1.2.3-rc.1", {image}),
                    ("tag", pattern.replace("*", "invalid"), None, None),
                ]
            for event in ("push", "workflow_dispatch"):
                for ref_type, ref_name, expected, images in cases:
                    with self.subTest(workflow=name, event=event, ref=ref_name):
                        result, values = run_step(
                            render(script, ref_type, ref_name),
                            {"GITHUB_EVENT_NAME": event},
                        )
                        if expected is None:
                            self.assertNotEqual(result.returncode, 0)
                            self.assertEqual(values, {})
                            continue
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(values["image_tag"], expected)
                        if "images" in values:
                            matrix = json.loads(values["images"])
                            self.assertEqual(
                                {entry["name"] for entry in matrix["include"]}, images
                            )
                            for entry in matrix["include"]:
                                self.assertTrue((ROOT / entry["file"]).is_file(), entry)
                                self.assertTrue(
                                    (ROOT / entry["file"]).is_relative_to(
                                        ROOT / entry["context"]
                                    ),
                                    entry,
                                )
                        else:
                            self.assertEqual(len(images), 1)

    def test_satellite_images_build_as_a_matrix_from_the_resolved_revision(self):
        workflow = load("publish-satellite-images.yml")
        publish = workflow["jobs"]["push-image"]
        self.assertEqual(
            publish["strategy"]["matrix"],
            "${{ fromJSON(needs.resolve-image-tag.outputs.images) }}",
        )
        build = next(
            step
            for step in publish["steps"]
            if step.get("uses", "").startswith("docker/build-push-action@")
        )
        self.assertEqual(build["with"]["context"], "${{ matrix.context }}")
        self.assertEqual(build["with"]["file"], "${{ matrix.file }}")
        self.assertIn("${{ matrix.name }}:${{ github.sha }}", build["with"]["tags"])

    def test_promotion_retags_the_main_build_instead_of_rebuilding(self):
        workflow = load(PROMOTION)
        self.assertEqual(set(workflow["on"]["push"]["branches"]), PROMOTION_BRANCHES)
        self.assertIn("workflow_dispatch", workflow["on"])
        self.assertNotIn("workflow_run", workflow["on"])
        self.assertNotIn("tags", workflow["on"]["push"])
        jobs = workflow["jobs"]
        promote = jobs["promote"]
        self.assertIn("resolve-image-tag", ancestors(jobs, "promote"))
        self.assertEqual(promote.get("if", "success()"), "success()")
        self.assertNotIn("continue-on-error", promote)
        steps_text = "\n".join(step.get("run", "") for step in promote["steps"])
        self.assertNotIn("build-push-action", json.dumps(promote["steps"]))
        self.assertIn("docker manifest inspect", steps_text)
        self.assertIn("docker buildx imagetools create", steps_text)
        self.assertIn("--first-parent", steps_text)
        checkouts = [
            step
            for step in promote["steps"]
            if step.get("uses", "").startswith("actions/checkout@")
        ]
        self.assertEqual(len(checkouts), 1)
        self.assertEqual(checkouts[0]["with"]["fetch-depth"], "0")
        self.assertNotIn("ref", checkouts[0]["with"])

        images = {}
        for pattern_to_image in IMAGE_TAGS.values():
            for name, image in pattern_to_image.items():
                images[image] = next(
                    workflow
                    for workflow, patterns in IMAGE_TAGS.items()
                    if name in patterns
                )
        entries = {
            entry["name"]: entry for entry in promote["strategy"]["matrix"]["include"]
        }
        self.assertEqual(set(entries), set(images))
        promoted_paths = set()
        for image, publisher in images.items():
            with self.subTest(image=image):
                entry = entries[image]
                self.assertEqual(entry["built-by"], publisher)
                publisher_paths = set(load(publisher)["on"]["push"]["paths"])
                self.assertEqual(set(entry["paths"].split()), publisher_paths)
                promoted_paths |= publisher_paths
        promoted_paths.add(f".github/workflows/{PROMOTION}")
        self.assertEqual(set(workflow["on"]["push"]["paths"]), promoted_paths)

    def test_promotion_tag_resolution_accepts_promotion_branches_only(self):
        script = resolve_script(PROMOTION)
        cases = [
            ("staging", "staging"),
            ("production", "latest"),
            ("main", None),
            ("feature/unapproved", None),
        ]
        for ref_name, expected in cases:
            with self.subTest(ref=ref_name):
                result, values = run_step(render(script, "branch", ref_name), {})
                if expected is None:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(values, {})
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(values, {"image_tag": expected})

    def test_promotion_finds_the_last_commit_that_touched_the_image_inputs(self):
        promote = load(PROMOTION)["jobs"]["promote"]
        script = named_step(promote, "Find the build of this revision")["run"]
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            git(repo, "init", "-q", "-b", "main")

            def commit(path, message):
                target = repo / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(message)
                git(repo, "add", path)
                git(repo, "commit", "-q", "-m", message)
                return git(repo, "rev-parse", "HEAD")

            commit("relay/luml_relay/app.py", "relay 1")
            built = commit("sdk/python/api/client.py", "api change")
            head = commit("backend/app.py", "unrelated")

            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            inspected = Path(directory) / "inspected"
            docker = bin_dir / "docker"
            docker.write_text(
                "#!/bin/bash\n"
                f'echo "$*" >> "{inspected}"\n'
                '[[ "$3" == "$EXISTING_IMAGE" ]]\n'
            )
            docker.chmod(0o755)
            env = {
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "IMAGE": "ghcr.io/example/luml-relay",
                "PATHS": "relay/**\nsdk/python/api/**\n",
                "BUILT_BY": "publish-relay-image.yml",
                "IMAGE_TAG": "staging",
            }
            rendered = script.replace("${{ github.sha }}", head)

            result, values = run_step(
                rendered,
                {**env, "EXISTING_IMAGE": f"ghcr.io/example/luml-relay:{built}"},
                cwd=repo,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(values, {"image": env["IMAGE"], "source": built})
            self.assertEqual(
                inspected.read_text().strip(),
                f"manifest inspect ghcr.io/example/luml-relay:{built}",
            )

            inspected.unlink()
            result, values = run_step(
                rendered, {**env, "EXISTING_IMAGE": "none"}, cwd=repo
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(values, {})
            self.assertIn("not in the registry", result.stderr)

            inspected.unlink()
            result, values = run_step(
                rendered,
                {**env, "PATHS": "model_servers/**\n", "EXISTING_IMAGE": "none"},
                cwd=repo,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(values, {})
            self.assertFalse(inspected.exists())

    def test_flow_frontend_gate_builds_the_bundle(self):
        workflow = load("[lumlflow-frontend] tests-and-linters.yml")
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

    def test_each_python_package_tag_requires_its_own_checks(self):
        workflow = load("publish-sdk-python.yml")
        jobs = workflow["jobs"]
        self.assertEqual(set(workflow["on"]["push"]["tags"]), set(PACKAGE_GATES))
        script = jobs["resolve"]["steps"][0]["run"]
        for pattern, gates in PACKAGE_GATES.items():
            tag = pattern.replace("*", "1.2.3rc0")
            with self.subTest(tag=tag):
                result, values = run_step(script, {"GITHUB_REF_NAME": tag})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(set(values["gates"].split()), set(gates))
                self.assertEqual(values["version"], "1.2.3rc0")
                for gate, suite in gates.items():
                    self.assertEqual(jobs[gate]["uses"], f"./.github/workflows/{suite}")
                    self.assertIn("workflow_call", load(suite)["on"])
                    self.assertEqual(
                        jobs[gate]["if"],
                        f"startsWith(github.ref_name, '{pattern[:-1]}')",
                    )
        result, _ = run_step(script, {"GITHUB_REF_NAME": "unrelated/v1.2.3"})
        self.assertNotEqual(result.returncode, 0)

    def test_a_python_package_publishes_only_after_its_checks_succeed(self):
        jobs = load("publish-sdk-python.yml")["jobs"]
        publish = jobs["publish"]
        gates = {gate for gates in PACKAGE_GATES.values() for gate in gates}
        self.assertEqual(dependencies(jobs, "publish"), gates | {"resolve"})
        self.assertNotIn("continue-on-error", publish)
        self.assertEqual(publish["steps"][0]["name"], "Require the package's checks")
        script = publish["steps"][0]["run"]
        cases = [
            ({"sdk-tests": "success"}, "sdk-tests", 0),
            ({"sdk-tests": "failure"}, "sdk-tests", 1),
            ({"sdk-tests": "skipped"}, "sdk-tests", 1),
            ({"sdk-tests": "cancelled"}, "sdk-tests", 1),
            (
                {"lumlflow-tests": "success", "lumlflow-frontend-tests": "failure"},
                "lumlflow-tests lumlflow-frontend-tests",
                1,
            ),
            ({}, "", 0),
        ]
        for results, required, expected in cases:
            with self.subTest(results=results):
                needs = {gate: {"result": value} for gate, value in results.items()}
                result, _ = run_step(
                    script, {"GATES": required, "RESULTS": json.dumps(needs)}
                )
                self.assertEqual(result.returncode != 0, bool(expected), result.stderr)

    def test_a_python_package_is_installed_from_the_index_before_it_is_published(
        self,
    ):
        steps = load("publish-sdk-python.yml")["jobs"]["publish"]["steps"]
        names = [step.get("name") for step in steps]
        check = names.index("Install the wheel from the public index")
        self.assertLess(names.index("Build"), check)
        self.assertLess(check, names.index("Publish"))
        command = steps[check]["run"]
        self.assertIn("--no-sources", command)
        self.assertIn("Provides-Extra", command)
        self.assertIn("import $IMPORT_NAME", command)
        self.assertNotIn("continue-on-error", steps[check])
        self.assertNotIn("if", steps[check])

    def test_the_chart_publishes_only_after_the_kubernetes_checks(self):
        jobs = load("publish-kubernetes-satellite-chart.yml")["jobs"]
        for gate, suite in CHART_GATES.items():
            with self.subTest(gate=gate):
                self.assertEqual(jobs[gate]["uses"], f"./.github/workflows/{suite}")
                self.assertIn("workflow_call", load(suite)["on"])
                self.assertNotIn("if", jobs[gate])
                self.assertIn(gate, ancestors(jobs, "publish-chart"))
        self.assertIn(
            jobs["publish-chart"].get("if", "success()"),
            ("success()", "${{ success() }}"),
        )

    def test_gate_acceptance_checks_run_in_ci(self):
        jobs = load("[repo] root-artifacts.yml")["jobs"]
        commands = "\n".join(
            step.get("run", "") for job in jobs.values() for step in job["steps"]
        )
        self.assertIn("python -m unittest discover -s .github/tests", commands)


if __name__ == "__main__":
    unittest.main()
