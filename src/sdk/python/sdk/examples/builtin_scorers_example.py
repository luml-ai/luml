# ruff: noqa: ANN001, ANN201
"""Example showing built-in LLM-as-judge scorers alongside custom scorers.

Prerequisites:
    pip install luml_sdk[llm]
    export OPENAI_API_KEY=sk-...

The built-in scorers use OpenAI's gpt-4.1-mini by default (temperature=0).
To use a different model or provider, inject a custom client:
    Relevancy(client=OpenAIClient(model="gpt-4.1"))
"""

from openai import OpenAI

from luml.experiments.evaluation import EvalItem, unsupervised_scorer
from luml.experiments.evaluation.evaluate import evaluate
from luml.experiments.evaluation.scorers.builtin import (
    Completeness,
    Correctness,
    Relevancy,
)
from luml.experiments.tracing import instrument_openai
from luml.experiments.tracker import ExperimentTracker

tracker = ExperimentTracker()
client = OpenAI()

# step 1: define an evaluation dataset
eval_dataset = [
    EvalItem(
        id="eval_201",
        inputs={
            "question": "What is retrieval-augmented generation (RAG)?",
        },
        expected_output={
            "expected_facts": [
                "RAG combines retrieval with generation",
                "RAG reduces hallucinations",
            ],
        },
        metadata={"difficulty": "medium", "topic": "nlp"},
    ),
    EvalItem(
        id="eval_202",
        inputs={
            "question": "What are the three primary colors in the RGB model?",
        },
        expected_output={
            "expected_facts": ["Red", "Green", "Blue"],
        },
        metadata={"difficulty": "easy", "topic": "art"},
    ),
    EvalItem(
        id="eval_203",
        inputs={
            "question": "Explain the benefits of RAG and list at least two.",
        },
        expected_output={
            "expected_facts": [
                "Reduces hallucinations",
                "Grounds responses in retrieved documents",
            ],
        },
        metadata={"difficulty": "medium", "topic": "nlp"},
    ),
]


# step 2: define a custom scorer to mix with built-in scorers
@unsupervised_scorer
def is_non_empty(inputs, output):
    return bool(output and str(output).strip())


# step 3: llm call function
def inference_fn(inputs: dict) -> str:
    prompt = inputs["question"]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


tracker.enable_tracing()
instrument_openai()
tracker.start_experiment(name="builtin_scorers_eval")

# step 4: evaluation with built-in + custom scorers
results = evaluate(
    n_threads=3,
    eval_dataset=eval_dataset,
    inference_fn=inference_fn,
    scorers=[
        Relevancy(),
        Correctness(),
        Completeness(),
        is_non_empty,
    ],
    dataset_id="qa_builtin_v1",
    experiment_tracker=tracker,
)

tracker.end_experiment()

print("=== Per-item scores ===")
for r in results.results:
    print(f"  {r.eval_item.id}: {r.scores}")

print("\n=== Aggregated scores ===")
for k, v in sorted(results.aggregated_scores.items()):
    print(f"  {k}: {v}")
