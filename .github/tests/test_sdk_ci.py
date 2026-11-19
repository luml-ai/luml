"""acceptance checks for SDK CI coverage on Windows.

run with: uv run --with pyyaml python -m unittest discover -s .github/tests
"""

import unittest

from test_release_gates import load


class SdkCITests(unittest.TestCase):
    def test_windows_job_runs_the_experiment_export_tests(self):
        job = load("[sdk] tests-and-linters.yml")["jobs"]["windows"]
        self.assertTrue(job["runs-on"].startswith("windows"))
        self.assertNotIn("continue-on-error", job)
        steps = [
            step
            for step in job["steps"]
            if "tests/artifacts/test_experiment_packaging.py" in step.get("run", "")
        ]
        self.assertEqual(len(steps), 1)
        self.assertNotIn("continue-on-error", steps[0])
        self.assertNotIn("if", steps[0])


if __name__ == "__main__":
    unittest.main()
