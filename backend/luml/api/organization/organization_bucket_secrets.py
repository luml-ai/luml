from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from luml.handlers.bucket_secrets import BucketSecretHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.bucket_secrets import (
    BucketSecretCreateIn,
    BucketSecretOut,
    BucketSecretUpdate,
    BucketSecretUrls,
)

bucket_secrets_router = APIRouter(
    prefix="/{organization_id}/bucket-secrets",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["organizations-bucket-secrets"],
)

bucket_secret_handler = BucketSecretHandler()


@bucket_secrets_router.get(
    "", responses=endpoint_responses, response_model=list[BucketSecretOut]
)
async def get_organization_bucket_secrets(
    request: Request, organization_id: UUID
) -> list[BucketSecretOut]:
    return await bucket_secret_handler.get_organization_bucket_secrets(
        request.user.id, organization_id
    )


@bucket_secrets_router.post(
    "", responses=endpoint_responses, response_model=BucketSecretOut
)
async def create_bucket_secret(
    request: Request, organization_id: UUID, secret: BucketSecretCreateIn
) -> BucketSecretOut:
    return await bucket_secret_handler.create_bucket_secret(
        request.user.id, organization_id, secret
    )


@bucket_secrets_router.get(
    "/{secret_id}", responses=endpoint_responses, response_model=BucketSecretOut
)
async def get_bucket_secret(
    request: Request, organization_id: UUID, secret_id: UUID
) -> BucketSecretOut:
    return await bucket_secret_handler.get_bucket_secret(
        request.user.id, organization_id, secret_id
    )


@bucket_secrets_router.patch(
    "/{secret_id}", responses=endpoint_responses, response_model=BucketSecretOut
)
async def update_bucket_secret(
    request: Request,
    organization_id: UUID,
    secret_id: UUID,
    secret: BucketSecretUpdate,
) -> BucketSecretOut:
    return await bucket_secret_handler.update_bucket_secret(
        request.user.id, organization_id, secret_id, secret
    )


@bucket_secrets_router.delete(
    "/{secret_id}", responses=endpoint_responses, status_code=status.HTTP_204_NO_CONTENT
)
async def delete_bucket_secret(
    request: Request, organization_id: UUID, secret_id: UUID
) -> None:
    await bucket_secret_handler.delete_bucket_secret(
        request.user.id, organization_id, secret_id
    )


@bucket_secrets_router.post(
    "/{secret_id}/urls", responses=endpoint_responses, response_model=BucketSecretUrls
)
async def get_existing_bucket_secret_connection_urls(
    secret: BucketSecretUpdate,
) -> BucketSecretUrls:
    return await bucket_secret_handler.get_existing_bucket_urls(secret)
