"""acceptance checks that every change able to break the experiment snapshot e2e runs it.

run with: uv run --with pyyaml python -m unittest discover -s .github/tests
"""

import json
import re
import subprocess
import tomllib
import unittest

from test_release_gates import ROOT, load

WORKFLOW = "[experiment-snapshots] end-to-end.yml"
STACK = "frontend/tests/stack"
COMPONENT_ROOTS = {
    # built by run.sh (vite build) and served to the browser; also holds the stack suite
    "frontend": "platform frontend",
    # @luml/experiments and @luml/attachments, built by run.sh, imported by both frontends
    "extras/js": "shared JS packages",
    # run from source with real migrations
    "backend": "platform backend",
    # writes the experiments; the API client publishes them
    "sdk/python/sdk": "Python SDK",
    "sdk/python/api": "API client",
    # server from source, its web app bundled by run.sh
    "lumlflow": "Flow",
}
# The audit (LM-1100) found these changes merged without the e2e running.
MISSED_BEFORE = (
    "frontend/vite.config.ts",
    "frontend/package.json",
    "frontend/index.html",
    "frontend/src/main.ts",
    "frontend/src/lib/api/artifacts/index.ts",
    "frontend/src/components/collection/Table.vue",
    "frontend/src/router/index.ts",
    "extras/js/packages/attachments/src/index.ts",
    "package.json",
    "backend/luml/schemas/artifacts.py",
    "backend/luml/repositories/artifacts.py",
    "backend/luml/server.py",
    "lumlflow/lumlflow/server.py",
    "lumlflow/lumlflow/cli.py",
    "lumlflow/lumlflow/session.py",
    "lumlflow/lumlflow/handlers/annotations.py",
    "lumlflow/frontend/vite.config.ts",
    "lumlflow/frontend/src/docs/lumlflow_quickstart.md",
    "sdk/python/sdk/luml/utils/time.py",
)
UNRELATED = (
    "README.md",
    "frontend/README.md",
    "lumlflow/docs/user-guide.md",
    "docs/docs/index.md",
    "docs/package.json",
    "prisma/pyproject.toml",
    "satellite/kit/pyproject.toml",
    "model_servers/default/Dockerfile",
    "wasm/build.sh",
    "dev/docker-compose.yml",
    ".github/workflows/[backend] tests-and-linters.yml",
    ".github/tests/test_release_gates.py",
)
PYTHON_PROJECTS = ("backend", "sdk/python/sdk", "sdk/python/api", "lumlflow")


def filter_regex(pattern: str) -> str:
    """GitHub filter glob: `**` crosses `/`, `*` does not, `**/` may match no directory."""
    unsupported = set("?+[]") & set(pattern)
    assert not unsupported, f"{pattern}: {unsupported} not modelled"
    parts = re.split(r"(\*\*/|\*\*|\*)", pattern)
    wildcards = {"**/": "(?:.*/)?", "**": ".*", "*": "[^/]*"}
    return "".join(wildcards.get(part, re.escape(part)) for part in parts)


def triggers(patterns: list[str], changed: str) -> bool:
    # the last matching pattern decides; a leading `!` excludes
    included = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        if re.fullmatch(filter_regex(pattern.removeprefix("!")), changed):
            included = not negated
    return included


def tracked_files(root: str) -> list[str]:
    return subprocess.run(
        ["git", "ls-files", "--", root],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()


def probe(relative: str) -> str:
    return f"{relative}/module.ts" if (ROOT / relative).is_dir() else relative


def paths_the_jobs_read() -> set[str]:
    run_script = (ROOT / STACK / "run.sh").read_text()
    paths = set(re.findall(r"\$REPO/([\w./-]+)", run_script))
    for job in load(WORKFLOW)["jobs"].values():
        for step in job["steps"]:
            run = step.get("run", "")
            paths |= set(re.findall(r"\bcd ([\w./-]+)", run))
            paths |= set(re.findall(rf"^({STACK}/[\w./-]+)", run, re.MULTILINE))
            if "working-directory" in step:
                paths.add(step["working-directory"])
            dependency_path = step.get("with", {}).get("cache-dependency-path")
            if dependency_path:
                paths.add(dependency_path.removeprefix("./"))
    return paths


def local_dependencies() -> set[str]:
    workspaces = json.loads((ROOT / "package.json").read_text())["workspaces"]
    dependencies = {
        str(path.relative_to(ROOT))
        for workspace in workspaces
        for path in ROOT.glob(workspace)
        if path.is_dir()
    }
    for project in PYTHON_PROJECTS:
        pyproject = tomllib.loads((ROOT / project / "pyproject.toml").read_text())
        sources = pyproject.get("tool", {}).get("uv", {}).get("sources", {})
        for source in sources.values():
            if "path" in source:
                path = (ROOT / project / source["path"]).resolve()
                dependencies.add(str(path.relative_to(ROOT)))
    return dependencies


class ExperimentSnapshotsE2ETriggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = load(WORKFLOW)["on"]
        self.paths = self.events["pull_request"]["paths"]

    def test_push_to_main_uses_the_pull_request_paths(self) -> None:
        self.assertEqual(self.events["push"]["branches"], ["main"])
        self.assertEqual(self.events["push"]["paths"], self.paths)
        self.assertIn("workflow_dispatch", self.events)
        self.assertNotIn("paths-ignore", self.events["push"])
        self.assertNotIn("paths-ignore", self.events["pull_request"])

    def test_every_tracked_source_file_of_a_component_triggers(self) -> None:
        for root in COMPONENT_ROOTS:
            files = [path for path in tracked_files(root) if not path.endswith(".md")]
            with self.subTest(root=root):
                self.assertTrue(files)
                untriggered = [path for path in files if not triggers(self.paths, path)]
                self.assertEqual(untriggered, [])

    def test_files_the_jobs_read_trigger(self) -> None:
        paths = paths_the_jobs_read()
        self.assertIn("dev/seed.py", paths)
        for path in sorted(paths):
            with self.subTest(path=path):
                self.assertTrue(triggers(self.paths, probe(path)))

    def test_workspaces_and_source_installed_packages_trigger(self) -> None:
        dependencies = local_dependencies()
        self.assertIn("relay", dependencies)
        for path in sorted(dependencies):
            with self.subTest(path=path):
                self.assertTrue(triggers(self.paths, f"{path}/module.py"))
                self.assertTrue(triggers(self.paths, f"{path}/pyproject.toml"))

    def test_changes_the_audit_found_missed_trigger(self) -> None:
        for path in MISSED_BEFORE:
            with self.subTest(path=path):
                self.assertTrue(triggers(self.paths, path))

    def test_the_workflow_itself_triggers(self) -> None:
        self.assertTrue(triggers(self.paths, f".github/workflows/{WORKFLOW}"))

    def test_unrelated_changes_do_not_trigger(self) -> None:
        for path in UNRELATED:
            with self.subTest(path=path):
                self.assertFalse(triggers(self.paths, path))

    def test_matcher_follows_github_filter_rules(self) -> None:
        self.assertTrue(triggers(["a/**"], "a/b/c.py"))
        self.assertFalse(triggers(["a/*"], "a/b/c.py"))
        self.assertTrue(triggers(["**/*.md"], "README.md"))
        self.assertFalse(triggers(["a/**", "!**/*.md"], "a/README.md"))
        self.assertTrue(triggers(["!**/*.md", "a/**"], "a/README.md"))
        self.assertTrue(triggers([".github/*x*y.yml"], ".github/[x] y.yml"))


if __name__ == "__main__":
    unittest.main()
