from fastapi import APIRouter

from luml.api.orbits.orbit_live_sessions import live_session_handler

well_known_router = APIRouter(prefix="/.well-known", tags=["well-known"])


@well_known_router.get("/jwks.json")
async def get_jwks() -> dict[str, list[dict[str, str]]]:
    return live_session_handler.public_keys()
