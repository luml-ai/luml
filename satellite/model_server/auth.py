import os

import httpx

from _exceptions import HTTPException

SATELLITE_AGENT_URL = os.getenv("SATELLITE_AGENT_URL", "").rstrip("/")


def require_api_key(scope: dict) -> None:
    headers = {}
    for name, value in scope.get("headers", []):
        key = name.decode().lower()
        val = value.decode()
        if key == "authorization":
            headers["Authorization"] = val

    auth = headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing API key")
    api_key = auth.split()[1]

    try:
        r = httpx.post(
            f"{SATELLITE_AGENT_URL}/satellites/deployments/inference-access",
            json={"api_key": api_key},
            timeout=5.0,
        )
        r.raise_for_status()
        data = r.json()
        if not bool(data.get("authorized")):
            raise HTTPException(status_code=403, detail="Invalid API key")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(status_code=502, detail="Authorization check failed")
