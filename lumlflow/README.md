# Lumlflow

Local ML experiment tracking and model management.

Lumlflow gives you a lightweight, self-hosted dashboard to track machine learning experiments, organize them into groups, and manage associated models — all running locally with zero cloud dependencies.

## Quickstart

```bash
pip install lumlflow
lumlflow ui
```

This starts the web UI at [http://127.0.0.1:5000](http://127.0.0.1:5000) and opens it in your browser automatically.

## Usage

Lumlflow bundles the LUML SDK (`luml`), so you can start tracking experiments right away.

### Classical ML example

The example below trains a gradient-boosted classifier on the Iris dataset (install `scikit-learn` to run it):

```python
from sklearn.datasets import load_iris
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import train_test_split

from luml.experiments.tracker import ExperimentTracker

X, y = load_iris(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

tracker = ExperimentTracker()

# Start an experiment
tracker.start_experiment(
    name="gbm_baseline",
    group="iris_classification",
    tags=["baseline", "gbm"],
)

# Log hyperparameters
tracker.log_static("n_estimators", 100)
tracker.log_static("learning_rate", 0.1)
tracker.log_static("max_depth", 3)

# Train the model
model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=3)
model.fit(X_train, y_train)

# Log metrics over training steps
for step, probs in enumerate(model.staged_predict_proba(X_test)):
    loss = log_loss(y_test, probs, labels=[0, 1, 2])
    acc = accuracy_score(y_test, probs.argmax(axis=1))
    tracker.log_dynamic("loss", loss, step=step)
    tracker.log_dynamic("accuracy", acc, step=step)

# Log the trained model
tracker.log_model(model, name="gbm_final", inputs=X_train)

# End the experiment
tracker.end_experiment()
```

### LLM example

The example below evaluates an OpenAI model on a small Q&A dataset. Every LLM call is automatically captured as a trace, and each question is logged as an eval sample with a score (install `luml-sdk[tracing]`, `opentelemetry-instrumentation-openai`, and `openai`, then set `OPENAI_API_KEY` to run it):

```python
from openai import OpenAI

from luml.experiments.tracker import ExperimentTracker
from luml.experiments.tracing import instrument_openai

client = OpenAI()

tracker = ExperimentTracker()
tracker.enable_tracing()
instrument_openai()  # auto-trace every OpenAI call as a span

tracker.start_experiment(
    name="qa_gpt4_baseline",
    group="qa_evaluation",
    tags=["baseline", "gpt-4o-mini"],
)

tracker.log_static("model", "gpt-4o-mini")
tracker.log_static("temperature", 0.0)

dataset = [
    {"question": "What is 2 + 2?", "expected": "4"},
    {"question": "What is the capital of France?", "expected": "Paris"},
]

for i, sample in enumerate(dataset):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[{"role": "user", "content": sample["question"]}],
    )
    answer = response.choices[0].message.content.strip()
    correct = sample["expected"].lower() in answer.lower()

    tracker.log_eval_sample(
        eval_id=f"q{i}",
        dataset_id="qa_v1",
        inputs={"question": sample["question"]},
        outputs={"answer": answer},
        references={"expected": sample["expected"]},
        scores={"correct": float(correct)},
    )

tracker.end_experiment()
```

All logged data is stored locally and visible in the web UI launched by `lumlflow ui`.

## Overview

Lumlflow consists of two parts:

- **CLI** — a command-line interface to launch and configure the server
- **Web UI** — a browser-based dashboard for viewing and managing experiments

The server exposes a REST API that the UI consumes, so you can also integrate programmatically.

## CLI Reference

```bash
lumlflow ui                          # Start UI at localhost:5000
lumlflow ui --port 8080              # Custom port
lumlflow ui --host 0.0.0.0           # Bind to all interfaces
lumlflow ui --no-browser             # Don't open browser automatically
lumlflow version                     # Show installed version
```

## Features

### Experiment Tracking

Run your ML experiments locally while seamlessly tracking their progress in a clear, real-time UI.

The platform gives you full visibility into every experiment as it executes. As your code runs, all experiment data is automatically captured and stored, allowing you to monitor progress, inspect intermediate results, and analyze outcomes in a structured way.

Each experiment can be easily identified by its **name** and **tags**, allowing you to quickly find relevant runs, filter them, and organize your workflow.

Each experiment serves as a complete record of a run and can include:

- **Metrics** — track performance over time (accuracy, loss, F1, etc.)
- **Parameters** — log hyperparameters and configuration settings
- **Models** — store produced models and link them to specific runs

![Experiment tracking overview](https://raw.githubusercontent.com/luml-ai/luml/docs/lumlflow-readme/lumlflow/docs/images/exp_track.webp)

![Experiment metrics view](https://raw.githubusercontent.com/luml-ai/luml/docs/lumlflow-readme/lumlflow/docs/images/exp_track1.webp)

- **Evaluations (Evals)** — record evaluation results and comparisons
- **Traces** — capture step-by-step execution details for deeper analysis

![Evaluations view](https://raw.githubusercontent.com/luml-ai/luml/docs/lumlflow-readme/lumlflow/docs/images/evals.webp)

- **Attachments** — save artifacts like datasets, plots, or logs

![Attachments view](https://raw.githubusercontent.com/luml-ai/luml/docs/lumlflow-readme/lumlflow/docs/images/attachments.webp)

All of this is accessible through an interactive web UI where you can explore experiments, analyze metrics, inspect traces, and compare results.

### Annotations

Add annotations to evaluation samples and trace spans to capture feedback, expectations, or manual scores.

Use annotations to review experiment quality, document insights, or collaborate with teammates by leaving structured notes with optional rationale.

Annotations in trace span:

![Annotations in trace span](https://raw.githubusercontent.com/luml-ai/luml/docs/lumlflow-readme/lumlflow/docs/images/trace_ann.webp)

Annotations in eval sample:

![Annotations in eval sample](https://raw.githubusercontent.com/luml-ai/luml/docs/lumlflow-readme/lumlflow/docs/images/eval_ann.webp)

### Experiment Groups

Organize related experiments into groups for easier navigation and comparison.

![Experiment groups list](https://raw.githubusercontent.com/luml-ai/luml/docs/lumlflow-readme/lumlflow/docs/images/groups.webp)

![Experiment groups detail](https://raw.githubusercontent.com/luml-ai/luml/docs/lumlflow-readme/lumlflow/docs/images/groups1.webp)

### Uploading to LUML

Use your API key to upload experiments and models from your local environment to the LUML platform.

This allows you to move from local experimentation to shared cloud storage, making it easier to collaborate, persist results, and manage models centrally.


## Requirements

- Python 3.12+
