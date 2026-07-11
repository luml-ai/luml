from falcon import AutoML
from falcon.tabular.tabular_manager import TabularTaskManager
from falcon.task_configurations import get_task_configuration
import numpy as np
from dfs_webworker.constants import (
    PRODUCER,
    TABULAR_CLASSIFICATION,
    TABULAR_REGRESSION,
)
from dfs_webworker.store import Store
from dfs_webworker.utils import success
import pandas as pd

loaded_models = {}


tabular_tasks = {
    TABULAR_CLASSIFICATION: [f"{PRODUCER}::{TABULAR_CLASSIFICATION}:v1"],
    TABULAR_REGRESSION: [f"{PRODUCER}::{TABULAR_REGRESSION}:v1"],
}


def tabular_train(task: str, data: dict, target: str) -> dict:
    if task not in tabular_tasks.keys():
        raise ValueError(
            f"Invalid task {task}. Supported tasks are {tabular_tasks.keys()}"
        )

    m: TabularTaskManager = AutoML(
        task=task,
        train_data=pd.DataFrame(data),
        target=target,
        save_model=False,
        config="PlainLearner",
    )  # type: ignore

    importances = m.get_permutation_importance()  # type: ignore

    fnnx_model = m.save_model(extra_tags=tabular_tasks[task])

    metrics = m._cached_metrics["performance"]

    train_metrics = metrics["train"]
    test_metrics = metrics.get("eval", metrics.get("eval_cv"))

    for k, v in train_metrics.items():
        if hasattr(v, "item"):
            train_metrics[k] = v.item()

    for k, v in test_metrics.items():
        if hasattr(v, "item"):
            test_metrics[k] = v.item()

    out = {}

    if m._eval_set is not None:
        Xe = m._eval_set[0][:100]
        ye = m._eval_set[1][:100]
        predicted_data_type = "test"
    else:
        Xe = m._data[0][:100]
        ye = m._data[1][:100]
        predicted_data_type = "train"

    predictions = m.predict(Xe)
    predictions = np.array(predictions)

    in_features = m.feature_names_to_save
    predicted_data = {fname: Xe[:, i].tolist() for i, fname in enumerate(in_features)}

    predicted_data[target] = ye.tolist()
    predicted_data["<=PREDICTED=>"] = predictions.tolist()

    model_id = Store.save(m)
    out = {
        "model_id": model_id,
        "importances": importances,
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "predicted_data_type": predicted_data_type,
        "predicted_data": predicted_data,
        "model": fnnx_model,
    }
    return success(**out)


def tabular_predict(model_id: str, data: dict) -> dict:
    m = Store.get(model_id)
    predictions = m.predict(pd.DataFrame(data))
    return success(predictions=predictions.tolist())


def tabular_deallocate(model_id: str) -> dict:
    Store.delete(model_id)
    return success()
