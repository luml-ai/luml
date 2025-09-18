from pydantic import BaseModel, HttpUrl


class InferenceAccessIn(BaseModel):
    api_key: str


class InferenceAccessOut(BaseModel):
    authorized: bool


class DeploymentInfo(BaseModel):
    deployment_id: int
    model_url: HttpUrl


class Healthz(BaseModel):
    status: str = "healthy"


class DocsUrl(BaseModel):
    url: HttpUrl
