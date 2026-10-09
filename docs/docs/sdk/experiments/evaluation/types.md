<a id="luml.experiments.evaluation.types"></a>

# luml.experiments.evaluation.types

<a id="luml.experiments.evaluation.types.EvalItem"></a>

## EvalItem Objects

```python
@dataclass
class EvalItem()
```

One evaluation case: the inputs to run and, optionally, the expected output.

**Attributes**:

- `id` - Unique id of the case within its dataset.
- `inputs` - Keyword arguments handed to the evaluated task.
- `expected_output` - Reference answer for scorers that compare against one.
- `metadata` - Free-form extra context stored with the case.

<a id="luml.experiments.evaluation.types.EvalResult"></a>

## EvalResult Objects

```python
@dataclass
class EvalResult()
```

Outcome of one evaluation case.

**Attributes**:

- `eval_item` - The case that was run.
- `model_response` - What the evaluated task returned.
- `scores` - Score name to value, as produced by the scorers.
- `trace_id` - Id of the trace recorded for this run.

<a id="luml.experiments.evaluation.types.EvalResults"></a>

## EvalResults Objects

```python
@dataclass
class EvalResults()
```

All outcomes of one evaluation run.

**Attributes**:

- `results` - One `EvalResult` per evaluated case.
- `aggregated_scores` - Score name to aggregate value across the run.
- `dataset_id` - Id of the dataset the cases came from.

