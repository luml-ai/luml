"""acceptance checks for package-prefixed release workflow filenames."""

import tempfile
import unittest
from pathlib import Path

from test_release_gates import WORKFLOWS, git, load

RELEASE_NAMES = {
    "[backend] deploy.yml": "Deploy Backend",
    "[frontend] deploy.yml": "Deploy Frontend",
    "[docs] deploy.yml": "Deploy Docs",
    "[satellite] publish-images.yml": "Publish Satellite Images",
    "[satellite-kubernetes] publish-chart.yml": "Publish Kubernetes Satellite Chart",
    "[model-server] publish-image.yml": "Publish Model Server Image",
    "[relay] publish-image.yml": "Publish Relay Image",
    "[python-packages] publish.yml": "Publish Python Package",
    "[images] promote.yml": "Promote Images",
}


class WorkflowNameTests(unittest.TestCase):
    def test_release_workflows_keep_their_display_names(self):
        for name, title in RELEASE_NAMES.items():
            with self.subTest(workflow=name):
                self.assertEqual(load(name)["name"], title)
        for path in WORKFLOWS.glob("*.yml"):
            with self.subTest(workflow=path.name):
                self.assertRegex(path.name, r"^\[[a-z-]+\] .+\.yml$")

    def test_workflow_changes_match_their_trigger_filters(self):
        triggers = {
            "[satellite] publish-images.yml": [
                ("[satellite] publish-images.yml", "push"),
                ("[satellite-docker] tests-and-linters.yml", "pull_request"),
                ("[satellite-kubernetes] tests-and-linters.yml", "pull_request"),
                ("[images] promote.yml", "push"),
            ],
            "[model-server] publish-image.yml": [
                ("[model-server] publish-image.yml", "push"),
                ("[model-server] tests-and-linters.yml", "pull_request"),
                ("[images] promote.yml", "push"),
            ],
            "[relay] publish-image.yml": [
                ("[relay] publish-image.yml", "push"),
                ("[images] promote.yml", "push"),
            ],
            "[satellite-kubernetes] publish-chart.yml": [
                ("[satellite-kubernetes] tests-and-linters.yml", "pull_request"),
            ],
            "[images] promote.yml": [("[images] promote.yml", "push")],
        }
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            git(repo, "init", "-q")
            for name in triggers:
                target = repo / ".github/workflows" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
            git(repo, "add", ".")
            for name, callers in triggers.items():
                for caller, event in callers:
                    with self.subTest(changed=name, workflow=caller, event=event):
                        patterns = load(caller)["on"][event]["paths"]
                        matches = git(
                            repo, "ls-files", "--", *(f":(glob){p}" for p in patterns)
                        ).splitlines()
                        self.assertIn(f".github/workflows/{name}", matches)


if __name__ == "__main__":
    unittest.main()
