"""Reading an alert back: key parsing, wording, and the metric behind it."""

import uuid

from tests.support import FIXED_NOW, ago

from agent.monitoring import MonitoringQueryService, QueryDimensions
from agent.monitoring.alerts import format_value, history_value, parse_alert_key
from agent.monitoring.query_store import (
    InMemoryMonitoringStore,
    StoredAlert,
    StoredMetricResult,
)
from agent.schemas.monitoring_query import SectionState, Severity, Window


def _service(store: InMemoryMonitoringStore) -> MonitoringQueryService:
    return MonitoringQueryService(store, clock=lambda: FIXED_NOW)


def test_key_splits_into_group_and_feature() -> None:
    drift = parse_alert_key("feature_drift:income")
    assert (drift.group, drift.feature, drift.label) == ("feature_drift", "income", "PSI")

    runtime = parse_alert_key("runtime:latency_p95")
    assert (runtime.group, runtime.feature, runtime.unit) == ("runtime", None, "ms")

    multivariate = parse_alert_key("multivariate:centroid_shift")
    assert (multivariate.label, multivariate.unit) == ("Centroid shift", "sigma")


def test_dotted_feature_names_keep_their_dots() -> None:
    """Iris features are called "petal.length", so the check cannot be split off blindly."""
    parsed = parse_alert_key("data_quality:petal.length.range_violation")

    assert parsed.group == "data_quality"
    assert parsed.feature == "petal.length"
    assert parsed.check == "range_violation"
    assert parsed.label == "Range violation rate"


def test_values_are_phrased_in_their_own_units() -> None:
    assert format_value(0.0221, "ratio") == "2.2%"
    assert format_value(1836.4, "ms") == "1836 ms"
    assert format_value(1.6, "sigma") == "1.60σ"
    assert format_value(0.3955, "score") == "0.40"
    assert format_value(None, "ratio") == "—"


def test_history_is_read_from_the_group_own_layout() -> None:
    quality = {"features": {"region": {"unseen_category_rate": 0.03, "missing_rate": 0.0}}}
    assert history_value(parse_alert_key("data_quality:region.unseen_category"), quality) == 0.03

    drift = {"features": {"income": {"psi": 0.42}}}
    assert history_value(parse_alert_key("feature_drift:income"), drift) == 0.42

    assert history_value(parse_alert_key("runtime:error_rate"), {"error_rate": 0.07}) == 0.07
    assert history_value(parse_alert_key("output_drift:prediction"), {"psi": 0.9}) == 0.9
    assert (
        history_value(parse_alert_key("multivariate:mahalanobis_outliers"), {"outlier_rate": 0.15})
        == 0.15
    )


def _alert(dep: uuid.UUID, metric: str, value: float, threshold: float) -> StoredAlert:
    return StoredAlert(
        deployment_id=dep,
        group=metric.split(":")[0],
        metric=metric,
        feature=parse_alert_key(metric).feature,
        severity=Severity.CRITICAL,
        current_value=value,
        threshold=threshold,
        state="open",
        first_seen=ago(3600),
        last_seen=ago(600),
    )


def _drift_window(dep: uuid.UUID, psi: float, seconds_ago: float) -> StoredMetricResult:
    return StoredMetricResult(
        deployment_id=dep,
        group="feature_drift",
        window=Window.H24.value,
        values={"features": {"income": {"psi": psi}}},
        severity="critical",
        computed_at=ago(seconds_ago),
    )


async def test_alert_carries_its_wording_duration_and_history() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_alert(_alert(dep, "feature_drift:income", 0.42, 0.25))
    for psi, seconds_ago in ((0.28, 2400), (0.35, 1800), (0.42, 600)):
        store.add_result(_drift_window(dep, psi, seconds_ago))

    result = await _service(store).alerts(dep, QueryDimensions(window=Window.H24))

    assert result.state is SectionState.OK
    alert = result.groups[0].alerts[0]
    assert result.groups[0].group == "feature_drift"
    assert alert.feature == "income"
    assert alert.label == "PSI"
    # the message is only the numbers: the title already names group and feature
    assert alert.message == "PSI 0.42 vs threshold 0.25"
    assert alert.duration_seconds == 3000  # firing from first_seen to last_seen
    assert alert.history is not None
    assert [point.value for point in alert.history.points] == [0.28, 0.35, 0.42]


async def test_one_window_is_not_a_history() -> None:
    dep = uuid.uuid4()
    store = InMemoryMonitoringStore()
    store.add_alert(_alert(dep, "feature_drift:income", 0.42, 0.25))
    store.add_result(_drift_window(dep, 0.42, 600))

    result = await _service(store).alerts(dep, QueryDimensions(window=Window.H24))

    assert result.groups[0].alerts[0].history is None
