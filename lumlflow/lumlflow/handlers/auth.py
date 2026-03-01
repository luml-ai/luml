import contextlib
import json
import logging
from pathlib import Path

import httpx
import keyring
import keyring.errors

from lumlflow.infra.exceptions import ApplicationError
from lumlflow.schemas.auth import ApiKeyCredentials, SetApiKey
from lumlflow.settings import config

logger = logging.getLogger(__name__)


class AuthHandler:
    _KEYRING_SERVICE = "lumlflow"
    _LUML_JSON_PATH = Path.home() / ".luml.json"

    def get_stored_credentials(self) -> ApiKeyCredentials:
        with contextlib.suppress(keyring.errors.KeyringError, keyring.errors.NoKeyringError):
            api_key = keyring.get_password(self._KEYRING_SERVICE, "api_key")
            if api_key:
                return ApiKeyCredentials(api_key=api_key)

        if self._LUML_JSON_PATH.exists():
            with contextlib.suppress(OSError, json.JSONDecodeError):
                data = json.loads(self._LUML_JSON_PATH.read_text())
                api_key = data.get("api_key")
                if api_key:
                    return ApiKeyCredentials(api_key=api_key)

        return ApiKeyCredentials(api_key=config.LUML_API_KEY)

    def has_api_key(self) -> bool:
        creds = self.get_stored_credentials()
        return creds.api_key is not None

    def _write_api_key_to_file(self, api_key: str):
        payload = json.dumps({"api_key": api_key}, indent=2)
        self._LUML_JSON_PATH.touch(mode=0o600, exist_ok=True)
        self._LUML_JSON_PATH.write_text(payload)
        self._LUML_JSON_PATH.chmod(0o600)

    def save_credentials(self, api_key: str) -> None:
        try:
            keyring.set_password(self._KEYRING_SERVICE, "api_key", api_key)
            return
        except (keyring.errors.KeyringError, keyring.errors.NoKeyringError) as e:
            logger.warning(f"Keyring unavailable, falling back to file storage: {str(e)}")

        try:
            self._write_api_key_to_file(api_key)
        except OSError as e:
            logger.error(f"Failed to write credentials to file: {str(e)}")
            raise


    def set_api_key(self, data: SetApiKey) -> None:
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{config.LUML_BASE_URL}/auth/api-keys/validate",
                    headers={"Authorization": f"Bearer {data.api_key}"},
                    timeout=10,
                )
        except Exception as e:
            raise ApplicationError("Could not reach LUML platform", 502) from e

        if response.status_code == 204:
            self.save_credentials(data.api_key)
            return
        if response.status_code == 401:
            raise ApplicationError("Invalid API key", 401)
        raise ApplicationError(response.text, response.status_code)
