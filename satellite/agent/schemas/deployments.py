from typing import Any

from pydantic import BaseModel


class Deployment(BaseModel):
    id: str
    orbit_id: str
    satellite_id: str
    satellite_name: str
    name: str
    model_id: str
    model_artifact_name: str
    collection_id: str
    inference_url: str | None = None
    status: str
    satellite_parameters: dict[str, int | str] | None = {}
    description: str | None = None
    dynamic_attributes_secrets: dict[str, str] | None = {}
    env_variables_secrets: dict[str, str] | None = {}
    env_variables: dict[str, str] | None = {}
    schemas: dict[str, str] | None = {}
    created_by_user: str | None = None
    tags: list[str] | None = None
    created_at: str
    updated_at: str | None = None


class LocalDeployment(BaseModel):
    deployment_id: str
    dynamic_attributes_secrets: dict[str, str] | None = {}
    manifest: dict | None = None
    openapi_schema: dict | None = None


class Secret(BaseModel):
    name: str
    value: str


class InferenceAccessIn(BaseModel):
    api_key: str


class InferenceAccessOut(BaseModel):
    authorized: bool


class DeploymentInfo(BaseModel):
    deployment_id: str


class Healthz(BaseModel):
    status: str = "healthy"


class EndpointSchema(BaseModel):
    url: str | None = None
    route: str
    request: dict[str, Any]
    response: dict[str, Any]


class Schemas(BaseModel):
    base_url: str | None = None
    headers: dict[str, str] | None = None
    endpoints: list[EndpointSchema]
