from datetime import datetime
from typing import Any

from pydantic import Field

from luml_satellite._version import KIT_NAME, KIT_VERSION, SATELLITE_API_VERSION
from luml_satellite.wire._base import PlatformModel


class KitInfo(PlatformModel):
    name: str = KIT_NAME
    version: str = KIT_VERSION
    kind: str
    api_version: int = SATELLITE_API_VERSION


class PairingRequest(PlatformModel):
    base_url: str | None = None
    capabilities: dict[str, Any]
    slug: str | None = None
    openapi: dict[str, Any] | None = None
    kit: KitInfo | None = None


class PairedSatellite(PlatformModel):
    id: str
    orbit_id: str
    name: str | None = None
    description: str | None = None
    base_url: str | None = None
    paired: bool
    capabilities: dict[str, Any]
    slug: str | None = None
    kit_info: KitInfo | None = None
    created_at: datetime
    updated_at: datetime | None = None
    last_seen_at: datetime | None = None


class SatelliteContract(PlatformModel):
    api_version: int
    openapi: dict[str, Any] = Field(default_factory=dict)
