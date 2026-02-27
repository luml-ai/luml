import contextlib
import json
import os
from pathlib import Path

import httpx
import keyring
import keyring.errors

from lumlflow.infra.exceptions import ApplicationError
from lumlflow.schemas.auth import ApiKeyCredentials
from lumlflow.settings import config


class AuthHandler:
    _KEYRING_SERVICE = "lumlflow"
    _LUML_JSON_PATH = Path.home() / ".luml.json"

    def get_stored_credentials(self) -> ApiKeyCredentials:
        with contextlib.suppress(Exception, keyring.errors.NoKeyringError):
            api_key = keyring.get_password(self._KEYRING_SERVICE, "api_key")
            if api_key:
                return ApiKeyCredentials(api_key=api_key)

        if self._LUML_JSON_PATH.exists():
            with contextlib.suppress(Exception):
                data = json.loads(self._LUML_JSON_PATH.read_text())
                api_key = data.get("api_key")
                if api_key:
                    return ApiKeyCredentials(api_key=api_key)

        return ApiKeyCredentials(api_key=os.environ.get("LUML_API_KEY"))

    def has_api_key(self) -> bool:
        creds = self.get_stored_credentials()
        return creds.api_key is not None

    def save_credentials(self, api_key: str) -> None:
        with contextlib.suppress(Exception, keyring.errors.NoKeyringError):
            keyring.set_password(self._KEYRING_SERVICE, "api_key", api_key)

        self._LUML_JSON_PATH.write_text(json.dumps({"api_key": api_key}, indent=2))

    def set_api_key(self, data: ApiKeyCredentials) -> None:
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{config.LUML_BASE_URL}/auth/api-keys/validate",
                    headers={"Authorization": f"Bearer {data.api_key}"},
                    timeout=10,
                )
        except Exception as e:
            raise ApplicationError("Could not reach LUML platform", 502) from e

        if response.status_code == 200:
            self.save_credentials(data.api_key)
            return
        if response.status_code == 401:
            raise ApplicationError("Invalid API key", 401)
        raise ApplicationError(response.text, response.status_code)
