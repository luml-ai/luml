# ruff: noqa: T201
from luml.api import LumlClient
from luml.api._types import CollectionType, ModelArtifactStatus

# Will use LUML API Production url "https://api.luml.ai"
# And search for LUML_API_KEY in .env
luml_simple = LumlClient()

# No default organization, orbit and collection are set
luml_without_defaults = LumlClient(api_key="luml_your_api_key_here")

# Recommended initialization with default resources.
# Resources initialized by their names
luml_with_defaults_names = LumlClient(
    api_key="luml_your_api_key_here",
    organization="My Organization",
    orbit="Default Orbit",
    collection="Default Collection",
)

# Recommended initialization with default resources.
# Resources initialized by their ids
luml = LumlClient(
    api_key="luml_your_api_key_here",
    organization="0199c455-21ec-7c74-8efe-41470e29bae5",
    orbit="0199c455-21ed-7aba-9fe5-5231611220de",
    collection="0199c455-21ee-74c6-b747-19a82f1a1e75",
)


def demo_client_defaults() -> None:
    # Get client defaults ids
    default_organization_id = luml.organization
    default_orbit_id = luml.orbit
    default_collection_id = luml.collection

    print(default_organization_id, default_orbit_id, default_collection_id)

    # Set default resources
    luml.organization = "0199c455-21ec-7c74-8efe-41470e29bae5"
    luml.orbit = "0199c455-21ed-7aba-9fe5-5231611220de"
    luml.collection = "0199c455-21ee-74c6-b747-19a82f1a1e75"

    print(luml.organization, luml.orbit, luml.collection)


def demo_organizations() -> None:
    # List all available organization for user
    all_my_organization = luml.organizations.list()
    print(f"All user organization: {all_my_organization}")

    # Get default organization
    default_org_details = luml.organizations.get()
    print(f"Default organization: {default_org_details}")

    # Get organization by name
    organization_by_name = luml.organizations.get("My Organization")
    print(f"Organization by name: {organization_by_name}")

    # Get organization by id
    organization_by_id = luml.organizations.get("0199c455-21ec-7c74-8efe-41470e29bae5")
    print(f"Organization by id: {organization_by_id}")


def demo_bucket_secrets() -> None:
    # Create a new bucket secret
    bucket_secret = luml.bucket_secrets.create(
        endpoint="s3.amazonaws.com",
        bucket_name="my-ml-models-bucket",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        secure=True,
        region="us-east-1",
    )
    print(f"Created bucket secret: {bucket_secret}")

    # List all bucket secrets
    secrets = luml.bucket_secrets.list()
    print(f"Bucket secrets: {secrets}")

    # Get bucket secret by name
    secret = luml.bucket_secrets.get("my-ml-models-bucket")
    print(f"Bucket secret by name: {secret}")

    # Get bucket secret by id
    secret = luml.bucket_secrets.get("0199c455-21ed-7aba-9fe5-5231611220de")
    print(f"Bucket secret by id: {secret}")

    # Update bucket secret
    updated_secret = luml.bucket_secrets.update(
        secret_id=bucket_secret.id, secure=False, region="us-west-2"
    )
    print(f"Updated bucket secret: {updated_secret}")

    # Delete bucket secret
    luml.bucket_secrets.delete("0199c455-21ed-7aba-9fe5-5231611220de")


def demo_orbits() -> None:
    # Create a new orbit
    orbit = luml.orbits.create(
        name="ML Production Orbit",
        bucket_secret_id="0199c455-21ed-7aba-9fe5-5231611220de",
    )
    print(f"Created orbit: {orbit}")

    # Get Orbit by name
    orbit_by_name = luml.orbits.get("ML Production Orbit")
    print(f"Orbit by name: {orbit_by_name}")

    # Get Orbit by id
    orbit_by_id = luml.orbits.get("0199c455-21ed-7aba-9fe5-5231611220de")
    print(f"Orbit by id: {orbit_by_id}")

    # List all orbits
    orbits = luml.orbits.list()
    print(f"Orbits: {orbits}")

    # Update orbit
    updated_orbit = luml.orbits.update(name="ML Production Environment")
    print(f"Updated orbit: {updated_orbit}")

    # Delete Orbit
    luml.orbits.delete("0199c455-21ed-7aba-9fe5-5231611220de")


def demo_collections() -> None:
    # Create a model collection
    collection = luml.collections.create(
        name="Production Models",
        description="Trained models ready for production deployment",
        collection_type=CollectionType.MODEL,
        tags=["production", "ml", "models"],
    )
    print(f"Created collection: {collection}")

    # Get default collection
    default_collection = luml.collections.get()
    print(f"Get Default Collection Details: {default_collection}")

    # Get collection by name
    collection_by_name = luml.collections.get("Production Models")
    print(f"Collection by name: {collection_by_name}")

    # Get collection by id
    collection_by_id = luml.collections.get("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"Collection by id: {collection_by_id}")

    # List all collections in the orbit
    collections = luml.collections.list()
    print(f"Collection: {collections}")

    # Update collection with new tags
    updated_collection = luml.collections.update(
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        description="Updated: Production-ready ML models",
    )
    print(f"Updated collection: {updated_collection}")

    # Delete collection
    luml.collections.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")


def demo_model_artifacts() -> None:
    # Create new model artifact record with upload URL
    model_created = luml.model_artifacts.create(
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
    models = luml.model_artifacts.list()
    print(f"All models in collection: {models}")

    # Get model by ID
    model_by_id = luml.model_artifacts.get("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"Model by id: {model_by_id}")

    # Get model by name
    model_by_name = luml.model_artifacts.get("Customer Churn Predictor")
    print(f"Model by name: {model_by_name}")

    # Get model from specific collection
    model_by_id_collection = luml.model_artifacts.get(
        "0199c455-21ee-74c6-b747-19a82f1a1e75",
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    )
    print(f"Model by id: {model_by_id_collection}")

    # Update model metadata
    updated_model = luml.model_artifacts.update(
        model_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        description="Updated: Advanced churn prediction model",
        tags=["xgboost", "churn", "production", "v2.1"],
        status=ModelArtifactStatus.UPLOADED,
    )
    print(f"Updated model: {updated_model}")

    # Get download URL
    download_url = luml.model_artifacts.download_url(
        "0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    print(f"Model Download URL: {download_url}")

    # Get delete URL
    delete_url = luml.model_artifacts.delete_url("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"Model Delete URL: {delete_url}")

    # Upload a model file (example - file should exist)
    uploaded_model = luml.model_artifacts.upload(
        file_path="/path/to/your/model.dfs",
        model_name="Customer Churn Predictor",
        description="XGBoost model predicting customer churn probability",
        tags=["xgboost", "churn", "production"],
    )
    print(f"Uploaded model: {uploaded_model}")

    # Download model
    luml.model_artifacts.download("0199c455-21ee-74c6-b747-19a82f1a1e75", "output.dfs")

    # Delete model permanently
    luml.model_artifacts.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")


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
