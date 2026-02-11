
from luml.api import LumlClient
from luml.api._types import CollectionType, ArtifactStatus

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
        bucket_name="my-ml-artifacts-bucket",
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
    secret = luml.bucket_secrets.get("my-ml-artifacts-bucket")
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
    # Create a artifact collection
    collection = luml.collections.create(
        name="Production artifacts",
        description="Trained artifacts ready for production deployment",
        type=CollectionType.MODEL,
        tags=["production", "ml", "artifacts"],
    )
    print(f"Created collection: {collection}")

    # Get default collection
    default_collection = luml.collections.get()
    print(f"Get Default Collection Details: {default_collection}")

    # Get collection by name
    collection_by_name = luml.collections.get("Production artifacts")
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
        description="Updated: Production-ready ML artifacts",
    )
    print(f"Updated collection: {updated_collection}")

    # Delete collection
    luml.collections.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")


def demo_artifacts() -> None:
    # Create new artifact artifact record with upload URL
    artifact_created = luml.artifacts.create(
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
    print(f"Created artifact: {artifact_created}")

    # List all artifact artifacts in the collection
    artifacts = luml.artifacts.list()
    print(f"All artifacts in collection: {artifacts}")

    # Get artifact by ID
    artifact_by_id = luml.artifacts.get("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"artifact by id: {artifact_by_id}")

    # Get artifact by name
    artifact_by_name = luml.artifacts.get("Customer Churn Predictor")
    print(f"artifact by name: {artifact_by_name}")

    # Get artifact from specific collection
    artifact_by_id_collection = luml.artifacts.get(
        "0199c455-21ee-74c6-b747-19a82f1a1e75",
        collection_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
    )
    print(f"artifact by id: {artifact_by_id_collection}")

    # Update artifact metadata
    updated_artifact = luml.artifacts.update(
        artifact_id="0199c455-21ee-74c6-b747-19a82f1a1e75",
        description="Updated: Advanced churn prediction artifact",
        tags=["xgboost", "churn", "production", "v2.1"],
        status=ArtifactStatus.UPLOADED,
    )
    print(f"Updated artifact: {updated_artifact}")

    # Get download URL
    download_url = luml.artifacts.download_url(
        "0199c455-21ee-74c6-b747-19a82f1a1e75"
    )
    print(f"artifact Download URL: {download_url}")

    # Get delete URL
    delete_url = luml.artifacts.delete_url("0199c455-21ee-74c6-b747-19a82f1a1e75")
    print(f"artifact Delete URL: {delete_url}")

    # Upload a artifact file (example - file should exist)
    uploaded_artifact = luml.artifacts.upload(
        file_path="/path/to/your/artifact.dfs",
        name="Customer Churn Predictor",
        description="XGBoost artifact predicting customer churn probability",
        tags=["xgboost", "churn", "production"],
    )
    print(f"Uploaded artifact: {uploaded_artifact}")

    # Download artifact
    luml.artifacts.download("0199c455-21ee-74c6-b747-19a82f1a1e75", "output.dfs")

    # Delete artifact permanently
    luml.artifacts.delete("0199c455-21ee-74c6-b747-19a82f1a1e75")


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
    demo_artifacts()
