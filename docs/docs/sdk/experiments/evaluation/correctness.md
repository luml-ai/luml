<a id="luml.experiments.evaluation.scorers.builtin.correctness"></a>

# luml.experiments.evaluation.scorers.builtin.correctness

<a id="luml.experiments.evaluation.scorers.builtin.correctness.Correctness"></a>

## Correctness Objects

```python
class Correctness(SupervisedLLMJudgeScorer)
```

Scores factual correctness of a response against expected facts.

Supervised scorer — requires ``expected_output``. Checks faithfulness
(facts correct?) and hallucination (fabricated information?). Returns a
float 0.0 (incorrect / hallucinated) to 1.0 (fully correct and faithful).

``expected_output`` can be a string or a dict with an ``"expected_facts"``
list, which is formatted as a bulleted block for the judge.

Default input keys: ``"request"``, ``"question"``.

```python
from luml.experiments.evaluation.scorers.builtin import Correctness
scorer = Correctness()
```


