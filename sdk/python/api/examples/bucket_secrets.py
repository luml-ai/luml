"""Bucket secrets: the object-storage buckets that hold artifact files.

The platform only signs URLs for a bucket; uploads and downloads go straight
from your machine to the bucket. A bucket secret is registered once per
organization and then attached to orbits.
"""

from luml_api import LumlClient

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
BUCKET_SECRET_ID = "0199c455-21ed-7aba-9fe5-5231611220de"

luml = LumlClient(api_key="luml_your_api_key_here", organization=ORGANIZATION_ID)


def main() -> None:
    # Register a bucket
    bucket_secret = luml.bucket_secrets.create(
        endpoint="s3.amazonaws.com",
        bucket_name="my-ml-artifacts-bucket",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        secure=True,
        region="us-east-1",
    )
    print(f"Created bucket secret: {bucket_secret}")

    # All buckets of the organization
    secrets = luml.bucket_secrets.list()
    print(f"Bucket secrets: {secrets}")

    # By bucket name or by id
    by_name = luml.bucket_secrets.get("my-ml-artifacts-bucket")
    print(f"Bucket secret by name: {by_name}")

    by_id = luml.bucket_secrets.get(BUCKET_SECRET_ID)
    print(f"Bucket secret by id: {by_id}")

    # Change the connection settings
    updated = luml.bucket_secrets.update(
        secret_id=bucket_secret.id, secure=False, region="us-west-2"
    )
    print(f"Updated bucket secret: {updated}")

    # Remove the registration (the bucket and its files are not touched)
    luml.bucket_secrets.delete(BUCKET_SECRET_ID)


if __name__ == "__main__":
    main()
