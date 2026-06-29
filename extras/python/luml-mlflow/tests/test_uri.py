import pytest
from luml_mlflow.uri import (
    build_artifact_uri,
    parse_artifact_uri,
    parse_tracking_uri,
)


def test_parses_org_and_orbit() -> None:
    target = parse_tracking_uri("luml://org1/orbit1")
    assert target.org == "org1"
    assert target.orbit == "orbit1"
    assert target.local_only is False
    assert target.sync_eligible is True


def test_local_only_short_form() -> None:
    target = parse_tracking_uri("luml://local")
    assert target.local_only is True
    assert target.org is None
    assert target.orbit is None
    assert target.sync_eligible is False


def test_local_only_with_trailing_path() -> None:
    target = parse_tracking_uri("luml://local/some/path")
    assert target.local_only is True


def test_missing_orbit_raises() -> None:
    with pytest.raises(ValueError, match="orbit id"):
        parse_tracking_uri("luml://org1")


def test_missing_org_raises() -> None:
    with pytest.raises(ValueError, match="organization id"):
        parse_tracking_uri("luml:///orbit1")


def test_non_luml_scheme_raises() -> None:
    with pytest.raises(ValueError, match="luml://"):
        parse_tracking_uri("file:///tmp/mlruns")


def test_trailing_segments_ignored() -> None:
    target = parse_tracking_uri("luml://org1/orbit1/extra")
    assert target.org == "org1"
    assert target.orbit == "orbit1"


def test_parse_artifact_uri_sync_eligible() -> None:
    loc = parse_artifact_uri("luml://org1/orbit1/runs/r-1/artifacts")
    assert loc.target.org == "org1"
    assert loc.target.orbit == "orbit1"
    assert loc.target.local_only is False
    assert loc.run_id == "r-1"


def test_parse_artifact_uri_local_only() -> None:
    loc = parse_artifact_uri("luml://local/runs/r-1/artifacts")
    assert loc.target.local_only is True
    assert loc.target.org is None
    assert loc.target.orbit is None
    assert loc.run_id == "r-1"


def test_parse_artifact_uri_missing_run_segment_raises() -> None:
    with pytest.raises(ValueError, match="runs/<run_id>/artifacts"):
        parse_artifact_uri("luml://org1/orbit1/something/else")


def test_parse_artifact_uri_missing_artifacts_segment_raises() -> None:
    with pytest.raises(ValueError, match="runs/<run_id>/artifacts"):
        parse_artifact_uri("luml://org1/orbit1/runs/r-1")


def test_parse_artifact_uri_without_name_has_no_model_name() -> None:
    assert parse_artifact_uri("luml://local/runs/r-1/artifacts").model_name is None


def test_parse_artifact_uri_reads_model_name_query() -> None:
    loc = parse_artifact_uri("luml://local/runs/r-1/artifacts?name=rf")
    assert loc.run_id == "r-1"
    assert loc.model_name == "rf"


def test_build_artifact_uri_round_trips_name_with_special_chars() -> None:
    base = "luml://org1/orbit1/runs/r-1/artifacts"
    loc = parse_artifact_uri(build_artifact_uri(base, "my model/v2"))
    assert loc.run_id == "r-1"  # the encoded name does not leak into the path
    assert loc.model_name == "my model/v2"


def test_build_artifact_uri_without_name_is_unchanged() -> None:
    base = "luml://local/runs/r-1/artifacts"
    assert build_artifact_uri(base, None) == base
