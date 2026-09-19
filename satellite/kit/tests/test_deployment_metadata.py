from luml_satellite.workload import DeploymentMetadata


def test_metadata_carries_the_dashboard_header_identity() -> None:
    metadata = DeploymentMetadata.from_platform(
        {
            "name": "insurance regression",
            "status": "active",
            "artifact_name": "insurance_regression_v2",
            "orbit_name": "Default Orbit",
            "satellite_name": "satellite",
            "inference_url": "/deployments/x",
        }
    )

    assert metadata.name == "insurance regression"
    assert metadata.model_name == "insurance_regression_v2"
    assert metadata.environment == "Default Orbit"
    assert metadata.satellite == "satellite"
    assert metadata.inference_url == "/deployments/x"


def test_metadata_without_an_orbit_name_leaves_environment_empty() -> None:
    metadata = DeploymentMetadata.from_platform({"name": "x", "status": "active"})

    assert metadata.environment is None


def test_metadata_accepts_the_legacy_model_artifact_name() -> None:
    metadata = DeploymentMetadata.from_platform({"model_artifact_name": "legacy-name"})

    assert metadata.model_name == "legacy-name"
