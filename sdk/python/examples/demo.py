# ruff: noqa: T201
from dataforce import DataForceClient
from dataforce.api._types import CollectionType, ModelArtifactStatus

# Will use DataForce API Production url "https://api.dataforce.studio"
# And search for DFS_API_KEY in .env
dfs_simple = DataForceClient()

# No default organization, orbit and collection are set
dfs_without_defaults = DataForceClient(api_key="dfs_your_api_key_here")

# Recommended initialization with default resources.
# Resources initialized by their names
dfs_with_defaults_names = DataForceClient(
    api_key="dfs_your_api_key_here",
    organization="My Organization",
    orbit="Default Orbit",
    collection="Default Collection",
)

# Recommended initialization with default resources.
# Resources initialized by their ids
dfs = DataForceClient(
    api_key="dfs_your_api_key_here",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75",
)


def demo_client_defaults() -> None:
    # Get client defaults ids
    default_organization_id = dfs.organization
    default_orbit_id = dfs.orbit
    default_collection_id = dfs.collection

    print(default_organization_id, default_orbit_id, default_collection_id)

    # Set default resources
    dfs.organization = "0199c455-21ec-7c74-8efe-41470e29bae5"
    dfs.orbit = "0199c455-21ed-7aba-9fe5-5231611220de"
    dfs.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"

    print(dfs.organization, dfs.orbit, dfs.collection)


def demo_organizations() -> None:
    # List all available organization for user
    all_my_organization = dfs.organizations.list()
    print(f"All user organization: {all_my_organization}")

    # Get default organization
    default_org_details = dfs.organizations.get()
    print(f"Default organization: {default_org_details}")

    # Get organization by name
    organization_by_name = dfs.organizations.get("My Organization")
    print(f"Organization by name: {organization_by_name}")

    # Get organization by id
    organization_by_id = dfs.organizations.get("0199c455-21ec-7c74-8efe-41470e29bae5")
    print(f"Organization by id: {organization_by_id}")


def demo_bucket_secrets() -> None:
    # Create a new bucket secret
    bucket_secret = dfs.bucket_secrets.create(
        endpoint="s3.amazonaws.com",
        bucket_name="my-ml-models-bucket",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        secure=True,
        region="us-east-1",
    )
    print(f"Created bucket secret: {bucket_secret}")

    # List all bucket secrets
    secrets = dfs.bucket_secrets.list()
    print(f"Bucket secrets: {secrets}")

    # Get bucket secret by name
    secret = dfs.bucket_secrets.get("my-ml-models-bucket")
    print(f"Bucket secret by name: {secret}")

    # Get bucket secret by id
    secret = dfs.bucket_secrets.get("0199c455-21ed-7aba-9fe5-5231611220de")
    print(f"Bucket secret by id: {secret}")

    # Update bucket secret
    updated_secret = dfs.bucket_secrets.update(
        secret_id=bucket_secret.id, secure=False, region="us-west-2"
    )
    print(f"Updated bucket secret: {updated_secret}")

    # Delete bucket secret
    dfs.bucket_secrets.delete("0199c455-21ed-7aba-9fe5-5231611220de")


def demo_orbits() -> None:
    # Create a new orbit
    orbit = dfs.orbits.create(
        name="ML Production Orbit",
        bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    print(f"Created orbit: {orbit}")

    # Get Orbit by name
    orbit_by_name = dfs.orbits.get("ML Production Orbit")
    print(f"Orbit by name: {orbit_by_name}")

    # Get Orbit by id
    orbit_by_id = dfs.orbits.get("0199c455-21ed-7aba-9fe5-5231611220de")
    print(f"Orbit by id: {orbit_by_id}")

    # List all orbits
    orbits = dfs.orbits.list()
    print(f"Orbits: {orbits}")

    # Update orbit
    updated_orbit = dfs.orbits.update(name="ML Production Environment")
    print(f"Updated orbit: {updated_orbit}")

    # Delete Orbit
    dfs.orbits.delete("0199c455-21ed-7aba-9fe5-5231611220de")


def demo_collections() -> None:
    # Create a model collection
    collection = dfs.collections.create(
        name="Production Models",
        description="Trained models ready for production deployment",
        collection_type=CollectionType.MODEL,
        tags=["production", "ml", "models"],
    )
    print(f"Created collection: {collection}")

    # Get default collection
    default_collection = dfs.collections.get()
    print(f"Get Default Collection Details: {default_collection}")

    # Get collection by name
    collection_by_name = dfs.collections.get("Production Models")
    print(f"Collection by name: {collection_by_name}")

    # Get collection by id
    collection_by_id = dfs.collections.get("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"Collection by id: {collection_by_id}")

    # List all collections in the orbit
    collections = dfs.collections.list()
    print(f"Collection: {collections}")

    # Update collection with new tags
    updated_collection = dfs.collections.update(
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        description="Updated: Production-ready ML models",
    )
    print(f"Updated collection: {updated_collection}")

    # Delete collection
    dfs.collections.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")


def demo_model_artifacts() -> None:
    # Create new model artifact record with upload URL
    model_created = dfs.model_artifacts.create(
        file_name="customer_churn_model.fnnx",
        metrics={"accuracy": 0.95, "precision": 0.92, "recall": 0.88},
        manifest={"version": "1.0", "framework": "xgboost"},
        file_hash="abc123def456",
        file_index={"layer1": (0, 1024), "layer2": (1024, 2048)},
        size=1048576,
        model_name="Customer Churn Predictor",
        description="XGBoost model predicting customer churn probability",
        tags=["xgboost", "churn", "production"],
    )
    print(f"Created model: {model_created}")

    # List all model artifacts in the collection
    models = dfs.model_artifacts.list()
    print(f"All models in collection: {models}")

    # Get model by ID
    model_by_id = dfs.model_artifacts.get("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"Model by id: {model_by_id}")

    # Get model by name
    model_by_name = dfs.model_artifacts.get("Customer Churn Predictor")
    print(f"Model by name: {model_by_name}")

    # Get model from specific collection
    model_by_id_collection = dfs.model_artifacts.get(
        "0199c455-21ee-74c6-b747-19a82f1a1e75",
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    )
    print(f"Model by id: {model_by_id_collection}")

    # Update model metadata
    updated_model = dfs.model_artifacts.update(
        model_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        description="Updated: Advanced churn prediction model",
        tags=["xgboost", "churn", "production", "v2.1"],
        status=ModelArtifactStatus.UPLOADED,
    )
    print(f"Updated model: {updated_model}")

    # Get download URL
    download_url = dfs.model_artifacts.download_url(
        "0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    print(f"Model Download URL: {download_url}")

    # Get delete URL
    delete_url = dfs.model_artifacts.delete_url("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"Model Delete URL: {delete_url}")

    # Upload a model file (example - file should exist)
    uploaded_model = dfs.model_artifacts.upload(
        file_path="/path/to/your/model.dfs",
        model_name="Customer Churn Predictor",
        description="XGBoost model predicting customer churn probability",
        tags=["xgboost", "churn", "production"],
    )
    print(f"Uploaded model: {uploaded_model}")

    # Download model
    dfs.model_artifacts.download("0199c455-21ee-74c6-b747-19a82f1a1e75", "output.dfs")

    # Delete model permanently
    dfs.model_artifacts.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")


if __name__ == "__main__":
    print("\n--------------------------------\n")
    demo_client_defaults()
    print("\n--------------------------------\n")
    demo_organizations()
    print("\n--------------------------------\n")
    demo_bucket_secrets()
    print("\n--------------------------------\n")
    demo_orbits()
    print("\n--------------------------------\n")
    demo_collections()
    print("\n--------------------------------\n")
    demo_model_artifacts()
