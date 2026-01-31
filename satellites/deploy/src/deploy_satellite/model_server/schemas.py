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
