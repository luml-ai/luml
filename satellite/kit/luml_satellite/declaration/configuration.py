from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SatelliteConfiguration(BaseSettings):
    SATELLITE_TOKEN: str
    PLATFORM_URL: AnyHttpUrl = AnyHttpUrl("https://api.luml.ai")
    BASE_URL: str | None = None
    POLL_INTERVAL_SEC: float = 2.0
    MONITORING_FRAME_ANCESTORS: str = ""
    MONITORING_SESSION_TTL_SECONDS: int = 1800
    AGENT_PORT: int = 8000

    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    MONITORING_ENABLED: bool = True
    MONITORING_INTERVAL_SEC: float = 60.0
    MONITORING_WINDOW_SEC: float = 300.0
    MONITORING_LATENCY_P95_THRESHOLD_MS: float = 1000.0
    MONITORING_BACKFILL_MAX_WINDOWS: int = 12
    MONITORING_EVENTS_TTL: str = "30d"
    MONITORING_RESULTS_TTL: str = "30d"
    MONITORING_ALERTS_TTL: str = "30d"
    MONITORING_TRACES_TTL: str = "30d"
    MONITORING_METRICS_TTL: str = "7d"
    GREPTIMEDB_HOST: str = "localhost"
    GREPTIMEDB_HTTP_PORT: int = 4000
    GREPTIMEDB_DATABASE: str = "public"

    POLL_BACKOFF_MAX_SEC: float = Field(default=60.0, gt=0)
    MAX_PARALLEL_CONVERGENCE: int = Field(default=8, gt=0)
    MAX_RELAUNCH_ATTEMPTS: int = Field(default=3, ge=0)
    DRIVER_CALL_TIMEOUT_SEC: float = Field(default=300.0, gt=0)
    HEALTH_PASS_INTERVAL_SEC: float = Field(default=60.0, ge=0)
    HEALTH_CHECK_TIMEOUT_SEC: int = Field(default=1800, gt=0)
    INTERNAL_PORT: int | None = Field(default=None, ge=1, le=65535)
    RECORDING_SAMPLE_RATE: float = Field(default=1.0, ge=0, le=1)
    RECORDING_BODY_MAX_BYTES: int = Field(default=65536, gt=0)
    RECORDING_KEEP_INPUTS: bool = True
    RECORDING_KEEP_OUTPUTS: bool = True
    INJECTION_BODY_MAX_BYTES: int = Field(default=16777216, gt=0)
    MONITORING_SESSION_SECRET: str | None = None
    DERIVATION_KEY: str | None = None
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def monitoring_frame_ancestors(self) -> list[str]:
        return self.MONITORING_FRAME_ANCESTORS.split()


Configuration = SatelliteConfiguration
