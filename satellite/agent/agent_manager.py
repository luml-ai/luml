from typing import Any

from .clients import PlatformClient
from .settings import config


class SatelliteManager:
    def __init__(self, platform: PlatformClient) -> None:
        self.platform = platform

    async def pair(self) -> None:
        slug = None
        await self.platform.pair_satellite(
            config.BASE_URL.rstrip("/"), self.get_capabilities(), slug
        )

    @staticmethod
    def get_capabilities() -> dict[str, Any]:
        return {
            "deploy": {
                "version": 1,
                "supported_variants": ["pyfunc", "pipeline"],
                "supported_tags_combinations": None,
                "extra_fields_form_spec": None,
            }
        }

    @staticmethod
    def _generate_form_spec() -> list[dict[str, Any]]:
        return [
            {
                "name": "custom_inference_url",
                "type": "text",
                "values": None,
                "required": False,
                "validators": [
                    {
                        "type": "regex",
                        "value": r"^https?://.*",
                        "message": "Your deployment custom base url. ",
                    }
                ],
                "conditions": [],
            },
            {
                "name": "use_gpu",
                "type": "boolean",
                "values": None,
                "required": False,
                "validators": [],
                "conditions": [],
            },
            {
                "name": "memory_limit",
                "type": "dropdown",
                "values": [
                    {"label": "512 MB", "value": "512m"},
                    {"label": "1 GB", "value": "1g"},
                    {"label": "2 GB", "value": "2g"},
                    {"label": "4 GB", "value": "4g"},
                    {"label": "8 GB", "value": "8g"},
                    {"label": "16 GB", "value": "16g"},
                ],
                "required": False,
                "validators": [],
                "conditions": [],
            },
            {
                "name": "cpu_limit",
                "type": "number",
                "values": None,
                "required": False,
                "validators": [
                    {"type": "min", "value": 0.1},
                    {"type": "max", "value": 16},
                ],
                "conditions": [
                    {
                        "type": "field",
                        "body": {
                            "field": "use_gpu",
                            "operator": "equal",
                            "value": False,
                        },
                    }
                ],
            },
            {
                "name": "gpu_count",
                "type": "number",
                "values": None,
                "required": False,
                "validators": [
                    {"type": "min", "value": 1},
                    {"type": "max", "value": 8},
                ],
                "conditions": [
                    {
                        "type": "field",
                        "body": {
                            "field": "use_gpu",
                            "operator": "equal",
                            "value": True,
                        },
                    }
                ],
            },
            {
                "name": "restart_policy",
                "type": "dropdown",
                "values": [
                    {"label": "Always restart", "value": "always"},
                    {"label": "On failure only", "value": "on-failure"},
                    {"label": "Unless stopped", "value": "unless-stopped"},
                    {"label": "Never restart", "value": "no"},
                ],
                "required": False,
                "validators": [],
                "conditions": [],
            },
            {
                "name": "health_check_timeout",
                "type": "number",
                "values": None,
                "required": False,
                "validators": [
                    {"type": "min", "value": 60},
                    {"type": "max", "value": 360},
                ],
                "conditions": [],
            },
            {
                "name": "log_level",
                "type": "dropdown",
                "values": [
                    {"label": "Debug", "value": "DEBUG"},
                    {"label": "Info", "value": "INFO"},
                    {"label": "Warning", "value": "WARNING"},
                    {"label": "Error", "value": "ERROR"},
                ],
                "required": False,
                "validators": [],
                "conditions": [],
            },
        ]
