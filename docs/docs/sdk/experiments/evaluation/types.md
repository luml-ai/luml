## EvalItem

*dataclass* `EvalItem(id, inputs, expected_output=None, metadata={})`

**Parameters**

- **id** (*str*)
- **inputs** (*dict[str, Any]*)
- **expected_output** (*Any, optional*) – Defaults to `None`.
- **metadata** (*dict[str, Any], optional*) – Defaults to `{}`.

## EvalResult

*dataclass* `EvalResult(eval_item, model_response, scores, trace_id)`

**Parameters**

- **eval_item** (*EvalItem*)
- **model_response** (*Any*)
- **scores** (*dict[str, Any]*)
- **trace_id** (*str*)

## EvalResults

*dataclass* `EvalResults(results, aggregated_scores, dataset_id)`

**Parameters**

- **results** (*list[EvalResult]*)
- **aggregated_scores** (*dict[str, float | int]*)
- **dataset_id** (*str*)
