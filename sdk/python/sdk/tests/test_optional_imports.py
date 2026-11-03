import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize(
    ("dependency", "script"),
    [
        (
            "scipy",
            """
            from luml.utils.packaging import normalize_inputs
            array, names, _ = normalize_inputs([[1, 2]], 'unified')
            assert array.tolist() == [[1, 2]]
            assert names == ['x0', 'x1']
            """,
        ),
        (
            "opentelemetry",
            """
            from luml.experiments.evaluation import EvalItem
            from luml.experiments.evaluation.evaluate import evaluate
            from luml.experiments.evaluation.scorers.builtin import Relevancy
            try:
                evaluate(
                    [EvalItem(id="item", inputs={})],
                    lambda _: 'response', [], 'data', None,
                )
            except ImportError as exc:
                assert 'luml_sdk[tracing]' in str(exc)
            else:
                raise AssertionError('expected an actionable missing dependency error')

            class Client:
                def complete(self, system_prompt, user_prompt):
                    raise AssertionError('should not call the judge without tracing')

            try:
                Relevancy(client=Client()).score({'prompt': 'question'}, 'answer')
            except ImportError as exc:
                assert 'luml_sdk[tracing]' in str(exc)
            else:
                raise AssertionError('expected an actionable missing dependency error')
            """,
        ),
    ],
    ids=["scipy", "opentelemetry"],
)
def test_import_without_optional_dependency(dependency: str, script: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            f"import sys\nsys.modules[{dependency!r}] = None\n"
            + textwrap.dedent(script),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
