"""Monitoring: the sections of a deployment's dashboard, read from its Satellite.

The Satellite's address is resolved from the deployment record itself, so the
name or id of the deployment is all it takes.
"""

from luml_api import LumlClient

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
TRACE_ID = "0199c455-21ee-74c6-b747-19a82f1a1e75"

luml = LumlClient(
    api_key="luml_your_api_key_here",
    organization=ORGANIZATION_ID,
    orbit=ORBIT_ID,
)


def main() -> None:
    monitoring = luml.deployments.monitoring("My Deployment")

    # Identity of the deployment as the dashboard header shows it
    header = monitoring.header()
    print(f"Header: {header}")

    # Status cards, alert banners, runtime series and top drifted features
    overview = monitoring.overview(window="7d")
    print(f"Overview: {overview}")

    # Request counts, error rate, latency percentiles and the outcome breakdown
    runtime = monitoring.runtime(window="24h")
    print(f"Runtime: {runtime}")

    # Per-feature validity checks; pass feature= for one feature's trends
    data_quality = monitoring.data_quality(feature="age")
    print(f"Data quality: {data_quality}")

    # PSI ranking, distributions, and the multivariate panel
    feature_drift = monitoring.feature_drift(severity="critical")
    print(f"Feature drift: {feature_drift}")

    # Did the model's outputs shift against the training reference
    output_drift = monitoring.output_drift(window="7d")
    print(f"Output drift: {output_drift}")

    # The profile the deployment is compared against
    reference_profile = monitoring.reference_profile()
    print(f"Reference profile: {reference_profile}")

    # Open and acknowledged alerts, grouped by metric family
    alerts = monitoring.alerts(window="7d", severity="critical")
    print(f"Alerts: {alerts}")

    # The local request log: one row per inference call
    traces = monitoring.traces(limit=20)
    print(f"Traces: {traces}")

    slowest = monitoring.traces(sort="latency", order="desc", limit=5)
    print(f"Slowest calls: {slowest}")

    # One call with its full payloads and span tree
    trace = monitoring.trace(TRACE_ID)
    print(f"Trace: {trace}")

    # Whether monitoring itself is keeping up; not a metric about the model
    worker = monitoring.worker()
    print(f"Worker health: {worker}")


if __name__ == "__main__":
    main()
