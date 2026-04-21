# LUMLFlow Quickstart

LUMLFlow is a local experiment tracking UI for viewing metrics, parameters, models, traces, and evaluation results logged by the LUML SDK. This guide walks through a minimal workflow: training a scikit-learn model, running an experiment, logging metrics and the model, then launching LUMLFlow to inspect the results.

*Note: LUMLFlow runs entirely on your machine. It reads experiment data from a local SQLite database created by the `ExperimentTracker` — no cloud account or API key is required.*

## Setup

Install the LUML SDK and scikit-learn:

```bash
pip install luml-sdk scikit-learn numpy 
```

*Note: the SDK requires Python 3.12 or later.*

## Train a Model

The example below trains a decision tree classifier on synthetic data. Any scikit-learn model works the same way.

```python
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score

# Synthetic dataset
X = np.random.rand(500, 5)
y = (X[:, 0] + X[:, 1] > 1).astype(int)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Train
model = DecisionTreeClassifier(max_depth=5, min_samples_split=10)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
```

## Run an Experiment

Create an `ExperimentTracker` pointing at a local SQLite database. This is the same database that LUMLFlow will read from later.

```python
from luml.experiments.tracker import ExperimentTracker

tracker = ExperimentTracker("sqlite://./my_experiments")

exp_id = tracker.start_experiment(
    name="decision_tree_v1",
    group="classification",
    tags=["decision_tree", "baseline"],
)
```

## Log Metrics

Log hyperparameters as static values and evaluation scores as dynamic values. Static values appear as key–value pairs in LUMLFlow's parameter table. Dynamic values are plotted as time-series charts.

```python
# Hyperparameters
tracker.log_static("max_depth", 5)
tracker.log_static("min_samples_split", 10)
tracker.log_static("test_size", 0.2)

# Evaluation metrics
tracker.log_dynamic("accuracy", accuracy, step=0)
tracker.log_dynamic("precision", precision, step=0)
tracker.log_dynamic("recall", recall, step=0)
```

For iterative training (e.g. incrementally adding trees or running multiple epochs), log metrics at each step to produce a training curve.

```python
for step in range(10):
    # ... train one more iteration ...
    tracker.log_dynamic("accuracy", accuracy, step=step)
```

## Log the Model

`log_model` serializes the trained model and attaches it to the experiment. The SDK auto-detects the framework (scikit-learn, XGBoost, LightGBM, CatBoost, LangGraph) from the model object. Pass `inputs` so the SDK can infer the input/output schema.

```python
model_ref = tracker.log_model(
    model,
    name="decision_tree_classifier",
    flavor="sklearn",
    inputs=X_train,
    experiment_id=exp_id,
    tags=["baseline"],
)
```

Close the experiment when all logging is done.

```python
tracker.end_experiment(exp_id)
```

### Using the Tracker as a Context Manager

As an alternative to calling `start_experiment` and `end_experiment` explicitly, the tracker can be used as a context manager. The experiment is started on entry and closed automatically on exit, including when an exception is raised inside the block.

```python
with tracker.experiment(
    name="decision_tree_v1",
    group="classification",
    tags=["decision_tree", "baseline"],
) as exp_id:
    tracker.log_static("max_depth", 5)
    tracker.log_dynamic("accuracy", accuracy, step=0)

    model_ref = tracker.log_model(
        model,
        name="decision_tree_classifier",
        flavor="sklearn",
        inputs=X_train,
        experiment_id=exp_id,
    )
```

This form is optional. The explicit `start_experiment` / `end_experiment` pattern remains supported and is useful when the experiment lifecycle does not map cleanly to a single block of code.

## View in LUMLFlow

Launch LUMLFlow from the directory that contains your experiment database.

```bash
lumlflow ui
```

By default, LUMLFlow reads from `sqlite://./experiments` and opens a browser at `http://localhost:5000`. To point it at a different database or port:

```bash
lumlflow ui --path sqlite://./my_experiments --port 8080
```

<!-- TODO: screenshot of LUMLFlow experiments list -->

The experiments list shows all recorded runs with their names, groups, tags, and status. Click an experiment to open its detail view.

<!-- TODO: screenshot of experiment detail view showing parameters table and metrics charts -->

The detail view displays static parameters as a table and dynamic metrics as interactive charts. The model tab shows the logged model with its inferred schema.

<!-- TODO: screenshot of model tab -->

## Complete Example

```python
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
from luml.experiments.tracker import ExperimentTracker

# Data
X = np.random.rand(500, 5)
y = (X[:, 0] + X[:, 1] > 1).astype(int)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Experiment
tracker = ExperimentTracker("sqlite://./my_experiments")
exp_id = tracker.start_experiment(
    name="decision_tree_v1",
    group="classification",
    tags=["decision_tree", "baseline"],
)

# Hyperparameters
tracker.log_static("max_depth", 5)
tracker.log_static("min_samples_split", 10)
tracker.log_static("test_size", 0.2)

# Train
model = DecisionTreeClassifier(max_depth=5, min_samples_split=10)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)

tracker.log_dynamic("accuracy", accuracy, step=0)
tracker.log_dynamic("precision", precision, step=0)
tracker.log_dynamic("recall", recall, step=0)

# Log model
model_ref = tracker.log_model(
    model,
    name="decision_tree_classifier",
    flavor="sklearn",
    inputs=X_train,
    experiment_id=exp_id,
    tags=["baseline"],
)

# Done
tracker.end_experiment(exp_id)

print("Experiment logged. Run 'lumlflow ui --path sqlite://./my_experiments' to view.")
```
