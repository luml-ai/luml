# Satellite

The Satellite runs model deployments and their monitoring next to them: the Agent proxies
inference, GreptimeDB stores telemetry locally, and the monitoring dashboard is served
from here into the Platform's iframe. Raw inputs and outputs never leave this machine.

See `SMOKE_TEST.md` for bringing a local stand up, and `spec_full.md` /
`MONITORING_API_SPEC.md` in the repository root for the architecture.

The Docker satellite lives in `implementations/docker`, the Kubernetes one in
`implementations/kubernetes`, and both are built on the kit in `kit/`. The Kubernetes
README covers its chart, a local stand on kind and the end-to-end scenario.

## Monitoring over the machine API

Monitoring is a facet of the deployment tree, next to inference, behind the same bearer
LUML API key:

```bash
# what runs here, and what is monitored
curl $SATELLITE/deployments -H "Authorization: Bearer $LUML_API_KEY"

# any dashboard section, per deployment — same query dimensions as the dashboard
curl "$SATELLITE/deployments/$DEPLOYMENT_ID/monitoring/overview?window=24h" \
  -H "Authorization: Bearer $LUML_API_KEY"
```

Sections: `header`, `overview`, `runtime`, `data-quality`, `feature-drift`,
`reference-profile`, `alerts`, `traces`, `traces/{event_id}`, `worker`.

The key is verified against the Platform (cached for about a minute) with the same
permission that gates inference access and dashboard launch. Read-only: acknowledging
alerts stays with the browser dashboard. The browser world under `/monitoring` is
untouched — cookie sessions only, minted from single-use launch tokens.
