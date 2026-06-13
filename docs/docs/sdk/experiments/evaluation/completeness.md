<a id="luml.experiments.evaluation.scorers.builtin.completeness"></a>

# luml.experiments.evaluation.scorers.builtin.completeness

<a id="luml.experiments.evaluation.scorers.builtin.completeness.Completeness"></a>

## Completeness Objects

```python
class Completeness(LLMJudgeScorer)
```

Scores whether a response fully addresses all parts of a question or task.

Unsupervised scorer — no expected output required. Returns a float 0.0
(does not address the question) to 1.0 (fully and completely addresses
all parts).

Default input keys: ``"question"``, ``"task"``.

```python
from luml.experiments.evaluation.scorers.builtin import Completeness
scorer = Completeness()
```


