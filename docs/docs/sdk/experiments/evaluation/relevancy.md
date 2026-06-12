<a id="luml.experiments.evaluation.scorers.builtin.relevancy"></a>

# luml.experiments.evaluation.scorers.builtin.relevancy

<a id="luml.experiments.evaluation.scorers.builtin.relevancy.Relevancy"></a>

## Relevancy Objects

```python
class Relevancy(LLMJudgeScorer)
```

Scores how relevant a response is to the input question.

Unsupervised scorer — no expected output required. Returns a float
0.0 (completely irrelevant) to 1.0 (fully relevant).

Default input keys: ``"question"``, ``"query"``.

```python
from luml.experiments.evaluation.scorers.builtin import Relevancy
scorer = Relevancy()
scorer = Relevancy(input_key="prompt")
```


