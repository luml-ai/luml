# LLM-as-Judge Evaluation with LangGraph

This guide walks through a more involved LUMLFlow experiment than the Quickstart. It builds a small LangGraph QA agent with an LLM-as-judge node, packages the agent as a `.luml` file, runs an evaluation with custom scorers over a dataset, and records parameters, scores, and execution traces to LUMLFlow.

After running the script, the experiment can be inspected in LUMLFlow: parameters, aggregated eval scores, per-sample results, and full OpenTelemetry traces for every inference call.

## Setup

Install all necessary modules:

```bash
pip install luml-sdk lumlflow python-dotenv langgraph langchain-openai opentelemetry-instrumentation-langchain opentelemetry-instrumentation-openai 'wrapt==1.17.0'

export OPENAI_API_KEY=<your key>
```

## Imports and Instrumentation

LangChain/LangGraph spans and OpenAI calls are captured automatically once their instrumentors are enabled. The instrumentors must be activated before the agent is built so that all subsequent calls are traced.

```python
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

load_dotenv()

from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from luml.integrations.langgraph import save_langgraph
from luml.experiments.tracker import ExperimentTracker
from luml.experiments.tracing import instrument_openai
from luml.experiments.evaluation.evaluate import evaluate
from luml.experiments.evaluation.scorers.base import (
    supervised_scorer,
    unsupervised_scorer,
)
from luml.experiments.evaluation.types import EvalItem

LangchainInstrumentor().instrument()
instrument_openai()
```

## Defining the Agent

The agent uses two LLM instances: one for generating answers (with a small amount of creativity) and one for judging answers (deterministic). A refinement threshold controls when low-scoring answers are rewritten.

```python
llm_answerer = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
llm_judge    = ChatOpenAI(model="gpt-4o-mini", temperature=0)

ANSWERER_MODEL = "gpt-4o-mini"
JUDGE_MODEL    = "gpt-4o-mini"
REFINE_THRESHOLD = 6.0
```

The graph state is shared between all nodes. It carries the question, the expected answer, the predicted question type, the produced answer, the judge's verdict, and a flag that prevents infinite refinement loops.

```python
class AgentState(TypedDict):
    question:      str
    expected:      str
    question_type: str     # "fact" | "explanation"
    answer:        str
    judge_output:  str
    judge_score:   float
    refined:       bool
```

## Graph Nodes

The workflow consists of four nodes. The classifier decides whether the question expects a factual or an explanatory answer. The answerer adapts its prompt accordingly. The judge scores the answer against the expected output on a 0–10 scale. The refiner rewrites low-scoring answers a single time.

```python
def classify_node(state: AgentState):
    prompt = (
        f"Classify the following question as either 'fact' or 'explanation'.\n"
        f"Return only one word: fact or explanation.\n\n"
        f"Question: {state['question']}"
    )
    result = llm_answerer.invoke(prompt)
    q_type = "explanation" if "explanation" in result.content.lower() else "fact"
    return {"question_type": q_type, "refined": False}


def answer_node(state: AgentState):
    if state["question_type"] == "explanation":
        prompt = f"Give a clear, educational explanation in 2–3 sentences:\n{state['question']}"
    else:
        prompt = f"Answer the following question concisely in one sentence:\n{state['question']}"
    result = llm_answerer.invoke(prompt)
    return {"answer": result.content}


def judge_node(state: AgentState):
    prompt = (
        f"You are an evaluator.\n"
        f"Compare the model answer to the expected answer and rate it 0–10, where:\n"
        f"  10 = perfectly correct and complete\n"
        f"   0 = completely wrong or missing\n\n"
        f"Question: {state['question']}\n"
        f"Expected answer: {state['expected']}\n"
        f"Model answer: {state['answer']}\n\n"
        f"Return only a single integer between 0 and 10."
    )
    result = llm_judge.invoke(prompt)
    try:
        score = float(result.content.strip())
    except ValueError:
        score = 5.0
    return {"judge_output": result.content, "judge_score": score}


def refine_node(state: AgentState):
    prompt = (
        f"Your previous answer received a low score.\n"
        f"Question: {state['question']}\n"
        f"Your answer: {state['answer']}\n"
        f"Judge feedback score: {state['judge_score']}/10\n\n"
        f"Rewrite the answer to be more accurate and complete."
    )
    result = llm_answerer.invoke(prompt)
    return {"answer": result.content, "refined": True}
```

## Building and Packaging the Graph

A conditional edge after the judge routes to the refiner only when the score falls below the threshold and the answer has not already been refined. The compiled graph is then packaged as a `.luml` file. `save_langgraph` records the environment variables the graph depends on, so the package can later be deployed on a Satellite with the right secrets.

```python
def should_refine(state: AgentState) -> str:
    if state["judge_score"] < REFINE_THRESHOLD and not state["refined"]:
        return "refine"
    return END


workflow = StateGraph(AgentState)
workflow.add_node("classify", classify_node)
workflow.add_node("answer",   answer_node)
workflow.add_node("judge",    judge_node)
workflow.add_node("refine",   refine_node)
workflow.add_edge(START,       "classify")
workflow.add_edge("classify",  "answer")
workflow.add_edge("answer",    "judge")
workflow.add_conditional_edges("judge", should_refine, {"refine": "refine", END: END})
workflow.add_edge("refine",    END)
graph = workflow.compile()

model_ref = save_langgraph(
    graph,
    path="qa_judge_agent.luml",
    env_vars=["OPENAI_API_KEY"],
    manifest_model_name="qa_judge_agent",
    manifest_model_version="1.0.0",
)
```

## Defining Scorers

Scorers are plain functions decorated with `@supervised_scorer` or `@unsupervised_scorer`. A supervised scorer receives the inputs, the expected output, and the model output. An unsupervised scorer receives only the inputs and the output. Each scorer returns a `bool`, `float`, `int`, or `dict`. The `evaluate()` function aggregates these across the dataset.

```python
@supervised_scorer
def exact_match(inputs, expected, output):
    """Binary: does the answer contain the key fact?"""
    return expected.lower().strip(". ") in output.lower()


@supervised_scorer
def keyword_overlap(inputs, expected, output):
    """Fraction of expected keywords present in the answer."""
    expected_words = set(expected.lower().split())
    output_words = set(output.lower().split())
    if not expected_words:
        return 0.0
    return len(expected_words & output_words) / len(expected_words)


@unsupervised_scorer
def answer_length(inputs, output):
    """Penalize very short or very long answers."""
    length = len(output.split())
    if length < 3:
        return 0.0
    if length > 100:
        return 0.5
    return 1.0
```

## Evaluation Dataset

Each `EvalItem` carries an id, an `inputs` dict that will be passed to the inference function, an optional `expected_output` consumed by supervised scorers, and free-form metadata.

```python
DATASET_ID = "qa_judge_v1"

eval_dataset = [
    EvalItem(
        id="sample_0",
        inputs={"question": "What is the capital of France?"},
        expected_output="Paris is the capital of France.",
        metadata={"category": "geography"},
    ),
    EvalItem(
        id="sample_1",
        inputs={"question": "Explain photosynthesis in one sentence."},
        expected_output=(
            "Photosynthesis is the process by which plants use sunlight, water, "
            "and CO2 to produce glucose and oxygen."
        ),
        metadata={"category": "biology"},
    ),
    EvalItem(
        id="sample_2",
        inputs={"question": "Who discovered gravity?"},
        expected_output="Isaac Newton is credited with discovering gravity.",
        metadata={"category": "history"},
    ),
]
```

## Running the Experiment

The tracker is created against a local SQLite database. Calling `enable_tracing()` routes all OpenTelemetry spans produced by the instrumented LangChain and OpenAI calls into the experiment store, so each evaluation sample is linked to its full execution trace.

```python
def run_agent(inputs: dict) -> str:
    result = graph.invoke({
        "question": inputs["question"],
        "expected": "",
    })
    return result["answer"]


tracker = ExperimentTracker("sqlite://./llm_judge_eval_experiments")
tracker.enable_tracing()

exp_id = tracker.start_experiment(
    name="llm_judge_eval",
    group="demo",
    tags=["llm-judge", "evals", "traces", "langgraph"],
)
try:
    tracker.log_static("answerer_model",   ANSWERER_MODEL)
    tracker.log_static("judge_model",      JUDGE_MODEL)
    tracker.log_static("graph_nodes",      ["classify", "answer", "judge", "refine"])
    tracker.log_static("refine_threshold", REFINE_THRESHOLD)

    eval_results = evaluate(
        eval_dataset=eval_dataset,
        inference_fn=run_agent,
        scorers=[exact_match, keyword_overlap, answer_length],
        dataset_id=DATASET_ID,
        experiment_tracker=tracker,
    )

    for key, value in eval_results.aggregated_scores.items():
        tracker.log_static(f"eval_{key}", value)

    tracker.log_model(
        model_ref,
        name="qa_judge_agent",
        flavor="langgraph",
        experiment_id=exp_id,
        tags=["langgraph", "model"],
    )
finally:
    tracker.end_experiment(exp_id)
```

Once the block exits, the experiment is finalized. Launch LUMLFlow against the same database to inspect the results.

```bash
lumlflow ui --path sqlite://./llm_judge_eval_experiments
```

## Complete Script

```python
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

load_dotenv()

from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from luml.integrations.langgraph import save_langgraph
from luml.experiments.tracker import ExperimentTracker
from luml.experiments.tracing import instrument_openai
from luml.experiments.evaluation.evaluate import evaluate
from luml.experiments.evaluation.scorers.base import (
    supervised_scorer,
    unsupervised_scorer,
)
from luml.experiments.evaluation.types import EvalItem

LangchainInstrumentor().instrument()
instrument_openai()

llm_answerer = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
llm_judge    = ChatOpenAI(model="gpt-4o-mini", temperature=0)

ANSWERER_MODEL = "gpt-4o-mini"
JUDGE_MODEL    = "gpt-4o-mini"
REFINE_THRESHOLD = 6.0


class AgentState(TypedDict):
    question:      str
    expected:      str
    question_type: str
    answer:        str
    judge_output:  str
    judge_score:   float
    refined:       bool


def classify_node(state: AgentState):
    prompt = (
        f"Classify the following question as either 'fact' or 'explanation'.\n"
        f"Return only one word: fact or explanation.\n\n"
        f"Question: {state['question']}"
    )
    result = llm_answerer.invoke(prompt)
    q_type = "explanation" if "explanation" in result.content.lower() else "fact"
    return {"question_type": q_type, "refined": False}


def answer_node(state: AgentState):
    if state["question_type"] == "explanation":
        prompt = f"Give a clear, educational explanation in 2–3 sentences:\n{state['question']}"
    else:
        prompt = f"Answer the following question concisely in one sentence:\n{state['question']}"
    result = llm_answerer.invoke(prompt)
    return {"answer": result.content}


def judge_node(state: AgentState):
    prompt = (
        f"You are an evaluator.\n"
        f"Compare the model answer to the expected answer and rate it 0–10, where:\n"
        f"  10 = perfectly correct and complete\n"
        f"   0 = completely wrong or missing\n\n"
        f"Question: {state['question']}\n"
        f"Expected answer: {state['expected']}\n"
        f"Model answer: {state['answer']}\n\n"
        f"Return only a single integer between 0 and 10."
    )
    result = llm_judge.invoke(prompt)
    try:
        score = float(result.content.strip())
    except ValueError:
        score = 5.0
    return {"judge_output": result.content, "judge_score": score}


def refine_node(state: AgentState):
    prompt = (
        f"Your previous answer received a low score.\n"
        f"Question: {state['question']}\n"
        f"Your answer: {state['answer']}\n"
        f"Judge feedback score: {state['judge_score']}/10\n\n"
        f"Rewrite the answer to be more accurate and complete."
    )
    result = llm_answerer.invoke(prompt)
    return {"answer": result.content, "refined": True}


def should_refine(state: AgentState) -> str:
    if state["judge_score"] < REFINE_THRESHOLD and not state["refined"]:
        return "refine"
    return END


workflow = StateGraph(AgentState)
workflow.add_node("classify", classify_node)
workflow.add_node("answer",   answer_node)
workflow.add_node("judge",    judge_node)
workflow.add_node("refine",   refine_node)
workflow.add_edge(START,       "classify")
workflow.add_edge("classify",  "answer")
workflow.add_edge("answer",    "judge")
workflow.add_conditional_edges("judge", should_refine, {"refine": "refine", END: END})
workflow.add_edge("refine",    END)
graph = workflow.compile()

model_ref = save_langgraph(
    graph,
    path="qa_judge_agent.luml",
    env_vars=["OPENAI_API_KEY"],
    manifest_model_name="qa_judge_agent",
    manifest_model_version="1.0.0",
)


@supervised_scorer
def exact_match(inputs, expected, output):
    return expected.lower().strip(". ") in output.lower()


@supervised_scorer
def keyword_overlap(inputs, expected, output):
    expected_words = set(expected.lower().split())
    output_words = set(output.lower().split())
    if not expected_words:
        return 0.0
    return len(expected_words & output_words) / len(expected_words)


@unsupervised_scorer
def answer_length(inputs, output):
    length = len(output.split())
    if length < 3:
        return 0.0
    if length > 100:
        return 0.5
    return 1.0


DATASET_ID = "qa_judge_v1"

eval_dataset = [
    EvalItem(
        id="sample_0",
        inputs={"question": "What is the capital of France?"},
        expected_output="Paris is the capital of France.",
        metadata={"category": "geography"},
    ),
    EvalItem(
        id="sample_1",
        inputs={"question": "Explain photosynthesis in one sentence."},
        expected_output=(
            "Photosynthesis is the process by which plants use sunlight, water, "
            "and CO2 to produce glucose and oxygen."
        ),
        metadata={"category": "biology"},
    ),
    EvalItem(
        id="sample_2",
        inputs={"question": "Who discovered gravity?"},
        expected_output="Isaac Newton is credited with discovering gravity.",
        metadata={"category": "history"},
    ),
]


def run_agent(inputs: dict) -> str:
    result = graph.invoke({
        "question": inputs["question"],
        "expected": "",
    })
    return result["answer"]


tracker = ExperimentTracker("sqlite://./llm_judge_eval_experiments")
tracker.enable_tracing()

exp_id = tracker.start_experiment(
    name="llm_judge_eval",
    group="demo",
    tags=["llm-judge", "evals", "traces", "langgraph"],
)
try:
    tracker.log_static("answerer_model",   ANSWERER_MODEL)
    tracker.log_static("judge_model",      JUDGE_MODEL)
    tracker.log_static("graph_nodes",      ["classify", "answer", "judge", "refine"])
    tracker.log_static("refine_threshold", REFINE_THRESHOLD)

    eval_results = evaluate(
        eval_dataset=eval_dataset,
        inference_fn=run_agent,
        scorers=[exact_match, keyword_overlap, answer_length],
        dataset_id=DATASET_ID,
        experiment_tracker=tracker,
    )

    for key, value in eval_results.aggregated_scores.items():
        tracker.log_static(f"eval_{key}", value)

    tracker.log_model(
        model_ref,
        name="qa_judge_agent",
        flavor="langgraph",
        experiment_id=exp_id,
        tags=["langgraph", "model"],
    )
finally:
    tracker.end_experiment(exp_id)
```
