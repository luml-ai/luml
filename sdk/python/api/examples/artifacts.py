"""Artifacts: models, datasets and experiments stored in a collection.

``upload`` is the everyday call: it registers the artifact, sends the file to
the bucket and confirms the upload. ``create`` is the first of those steps on
its own, for clients that move the file themselves. Lineage between artifacts
is covered in ``lineage.py``.
"""

from luml_api import (
    ArtifactStatus,
    ArtifactType,
    LumlClient,
    SortOrder,
)

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
COLLECTION_ID = "0199c455-21ee-74c6-b747-19a82f1a1e75"
ARTIFACT_ID = "0199c455-21ee-74c6-b747-19a82f1a1e82"
DATASET_ID = "0199c455-21ee-74c6-b747-19a82f1a1e80"

luml = LumlClient(
    api_key="luml_your_api_key_here",
    organization=ORGANIZATION_ID,
    orbit=ORBIT_ID,
    collection=COLLECTION_ID,
)


def main() -> None:
    # Upload a file from disk into the default collection
    uploaded = luml.artifacts.upload(
        file_path="/path/to/your/artifact.fnnx",
        name="Customer Churn Predictor",
        description="XGBoost artifact predicting customer churn probability",
        tags=["xgboost", "churn", "production"],
    )
    print(f"Uploaded artifact: {uploaded}")

    # Upload into another collection and record what the artifact was produced
    # from; the lineage is written together with the artifact (see lineage.py)
    uploaded_with_lineage = luml.artifacts.upload(
        file_path="/path/to/your/artifact.fnnx",
        name="Customer Churn Predictor v2",
        lineage_inputs=[DATASET_ID],
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e76",
    )
    print(f"Uploaded artifact: {uploaded_with_lineage}")

    # Register an artifact without uploading its file: the response carries the
    # signed upload URL for the file, and the artifact stays in
    # ``pending_upload`` until the upload is confirmed with ``update``
    created = luml.artifacts.create(
        file_name="customer_churn_artifact.fnnx",
        extra_values={"accuracy": 0.95, "precision": 0.92, "recall": 0.88},
        manifest={"version": "1.0", "framework": "xgboost"},
        file_hash="abc123def456",
        file_index={"layer1": (0, 1024), "layer2": (1024, 2048)},
        size=1048576,
        name="Customer Churn Predictor",
        description="XGBoost artifact predicting customer churn probability",
        tags=["xgboost", "churn", "production"],
    )
    print(f"Created artifact: {created}")

    # Everything in the default collection, one page at a time
    artifacts = luml.artifacts.list()
    print(f"All artifacts in collection: {artifacts}")

    # Models only, newest first, matching a search
    models = luml.artifacts.list(
        types=[ArtifactType.MODEL],
        search="churn",
        sort_by="created_at",
        order=SortOrder.DESC,
        limit=20,
    )
    print(f"Churn models: {models}")

    # By id or by name, in the default collection or a named one
    by_id = luml.artifacts.get(ARTIFACT_ID)
    print(f"Artifact by id: {by_id}")

    by_name = luml.artifacts.get("Customer Churn Predictor")
    print(f"Artifact by name: {by_name}")

    from_other_collection = luml.artifacts.get(
        ARTIFACT_ID,
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e76",
    )
    print(f"Artifact from another collection: {from_other_collection}")

    # Change the metadata, or confirm an upload by moving the status
    updated = luml.artifacts.update(
        artifact_id=ARTIFACT_ID,
        description="Updated: Advanced churn prediction artifact",
        tags=["xgboost", "churn", "production", "v2.1"],
        status=ArtifactStatus.UPLOADED,
    )
    print(f"Updated artifact: {updated}")

    # Signed URLs for the file itself
    download_url = luml.artifacts.download_url(ARTIFACT_ID)
    print(f"Artifact download URL: {download_url}")

    delete_url = luml.artifacts.delete_url(ARTIFACT_ID)
    print(f"Artifact delete URL: {delete_url}")

    # Download the file to disk
    luml.artifacts.download(ARTIFACT_ID, "output.fnnx")

    # Delete the artifact
    luml.artifacts.delete(ARTIFACT_ID)


if __name__ == "__main__":
    main()
