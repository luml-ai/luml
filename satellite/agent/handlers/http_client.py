import logging

import httpx

logger = logging.getLogger(__name__)


class HttpClient:
    def __init__(self) -> None:
        self.headers = {
            "Content-Type": "application/json",
        }

    async def post(self, url: str, request_data: dict, timeout: int = 45) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, json=request_data, headers=self.headers, timeout=timeout
                )
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            logger.warning(f"Connection failed to {url}: {e}")
            raise
        except httpx.TimeoutException as e:
            logger.warning(f"Request timeout to {url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} from {url}: {e}")
            raise

    async def get(self, url: str, timeout: int = 45) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=timeout)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            logger.warning(f"Connection failed to {url}: {e}")
            raise
        except httpx.TimeoutException as e:
            logger.warning(f"Request timeout to {url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} from {url}: {e}")
            raise
