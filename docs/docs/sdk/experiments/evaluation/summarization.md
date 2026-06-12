<a id="luml.experiments.evaluation.scorers.builtin.summarization"></a>

# luml.experiments.evaluation.scorers.builtin.summarization

<a id="luml.experiments.evaluation.scorers.builtin.summarization.Summarization"></a>

## Summarization Objects

```python
class Summarization(LLMJudgeScorer)
```

Scores how well a summary captures its source text.

Unsupervised scorer — no expected output required. Evaluates accuracy,
coverage, and absence of hallucination. Returns a float 0.0 (inaccurate /
fabricated) to 1.0 (accurately captures all key information).

Default input keys: ``"text"``.

```python
from luml.experiments.evaluation.scorers.builtin import Summarization
scorer = Summarization()
scorer = Summarization(input_key="document")
```


