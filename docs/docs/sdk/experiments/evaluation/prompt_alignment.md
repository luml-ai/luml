<a id="luml.experiments.evaluation.scorers.builtin.prompt_alignment"></a>

# luml.experiments.evaluation.scorers.builtin.prompt_alignment

<a id="luml.experiments.evaluation.scorers.builtin.prompt_alignment.PromptAlignment"></a>

## PromptAlignment Objects

```python
class PromptAlignment(LLMJudgeScorer)
```

Scores whether a response follows the given instructions.

Unsupervised scorer — no expected output required. Considers format,
length, style, and content constraints. Returns a float 0.0 (instructions
ignored) to 1.0 (all instructions followed).

Default input keys: ``"instructions"``.

```python
from luml.experiments.evaluation.scorers.builtin import PromptAlignment
scorer = PromptAlignment()
scorer = PromptAlignment(input_key="system_prompt")
```


