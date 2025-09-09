from fastapi import APIRouter, Depends

from dataforce_studio.handlers.bucket_secrets import BucketSecretHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.bucket_secrets import (
    BucketSecretCreateIn,
    BucketSecretUrls,
)

bucket_secret_urls_router = APIRouter(
    prefix="/bucket-secrets",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["bucket-secrets"],
)

bucket_secret_handler = BucketSecretHandler()


@bucket_secret_urls_router.post(
    "/urls", responses=endpoint_responses, response_model=BucketSecretUrls
)
async def get_bucket_secret_connection_urls(
    secret: BucketSecretCreateIn,
) -> BucketSecretUrls:
    return await bucket_secret_handler.get_bucket_urls(secret)
