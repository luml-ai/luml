from agent.handlers.model_server_handler import ModelServerHandler
from agent.monitoring import create_telemetry
from agent.settings import config

ms_handler = ModelServerHandler(
    telemetry=create_telemetry(
        endpoint=config.OTEL_EXPORTER_OTLP_ENDPOINT,
        enabled=config.MONITORING_ENABLED,
    ),
)


__all__ = ["ms_handler"]
