from luml_satellite.declaration import SatelliteConfiguration


def test_configuration_keeps_existing_and_new_defaults() -> None:
    configuration = SatelliteConfiguration(SATELLITE_TOKEN="token")

    assert str(configuration.PLATFORM_URL) == "https://api.luml.ai/"
    assert configuration.BASE_URL is None
    assert configuration.POLL_INTERVAL_SEC == 2.0
    assert configuration.MONITORING_FRAME_ANCESTORS == ""
    assert configuration.MONITORING_SESSION_TTL_SECONDS == 1800
    assert configuration.AGENT_PORT == 8000
    assert configuration.OTEL_EXPORTER_OTLP_ENDPOINT is None
    assert configuration.MONITORING_ENABLED is True
    assert configuration.MONITORING_INTERVAL_SEC == 60.0
    assert configuration.MONITORING_WINDOW_SEC == 300.0
    assert configuration.MONITORING_LATENCY_P95_THRESHOLD_MS == 1000.0
    assert configuration.MONITORING_BACKFILL_MAX_WINDOWS == 12
    assert configuration.MONITORING_EVENTS_TTL == "30d"
    assert configuration.MONITORING_RESULTS_TTL == "30d"
    assert configuration.MONITORING_ALERTS_TTL == "30d"
    assert configuration.MONITORING_TRACES_TTL == "30d"
    assert configuration.MONITORING_METRICS_TTL == "7d"
    assert configuration.GREPTIMEDB_HOST == "localhost"
    assert configuration.GREPTIMEDB_HTTP_PORT == 4000
    assert configuration.GREPTIMEDB_DATABASE == "public"
    assert configuration.POLL_BACKOFF_MAX_SEC == 60
    assert configuration.MAX_PARALLEL_CONVERGENCE == 8
    assert configuration.MAX_RELAUNCH_ATTEMPTS == 3
    assert configuration.DRIVER_CALL_TIMEOUT_SEC == 300
    assert configuration.HEALTH_PASS_INTERVAL_SEC == 60
    assert configuration.HEALTH_CHECK_TIMEOUT_SEC == 1800
    assert configuration.INTERNAL_PORT is None
    assert configuration.RECORDING_SAMPLE_RATE == 1.0
    assert configuration.RECORDING_BODY_MAX_BYTES == 65536
    assert configuration.RECORDING_KEEP_INPUTS is True
    assert configuration.RECORDING_KEEP_OUTPUTS is True
    assert configuration.INJECTION_BODY_MAX_BYTES == 16777216
    assert configuration.MONITORING_SESSION_SECRET is None
    assert configuration.DERIVATION_KEY is None
    assert configuration.LOG_LEVEL == "INFO"
    assert "MODEL_IMAGE" not in type(configuration).model_fields
    assert "MODEL_SERVER_PORT" not in type(configuration).model_fields


def test_two_configurations_coexist_without_shared_state() -> None:
    first = SatelliteConfiguration(
        SATELLITE_TOKEN="first-token",
        BASE_URL="https://first.example",
        POLL_INTERVAL_SEC=1,
        MONITORING_FRAME_ANCESTORS="https://one.example https://two.example",
    )
    second = SatelliteConfiguration(
        SATELLITE_TOKEN="second-token",
        BASE_URL=None,
        POLL_INTERVAL_SEC=5,
    )

    assert first.SATELLITE_TOKEN == "first-token"
    assert first.BASE_URL == "https://first.example"
    assert first.POLL_INTERVAL_SEC == 1
    assert first.monitoring_frame_ancestors() == [
        "https://one.example",
        "https://two.example",
    ]
    assert second.SATELLITE_TOKEN == "second-token"
    assert second.BASE_URL is None
    assert second.POLL_INTERVAL_SEC == 5
