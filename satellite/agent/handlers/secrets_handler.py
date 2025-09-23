import asyncio

from agent.clients import PlatformClient
from agent.logger import logger
from agent.schemas.deployments import Secret
from agent.settings import config


class SecretsHandler:
    def __init__(self) -> None:
        self.orbit_secrets: dict[int, Secret] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        await self._load_secrets_to_cache()
        self._start_cleanup_task()

        self._initialized = True

    async def _load_secrets_to_cache(self) -> dict[int, Secret]:
        secrets = await SecretsHandler.get_all_secrets()
        if secrets:
            for secret_data in secrets:
                if isinstance(secret_data, dict) and "id" in secret_data:
                    secret = Secret.model_validate(secret_data)
                    self.orbit_secrets[secret_data["id"]] = secret
        return self.orbit_secrets

    def clear_cache(self) -> None:
        self.orbit_secrets.clear()

    def _start_cleanup_task(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def _periodic_cleanup(self) -> None:
        while True:
            try:
                await asyncio.sleep(900)  # 15 minutes
                self.clear_cache()

                await self._load_secrets_to_cache()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

    async def get_secret(self, secret_id: int) -> Secret | None:
        if secret_id in self.orbit_secrets:
            return self.orbit_secrets[secret_id]

        try:
            async with PlatformClient(
                str(config.PLATFORM_URL), config.SATELLITE_TOKEN
            ) as platform_client:
                secret_data = await platform_client.get_orbit_secret(secret_id)
                if secret_data:
                    secret = Secret.model_validate(secret_data)
                    self.orbit_secrets[secret_id] = secret
                    return secret
                return None
        except Exception as e:
            logger.error(f"Failed to fetch secret {secret_id}: {e}")
            return None

    @staticmethod
    async def get_all_secrets() -> list[dict] | None:
        try:
            async with PlatformClient(
                str(config.PLATFORM_URL), config.SATELLITE_TOKEN
            ) as platform_client:
                return await platform_client.get_orbit_secrets()

        except Exception:
            logger.error("Failed to fetch secrets")
            return None
