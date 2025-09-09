from fastapi import APIRouter, Depends, Request, status

from dataforce_studio.handlers.bucket_secrets import BucketSecretHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.bucket_secrets import (
    BucketSecretCreateIn,
    BucketSecretOut,
    BucketSecretUpdate,
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
    request: Request, organization_id: int
) -> list[BucketSecretOut]:
    return await bucket_secret_handler.get_organization_bucket_secrets(
        request.user.id, organization_id
    )


@bucket_secrets_router.post(
    "", responses=endpoint_responses, response_model=BucketSecretOut
)
async def create_bucket_secret(
    request: Request, organization_id: int, secret: BucketSecretCreateIn
) -> BucketSecretOut:
    return await bucket_secret_handler.create_bucket_secret(
        request.user.id, organization_id, secret
    )


@bucket_secrets_router.get(
    "/{secret_id}", responses=endpoint_responses, response_model=BucketSecretOut
)
async def get_bucket_secret(
    request: Request, organization_id: int, secret_id: int
) -> BucketSecretOut:
    return await bucket_secret_handler.get_bucket_secret(
        request.user.id, organization_id, secret_id
    )


@bucket_secrets_router.patch(
    "/{secret_id}", responses=endpoint_responses, response_model=BucketSecretOut
)
async def update_bucket_secret(
    request: Request, organization_id: int, secret_id: int, secret: BucketSecretUpdate
) -> BucketSecretOut:
    return await bucket_secret_handler.update_bucket_secret(
        request.user.id, organization_id, secret_id, secret
    )


@bucket_secrets_router.delete(
    "/{secret_id}", responses=endpoint_responses, status_code=status.HTTP_204_NO_CONTENT
)
async def delete_bucket_secret(
    request: Request, organization_id: int, secret_id: int
) -> None:
    await bucket_secret_handler.delete_bucket_secret(
        request.user.id, organization_id, secret_id
    )
