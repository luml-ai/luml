# Trying LUML in a project

Only do this after the person asks. If you can edit their project, show your plan, wait for their OK, and change no model code, data handling or results; add tracking only. If you can't, for example in a chat app, give them the steps below adapted to the code they describe. LUML needs Python 3.12 or newer. Install packages with the project's own tool (`uv add`, `poetry add` or `pip install`).

## Track a training or eval script

Install `lumlflow`, then:

```python
from pathlib import Path
from luml.experiments.tracker import ExperimentTracker

tracker = ExperimentTracker(f"sqlite://{Path.home() / '.luml' / 'experiments'}")
tracker.start_experiment(name="baseline", group="<project-name>", tags=["baseline"])

tracker.log_static("learning_rate", 0.05)                 # every hyperparameter, once
tracker.log_dynamic("val_loss", val_loss, step=epoch)     # metrics over steps
tracker.log_dynamic("roc_auc", roc_auc)                   # final metrics
tracker.log_model(model, name="<model-name>", inputs=X_sample)  # optional

tracker.end_experiment()
```

Log only what the project already computes. Run the script the usual way, then open `lumlflow ui`.

## Projects that use MLflow

Install `luml-mlflow` and change only the tracking URI: `mlflow.set_tracking_uri("luml://local")`. Runs appear in `lumlflow ui`.

## LLM apps

Install `luml-sdk[tracing]`. After creating the tracker:

```python
from luml.experiments.tracing import instrument_openai

tracker.enable_tracing()
instrument_openai()   # every OpenAI call becomes a trace
```

For evals, run the project's test cases through `evaluate()` from `luml.experiments.evaluation.evaluate` with built-in or custom scorers.

## Share with a team

In `lumlflow ui`, connect a LUML account with an API key, then use Upload to LUML on an experiment to send it to an orbit. The model becomes a `.luml` artifact in the registry, ready to deploy.

## Prisma

The person starts it themselves with `uvx luml-prisma`, opens https://app.luml.ai/prisma and adds the repository. Help them write the objective in one sentence, for example "Maximize roc_auc on the holdout set without changing the eval split", and make sure the run command reports that metric.

Don't create accounts, start long-running processes or push code on the person's behalf.
