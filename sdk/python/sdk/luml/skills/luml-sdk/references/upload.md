# Uploading to the LUML platform without Flow

Flow uploads from its UI. Without Flow, use the platform client `luml_api`
(`pip install luml_api`). Run `python -m luml_api skills show luml-api` for the
client itself.

```python
from luml_api import LumlClient

client = LumlClient(organization="My org", orbit="Research", collection="Churn")
```

`LumlClient()` reads `LUML_API_KEY` from the environment. Never put the key
in code. It connects to `https://api.luml.ai`; set `LUML_BASE_URL` only for a
self-hosted platform.

## What to upload

| Situation | Upload |
| --- | --- |
| One model in the experiment | That model, with the experiment embedded. One artifact. |
| Several models in the experiment | The experiment on its own, then each model with the experiment embedded and the experiment as its lineage input. |
| No model | The experiment on its own. |
| A model saved to your own path, already linked | That file as it is. |

## A logged model

Embed the experiment into a copy, never into the stored model. The stored model
stays clean, and the snapshot is the experiment as it is at upload time.

```python
import shutil
import tempfile
from pathlib import Path

from luml.artifacts.model import ModelReference


def upload_logged_model(tracker, client, model_id, experiment_id, lineage=None):
    model = tracker.get_model(model_id)
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / Path(model.path).name
        shutil.copy2(model.path, copy)
        tracker.link_to_model(ModelReference(str(copy)), experiment_id)
        return client.artifacts.upload(
            file_path=str(copy),
            name=model.name,
            lineage_inputs=lineage,
        )
```

## Several models

```python
from luml import save_experiment

with tempfile.TemporaryDirectory() as directory:
    experiment_file = f"{directory}/experiment.luml"
    save_experiment(tracker, experiment_id, output_path=experiment_file)
    experiment_artifact = client.artifacts.upload(
        file_path=experiment_file, name=tracker.get_experiment_record(experiment_id).name
    )

for model in tracker.get_models(experiment_id):
    upload_logged_model(
        tracker, client, model.id, experiment_id, lineage=[experiment_artifact.id]
    )
```

## Datasets and lineage

Upload a dataset artifact the same way, and pass its artifact id in
`lineage_inputs` when you upload the model trained on it. The registry then
shows which data made which model.

## After uploading

The registry shows the embedded experiment with the model. Collections,
tracks, stages, deployments and monitoring are in the client skill:
`python -m luml_api skills show luml-api`.
