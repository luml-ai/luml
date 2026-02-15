from pydantic import BaseModel


class LocalDeployment(BaseModel):
    deployment_id: str
    dynamic_attributes_secrets: dict[str, str] | None = {}
    manifest: dict | None = None
    openapi_schema: dict | None = None


class InferenceAccessIn(BaseModel):
    api_key: str


class InferenceAccessOut(BaseModel):
    authorized: bool


class DeploymentInfo(BaseModel):
    deployment_id: str


class Healthz(BaseModel):
    status: str = "healthy"
