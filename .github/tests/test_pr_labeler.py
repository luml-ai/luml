import glob
import re
import subprocess
import unittest

import yaml

from test_release_gates import ROOT, load

PACKAGES = {
    "backend": {"backend"},
    "frontend": {"frontend"},
    "docs": {"documentation"},
    "extras/js": {"extras-js"},
    "extras/python/luml-mlflow": {"luml-mlflow"},
    "lumlflow": {"Lumlflow"},
    "lumlflow/frontend": {"lumlflow-frontend"},
    "model_servers/default": {"model-server"},
    "prisma": {"prisma"},
    "relay": {"relay"},
    "sdk/python/api": {"sdk-api"},
    "sdk/python/sdk": {"SDK"},
    "satellite/kit": {"satellite-kit"},
    "satellite/implementations/docker": {"satellite-docker"},
    "satellite/implementations/kubernetes": {"satellite-kubernetes"},
    "satellite/monitoring-ui": {"satellite-monitoring-ui"},
    "wasm/jupyter": {"wasm-jupyter"},
    "wasm/packages/promptopt": {"wasm-promptopt"},
    "wasm/packages/dfs_webworker": {"wasm-webworker"},
}
MANIFESTS = ("pyproject.toml", "package.json", "Chart.yaml")


def matches(path, pattern):
    negated = pattern.startswith("!")
    regex = glob.translate(pattern.lstrip("!"), recursive=True, include_hidden=True)
    return bool(re.fullmatch(regex, path)) != negated


def as_list(globs):
    return [globs] if isinstance(globs, str) else globs


def rule_matches(rule, files):
    (kind, globs), = rule.items()
    globs = as_list(globs)
    if kind == "any-glob-to-any-file":
        return any(matches(f, g) for f in files for g in globs)
    if kind == "all-globs-to-any-file":
        return any(all(matches(f, g) for g in globs) for f in files)
    raise AssertionError(f"unsupported matcher {kind}")


def labels_for(files):
    config = yaml.safe_load((ROOT / ".github/labeler.yml").read_text())
    labels = set()
    for label, match_objects in config.items():
        for match_object in match_objects:
            (key, rules), = match_object.items()
            if key != "changed-files":
                raise AssertionError(f"unsupported match object {key}")
            if any(rule_matches(rule, files) for rule in rules):
                labels.add(label)
    return labels


def package_roots():
    tracked = subprocess.run(
        ["git", "ls-files", *(f"*{name}" for name in MANIFESTS)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return {
        path.rsplit("/", 1)[0]
        for path in tracked
        if "/" in path and path.rsplit("/", 1)[1] in MANIFESTS
    }


class PRLabelerTests(unittest.TestCase):
    def test_each_package_gets_only_its_own_label(self):
        for root, expected in PACKAGES.items():
            with self.subTest(package=root):
                self.assertEqual(labels_for([f"{root}/src/module.py"]), expected)

    def test_every_tracked_package_has_a_label(self):
        for root in package_roots():
            with self.subTest(package=root):
                self.assertTrue(
                    any(root == known or root.startswith(f"{known}/") for known in PACKAGES),
                    f"{root} has no entry in .github/labeler.yml",
                )

    def test_files_outside_packages(self):
        cases = {
            ".github/workflows/deploy-backend.yml": {"ci"},
            "satellite/docker-compose.yml": {"satellite"},
            "wasm/build.sh": {"wasm"},
            "dev/seed.py": {"dev"},
            "package-lock.json": {"frontend"},
            "README.md": {"documentation"},
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(labels_for([path]), expected)

    def test_pull_request_touching_several_packages_gets_all_their_labels(self):
        self.assertEqual(
            labels_for(["lumlflow/luml_flow/cli.py", "lumlflow/frontend/src/App.vue"]),
            {"Lumlflow", "lumlflow-frontend"},
        )
        self.assertEqual(
            labels_for(["sdk/python/api/luml_api/client.py", "sdk/python/sdk/luml/flow.py"]),
            {"sdk-api", "SDK"},
        )

    def test_workflow_never_runs_pull_request_code(self):
        workflow = load("[repo] pr-labeler.yml")
        self.assertIn("pull_request_target", workflow["on"])
        self.assertEqual(workflow["permissions"], {})
        for job in workflow["jobs"].values():
            for step in job["steps"]:
                self.assertNotIn("checkout", step.get("uses", ""))
