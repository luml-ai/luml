import logging

from luml_satellite.declaration.capabilities import CapabilityDeclaration, capability_diff
from luml_satellite.wire.client import PlatformClient
from luml_satellite.wire.pairing import KitInfo, PairedSatellite


async def pair_satellite(
    platform: PlatformClient,
    *,
    kind: str,
    capabilities: CapabilityDeclaration,
    base_url: str | None = None,
    slug: str | None = None,
    openapi: dict[str, object] | None = None,
    logger: logging.Logger | None = None,
) -> PairedSatellite:
    paired = await platform.pair_satellite(
        base_url.rstrip("/") if base_url is not None else None,
        capabilities,
        slug=slug,
        openapi=openapi,
        kit=KitInfo(kind=kind),
    )
    active_logger = logger or logging.getLogger("luml_satellite")
    for difference in capability_diff(capabilities, paired.capabilities):
        active_logger.warning("platform changed capability declaration: %s", difference)
    await platform.check_contract()
    return paired
