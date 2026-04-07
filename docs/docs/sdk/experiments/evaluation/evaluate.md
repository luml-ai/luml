<a id="luml.experiments.evaluation.evaluate"></a>

# luml.experiments.evaluation.evaluate

<a id="luml.experiments.evaluation.evaluate.evaluate"></a>

#### evaluate

```python
def evaluate(
    eval_dataset: list[EvalItem],
    inference_fn: Callable[[dict[str, Any]], Any],
    scorers: list[BaseScorer],
    dataset_id: str,
    experiment_tracker: ExperimentTracker,
    n_threads: int = 1
) -> EvalResults
```

Evaluates a dataset using the given inference function and scorers.

This function processes each evaluation item from the input dataset, applies the
provided inference function to generate predictions, and scores these predictions
using the specified scorers. Results are aggregated across the dataset and returned.

**Arguments**:

- `eval_dataset` _list[EvalItem]_ - The dataset to evaluate, where each item contains
  the necessary data for inference and scoring.
- `inference_fn` _Callable[[dict[str, Any]], Any]_ - A callable that generates predictions
  for a single evaluation input. The callable receives a dictionary of input
  data and returns the corresponding prediction.
- `scorers` _list[BaseScorer]_ - A list of scorer objects used to evaluate the
  predictions for each item in the dataset.
- `dataset_id` _str_ - A unique identifier for the dataset being evaluated.
- `experiment_tracker` _ExperimentTracker_ - An object for tracking evaluation results
  and metadata during the experiment.
- `n_threads` _int_ - The number of threads to use for parallel evaluation. Defaults to 1,
  which performs evaluation sequentially.
  

**Returns**:

- `EvalResults` - An object containing detailed evaluation results for each item,
  aggregated scores across the dataset, and the associated dataset ID.

