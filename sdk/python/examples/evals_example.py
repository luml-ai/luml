import json
import random

from openai import OpenAI

from luml.experiments.evaluation.evaluate import evaluate
from luml.experiments.evaluation.scorers.base import (
    supervised_scorer,
    unsupervised_scorer,
)
from luml.experiments.evaluation.types import EvalItem
from luml.experiments.tracing import instrument_openai
from luml.experiments.tracker import ExperimentTracker

tracker = ExperimentTracker()
client = OpenAI()

# step 1: define an evaluation dataset
eval_dataset = [
    EvalItem(
        id="eval_101",
        inputs={
            "prompt": "What is the capital of the Netherlands?",
            "context": "Geography",
            "output_keys": ["capital"],
        },
        expected_output={
            "capital": "Amsterdam",
        },
        metadata={"difficulty": "medium", "topic": "geography"},
    ),
    EvalItem(
        id="eval_102",
        inputs={
            "prompt": "What are the three primary colors in the RGB model?",
            "context": "Art",
            "output_keys": ["color_1", "color_2", "color_3"],
        },
        expected_output={
            "color_1": "Red",
            "color_2": "Green",
            "color_3": "Blue",
        },
        metadata={"difficulty": "easy", "topic": "art"},
    ),
    EvalItem(
        id="eval_103",
        inputs={
            "prompt": "Calculate 10 + 5 and 10 - 5",
            "context": "Mathematics",
            "output_keys": ["sum", "difference"],
        },
        expected_output={
            "sum": 15,
            "difference": 5,
        },
        metadata={"difficulty": "easy", "topic": "math"},
    ),
]


# step 2.1: define supervised scorers
@supervised_scorer
def exact_match(inputs, expected_output, output):
    return expected_output == output


@supervised_scorer
def length_ratio(inputs, expected_output, output) -> dict:
    exp_len = len(str(expected_output)) if expected_output else 0
    out_len = len(str(output)) if output else 0
    max_len = max(exp_len, out_len)

    return {
        "length_ratio": min(exp_len, out_len) / max_len if max_len > 0 else 0.0,
        "expected_length": exp_len,
        "output_length": out_len,
    }


# step 2.2: define unsupervised scorers
@unsupervised_scorer
def is_non_empty(inputs, output):
    return bool(output and str(output).strip())


@unsupervised_scorer
def readability_score(inputs, output):
    # Mock: return random score between 0 and 10
    return random.uniform(0, 10)


# step 3: llm call function
def inference_fn(inputs: dict) -> str | dict:
    prompt = inputs["prompt"]
    output_keys = inputs.get("output_keys")

    prompt = (
        f"{prompt}\n\nRespond with a JSON object containing these keys: {output_keys}"
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


tracker.enable_tracing()
instrument_openai()
tracker.start_experiment(name="my_eval")

# step 4: evaluation
results = evaluate(
    n_threads=5,
    eval_dataset=eval_dataset,
    inference_fn=inference_fn,
    scorers=[exact_match, length_ratio, is_non_empty, readability_score],
    dataset_id="simple_qa_v1",
    experiment_tracker=tracker,
)

tracker.end_experiment()
