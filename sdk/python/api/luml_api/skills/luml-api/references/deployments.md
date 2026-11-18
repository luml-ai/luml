# Deployments and monitoring

A deployment is a model running on a satellite. The client reads deployments
and their monitoring. It cannot create, change or delete them yet; the user
does that in the web app.

## Find deployments

```python
for deployment in client.deployments.list():
    print(deployment.name, deployment.status, deployment.artifact_name)

deployment = client.deployments.get("churn-prod")   # exact name or id
print(deployment.inference_url)
```

A `Deployment` also has `satellite_name`, `artifact_id`, `monitoring_mode`
and `monitoring_url`.

## Monitoring

```python
monitoring = client.deployments.monitoring("churn-prod")

monitoring.header()                          # status, task type, last prediction, profile_status
monitoring.overview(window="7d")             # status cards, alerts, top drifted features
monitoring.alerts(severity="critical")
monitoring.runtime(window="24h")             # whether the endpoint is healthy
monitoring.data_quality(feature="tenure")
monitoring.feature_drift(window="7d")
monitoring.output_drift(window="7d")
monitoring.reference_profile()
monitoring.traces(limit=50, sort="latency")  # one row per inference call
monitoring.trace(event_id)
```

- The calls go to the satellite directly, with the same API key. Each returns
  the dict the matching dashboard tab shows.
- `window` is `"24h"`, `"7d"` or `"30d"`. `severity` is `"all"`,
  `"warning"` or `"critical"`. `compare` (overview, runtime) is
  `"reference"` (the training profile) or `"previous"` (the period before).
- Drift and data quality need a reference profile in the model. When
  `header()["profile_status"]` is not `"ready"`, the model was uploaded without
  one: see `python -m luml skills show luml-sdk references/monitoring.md`.
- `SatelliteOutOfSyncError` means the platform's record of the satellite no
  longer matches the build it runs. Restarting or re-pairing the satellite
  fixes it; tell the user.
