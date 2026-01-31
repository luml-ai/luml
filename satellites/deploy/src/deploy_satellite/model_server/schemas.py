"""Schemas for model server components."""

from typing import Any

from pydantic import BaseModel


class LocalDeployment(BaseModel):
    """Local deployment information tracked by the model server handler."""

    deployment_id: str
    dynamic_attributes_secrets: dict[str, str] | None = {}
    manifest: dict[str, Any] | None = None
    openapi_schema: dict[str, Any] | None = None


class Secret(BaseModel):
    """Secret value retrieved from the platform."""

    name: str
    value: str


class InferenceAccessIn(BaseModel):
    """Request schema for inference access authorization."""

    api_key: str


class InferenceAccessOut(BaseModel):
    """Response schema for inference access authorization."""

    authorized: bool


class DeploymentInfo(BaseModel):
    """Basic deployment information for API responses."""

    deployment_id: str


class Healthz(BaseModel):
    """Health check response schema."""

    status: str = "healthy"
