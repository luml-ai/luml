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

Lumlflow bundles the LUML SDK (`luml`), so you can start tracking experiments right away:

```python
from luml.experiments.tracker import ExperimentTracker

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

# Log metrics over training steps
for step, (loss, acc) in enumerate(train()):
    tracker.log_dynamic("loss", loss, step=step)
    tracker.log_dynamic("accuracy", acc, step=step)

# Log the trained model
tracker.log_model(model, name="gbm_final", inputs=X_train)

# End the experiment
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
lumlflow ui --host 0.0.0.0          # Bind to all interfaces
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
- **Evaluations (Evals)** — record evaluation results and comparisons
- **Traces** — capture step-by-step execution details for deeper analysis
- **Attachments** — save artifacts like datasets, plots, or logs

All of this is accessible through an interactive web UI where you can explore experiments, analyze metrics, inspect traces, and compare results.

[placeholder for screenshot]

### Annotations

Add annotations to evaluation samples and trace spans to capture feedback, expectations, or manual scores.

Use annotations to review experiment quality, document insights, or collaborate with teammates by leaving structured notes with optional rationale.

[placeholder for screenshot]

### Experiment Groups

Organize related experiments into groups for easier navigation and comparison.


### Uploading to LUML

Use your API key to upload experiments and models from your local environment to the LUML platform.

This allows you to move from local experimentation to shared cloud storage, making it easier to collaborate, persist results, and manage models centrally.


## Requirements

- Python 3.12+
