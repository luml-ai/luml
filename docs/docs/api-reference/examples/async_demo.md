---
title: async_demo.py
sidebar_position: 11
description: "The basic flow on the async client, in one function"
---

The basic flow on the async client.

`AsyncLumlClient` mirrors `LumlClient` call for call: every method of the
sync client exists on the async one with the same arguments and the same
answers, only awaited. The per-resource files in this directory show the calls
in detail; this file runs through the basic flow once, top to bottom.

```python
import asyncio

from luml_api import ArtifactType, AsyncLumlClient, CollectionType

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
COLLECTION_ID = "0199c455-21ee-74c6-b747-19a82f1a1e75"
DATASET_ID = "0199c455-21ee-74c6-b747-19a82f1a1e80"
MODEL_IDS = [
    "0199c455-21ee-74c6-b747-19a82f1a1e90",
    "0199c455-21ee-74c6-b747-19a82f1a1e91",
    "0199c455-21ee-74c6-b747-19a82f1a1e92",
]

# Reads LUML_API_KEY and LUML_BASE_URL from the environment when they are not given
luml = AsyncLumlClient(api_key="luml_your_api_key_here")


async def main() -> None:
    # The async client takes no defaults in its constructor: they are resolved
    # with one awaited call, by name or by id
    await luml.setup_config(
        organization=ORGANIZATION_ID,
        orbit=ORBIT_ID,
        collection=COLLECTION_ID,
    )
    print(luml.organization, luml.orbit, luml.collection)

    # Organizations the API key has access to
    organizations = await luml.organizations.list()
    print(f"Organizations: {organizations}")

    # A bucket is registered once per organization and attached to orbits
    bucket_secret = await luml.bucket_secrets.create(
        endpoint="s3.amazonaws.com",
        bucket_name="my-ml-artifacts-bucket",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        secure=True,
        region="us-east-1",
    )
    print(f"Bucket secret: {bucket_secret}")

    # An orbit on that bucket, and a collection of models inside it
    orbit = await luml.orbits.create(
        name="ML Production Orbit",
        bucket_secret_id=bucket_secret.id,
    )
    print(f"Orbit: {orbit}")

    collection = await luml.collections.create(
        name="Production artifacts",
        description="Trained artifacts ready for production deployment",
        type=CollectionType.MODEL,
        tags=["production", "ml", "artifacts"],
    )
    print(f"Collection: {collection}")

    # Upload a model, recording the dataset it was trained on
    model = await luml.artifacts.upload(
        file_path="/path/to/your/artifact.fnnx",
        name="Customer Churn Predictor",
        description="XGBoost artifact predicting customer churn probability",
        tags=["xgboost", "churn", "production"],
        lineage_inputs=[DATASET_ID],
        collection_id=collection.id,
    )
    print(f"Uploaded: {model}")

    models = await luml.artifacts.list(types=[ArtifactType.MODEL], search="churn")
    print(f"Churn models: {models}")

    download_url = await luml.artifacts.download_url(model.id)
    print(f"Download URL: {download_url}")

    # The lineage graph around the model
    graph = await luml.artifacts.get_lineage(model.id)
    print(f"{len(graph.nodes)} nodes, {len(graph.edges)} edges")

    # Where async pays off: independent requests run at the same time. The
    # direct neighbours of many artifacts arrive together instead of one by one
    graphs = await asyncio.gather(
        *(luml.artifacts.get_lineage(model_id, depth=1) for model_id in MODEL_IDS)
    )
    for model_id, model_graph in zip(MODEL_IDS, graphs, strict=True):
        print(f"{model_id}: {len(model_graph.edges)} connections")

    # The model becomes the next version of its track and goes to production
    track = await luml.tracks.create(
        name="churn-model",
        artifact_type=ArtifactType.MODEL,
        stages=["dev", "staging", "production"],
    )
    entry = await luml.tracks.add_artifact(str(track.id), model.id, stage="dev")
    promoted = await luml.tracks.update_artifact(
        str(track.id), str(entry.id), stage="production", force=True
    )
    print(f"v{promoted.version} of {track.name} is in {promoted.stage_name}")

    # Deployments of the orbit, and the monitoring of one of them: the sections
    # are independent reads, so a report fetches the ones it needs at once
    deployments = await luml.deployments.list()
    print(f"Deployments: {deployments}")

    monitoring = await luml.deployments.monitoring("My Deployment")
    overview, runtime, alerts = await asyncio.gather(
        monitoring.overview(window="7d"),
        monitoring.runtime(window="24h"),
        monitoring.alerts(window="7d", severity="critical"),
    )
    print(f"Overview: {overview}")
    print(f"Runtime: {runtime}")
    print(f"Alerts: {alerts}")


if __name__ == "__main__":
    asyncio.run(main())
```
