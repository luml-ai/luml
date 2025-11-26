from fastapi import APIRouter, Depends

from dataforce_studio.handlers.bucket_secrets import BucketSecretHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.bucket_secrets import (
    BucketSecretCreateIn,
    BucketSecretUrls,
)
from dataforce_studio.schemas.storage import (
    BucketMultipartUpload,
    MultiPartUploadDetails,
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
    return await bucket_secret_handler.generate_bucket_urls(secret)


@bucket_secret_urls_router.post(
    "/upload/multipart",
    responses=endpoint_responses,
    response_model=MultiPartUploadDetails,
)
async def get_bucket_multipart_urls(
    data: BucketMultipartUpload,
) -> MultiPartUploadDetails:
    return await bucket_secret_handler.get_bucket_multipart_urls(data)
