import warnings
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Tracer

from luml.experiments.evaluation.scorers.base import (
    BaseScorer,
    SupervisedScorer,
    UnsupervisedScorer,
)
from luml.experiments.evaluation.types import (
    EvalItem,
    EvalResult,
    EvalResults,
)
from luml.experiments.tracker import ExperimentTracker


def _call_scorer(
    scorer: BaseScorer,
    eval_item: EvalItem,
    model_response: Any,  # noqa: ANN401
) -> dict[str, Any]:  # noqa: ANN401
    """
    Calls the given scorer with the provided evaluation item and
    model response, handling both supervised and unsupervised scoring methods.
    This function determines the type of scorer and appropriately invokes
    its scoring mechanism. The result of the scoring is formatted as a
    dictionary for uniformity.

    Args:
        scorer (BaseScorer): The scorer instance to evaluate the provided inputs. Must
            be an instance of either SupervisedScorer or UnsupervisedScorer.
        eval_item (EvalItem): The evaluation item containing inputs and, in the case of
            supervised scoring, the expected output.
        model_response (Any): The model's response to the inputs in the evaluation item.

    Returns:
        dict[str, Any]: A dictionary containing the scorer's name as the key and the
            evaluation result as the value.

    Raises:
        ValueError: If a supervised scorer is provided but the
            `expected_output` field of the evaluation item is missing.
        TypeError: If the provided scorer is neither a SupervisedScorer nor an
            UnsupervisedScorer.
    """
    if isinstance(scorer, SupervisedScorer):
        if eval_item.expected_output is None:
            raise ValueError(
                f"Supervised scorer '{scorer.get_name()}' requires "
                f"expected_output, but it is not provided."
            )
        result = scorer.score(
            eval_item.inputs,
            eval_item.expected_output,
            model_response,
        )
    elif isinstance(scorer, UnsupervisedScorer):
        result = scorer.score(eval_item.inputs, model_response)
    else:
        raise TypeError(
            f"Scorer '{scorer.get_name()}' must be an instance "
            f"of UnsupervisedScorer or SupervisedScorer."
        )

    scorer_name = scorer.get_name()

    if isinstance(result, dict):
        return result
    if isinstance(result, bool):
        return {scorer_name: result}
    return {scorer_name: result}


def evaluate(
    eval_dataset: list[EvalItem],
    inference_fn: Callable[[dict[str, Any]], Any],  # noqa: ANN401
    scorers: list[BaseScorer],
    dataset_id: str,
    experiment_tracker: ExperimentTracker,
    n_threads: int = 1,
) -> EvalResults:
    """
    Evaluates a dataset using the given inference function and scorers.

    This function processes each evaluation item from the input dataset, applies the
    provided inference function to generate predictions, and scores these predictions
    using the specified scorers. Results are aggregated across the dataset and returned.

    Args:
        eval_dataset (list[EvalItem]): The dataset to evaluate, where each item contains
            the necessary data for inference and scoring.
        inference_fn (Callable[[dict[str, Any]], Any]): A callable that generates
            predictions for a single evaluation input. The callable receives a
            dictionary of input data and returns the corresponding prediction.
        scorers (list[BaseScorer]): A list of scorer objects used to evaluate the
            predictions for each item in the dataset.
        dataset_id (str): A unique identifier for the dataset being evaluated.
        experiment_tracker (ExperimentTracker): An object for tracking evaluation
            results and metadata during the experiment.
        n_threads (int): The number of threads to use for parallel evaluation.
            Defaults to 1, which performs evaluation sequentially.

    Returns:
        EvalResults: An object containing detailed evaluation results for each item,
            aggregated scores across the dataset, and the associated dataset ID.
    """
    tracer = trace.get_tracer(__name__)

    def evaluate_item(item: EvalItem) -> EvalResult:
        return _evaluate_single_item(
            eval_item=item,
            inference_fn=inference_fn,
            scorers=scorers,
            dataset_id=dataset_id,
            experiment_tracker=experiment_tracker,
            tracer=tracer,
        )

    if n_threads > 1:
        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            results = list(executor.map(evaluate_item, eval_dataset))
    else:
        results = [evaluate_item(item) for item in eval_dataset]

    aggregated_scores = _aggregate_scores(results)

    return EvalResults(
        results=results,
        aggregated_scores=aggregated_scores,
        dataset_id=dataset_id,
    )


def _evaluate_single_item(
    eval_item: EvalItem,
    inference_fn: Callable[[dict[str, Any]], Any],  # noqa: ANN401
    scorers: list[BaseScorer],
    dataset_id: str,
    experiment_tracker: ExperimentTracker,
    tracer: Tracer,
) -> EvalResult:
    """
    Executes the evaluation of a single item by using the provided inference function
    and a set of scoring objects.

    The function performs several steps:
    1. Generates a model response via the provided inference function.
    2. Applies multiple scoring functions to evaluate the model response against the
       inputs and expectations of the evaluation item.
    3. Logs the evaluation results into the experiment tracker, if provided.
    4. Records tracing details for debugging and monitoring purposes.

    Args:
        eval_item (EvalItem): The evaluation item containing input data, expected
            output, and metadata.
        inference_fn (Callable[[dict[str, Any]], Any]): A callable function to
            generate the model's inference results.
        scorers (list[BaseScorer]): A list of scoring objects to compute evaluation
            scores for the model's response.
        dataset_id (str): The identifier of the dataset that this evaluation item
            belongs to.
        experiment_tracker (ExperimentTracker): An object to log evaluation metadata
            and results.
        tracer (Tracer): A tracing object used to generate spans for performance
            monitoring.

    Returns:
        EvalResult: An object containing the evaluation item, the response produced
            by the inference function, computed scores, and the trace ID of the
            spanning context.

    Raises:
        Exception: If any unexpected error occurs during the evaluation process. This
            exception is captured and logged, and the function still returns an
            `EvalResult` object indicating the failure.

    """
    with tracer.start_as_current_span(name="eval_request") as span:
        trace_id = f"{span.context.trace_id:032x}"  # type: ignore

        try:
            with tracer.start_as_current_span(name="inference_fn"):
                model_response = inference_fn(eval_item.inputs)

            all_scores = {}
            with tracer.start_as_current_span(name="eval_scoring") as scoring_span:
                for scorer in scorers:
                    try:
                        scores = _call_scorer(scorer, eval_item, model_response)
                        duplicate_keys = set(scores.keys()) & set(all_scores.keys())
                        if duplicate_keys:
                            warnings.warn(
                                f"Duplicate score keys {duplicate_keys} from "
                                f"scorer '{scorer.get_name()}'. "
                                f"Previous values will be overwritten.",
                                stacklevel=4,
                            )
                        all_scores.update(scores)
                    except Exception as e:
                        scorer_name = scorer.get_name()
                        scoring_span.add_event(
                            f"scorer_error_{scorer_name}",
                            {"error": str(e)},
                        )
                        all_scores[f"__error__{scorer_name}"] = str(e)

                for score_name, score_value in all_scores.items():
                    if isinstance(score_value, int | float | bool):
                        scoring_span.set_attribute(
                            f"eval.score.{score_name}", score_value
                        )

            if experiment_tracker is not None:
                experiment_tracker.log_eval_sample(
                    eval_id=eval_item.id,
                    dataset_id=dataset_id,
                    inputs=eval_item.inputs,
                    outputs={"response": model_response},
                    references={"expected": eval_item.expected_output},
                    scores=all_scores,
                    metadata=eval_item.metadata,
                )

                experiment_tracker.link_eval_sample_to_trace(
                    eval_dataset_id=dataset_id,
                    eval_id=eval_item.id,
                    trace_id=trace_id,
                )

            span.set_status(Status(StatusCode.OK))

            return EvalResult(
                eval_item=eval_item,
                model_response=model_response,
                scores=all_scores,
                trace_id=trace_id,
            )

        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("eval.error", str(e))

            return EvalResult(
                eval_item=eval_item,
                model_response=None,
                scores={"error": str(e)},
                trace_id=trace_id,
            )


def _aggregate_scores(results: list[EvalResult]) -> dict[str, float | int]:
    """
    Aggregates scores from a list of evaluation results into a dictionary of calculated
    metrics.

    The function processes a list of `EvalResult` objects and computes statistical
    aggregations (mean, minimum, maximum, count) for each score key found in the
    results, excluding those that represent errors. Additionally, it calculates the
    total number of items and the number of successful items (those without errors).

    Args:
        results (list[EvalResult]): A list of evaluation result objects, where each
            object contains a `scores` dictionary holding score metrics and their
            corresponding values.

    Returns:
        dict[str, float | int]: A dictionary containing aggregated statistics for each
        score metric, along with metadata like the total number of items and the number
        of successful items.
    """
    if not results:
        return {}

    score_names = set()
    for result in results:
        score_names.update(result.scores.keys())

    aggregated: dict[str, float | int] = {}

    for score_name in score_names:
        if score_name == "error" or score_name.startswith("__error__"):
            continue

        values = []
        for result in results:
            value = result.scores.get(score_name)
            if isinstance(value, bool | int | float):
                values.append(float(value) if isinstance(value, bool) else value)

        if values:
            aggregated[f"{score_name}_mean"] = sum(values) / len(values)
            aggregated[f"{score_name}_min"] = min(values)
            aggregated[f"{score_name}_max"] = max(values)
            aggregated[f"{score_name}_count"] = len(values)

    aggregated["total_items"] = len(results)
    aggregated["successful_items"] = sum(1 for r in results if "error" not in r.scores)

    return aggregated
