# LUML Kubernetes satellite chart

This chart installs one LUML satellite, its monitoring processes, and the namespaced RBAC needed to manage model workloads. It uses standard Kubernetes resources and supports both vanilla Kubernetes and OpenShift.

## Install

Install with a satellite token and the public host that routes to the chart's Ingress:

```shell
helm install my-satellite ./chart \
  --namespace luml --create-namespace \
  --set-string satellite.token="$SATELLITE_TOKEN" \
  --set satellite.host=models.example.com
```

For OpenShift, add `-f chart/values-openshift.yaml`. The OpenShift preset leaves user and group IDs unset for the security context constraint, selects `openshift-default`, adds edge termination, and still renders a standard Ingress rather than a Route.

The release name is the satellite identity inside its namespace. Use a different release name and host for each satellite installed in the same namespace.

## Values

| Group | Purpose |
|---|---|
| `satellite` | Token or existing token Secret, derivation key, platform URL, host/base URL, slug, image, pull secrets and resources |
| `model`, `sidecar` | Model and serving images, sidecar authorization cache, recording defaults and resources |
| `deploymentLimits` | User-visible replica, CPU, memory and health-check limits sent in the satellite capability declaration |
| `gpu` | Whether GPU fields are offered, their limits, node selector, tolerations and runtime class |
| `sharedCache` | Optional artifact-cache claim, size, storage class and access modes |
| `ingress` | Ingress class, annotations and optional TLS Secret |
| `podSecurity` | `vanilla` or `openshift` preset plus pod/container context overrides |
| `monitoring` | Dashboard, worker, collector, session, retention and store configuration |
| `networkPolicy`, `rbac`, `serviceAccount` | Namespaced access controls |
| `probes` | Timeout and failure threshold for every probe this chart renders, including the ones the satellite gives model pods |

`satellite.baseUrl` overrides URL derivation. Otherwise the chart uses `https://` when an Ingress TLS Secret is configured or the OpenShift preset is active, and `http://` otherwise.

Kubernetes gives an unset probe timeout one second, which is too little for a container that has to start a process to answer. `probes.timeoutSeconds` and `probes.failureThreshold` are applied to every probe this chart renders — satellite, dashboard, worker, collector and store — and are passed to the satellite so the model and sidecar probes it creates carry them too. Changing either value changes the workload fingerprint the satellite labels those pods with, so reconciliation reapplies existing model Deployments instead of leaving them on the old setting. Both values fall back to the chart defaults when a release installed before this group is upgraded. The worker is probed through `luml-monitoring-probe`, an entry point that reads the heartbeat file without importing the rest of the kit.

The vanilla security preset pins user 10001, group 0 and file-system group 10001. Both presets require non-root containers, runtime-default seccomp, no privilege escalation and all Linux capabilities dropped. Context maps may be overridden for installations with additional policy requirements.

### Secrets and rotation

Set `satellite.existingSecret` and `satellite.existingSecretKey` to read the satellite token from an existing Secret. Otherwise the chart creates a token Secret from `satellite.token` and rolls the satellite, dashboard and worker when that value changes.

The derivation key is always held in a separate chart Secret. Set `satellite.derivationKey` to supply one; when it is empty, Helm generates one on the first install and retrieves the existing value during upgrades. The Secret is retained if the release is removed. Back it up before uninstalling.

Rotating only the satellite token leaves the derivation key and model pods unchanged. Existing token Secrets cannot be checksummed by Helm, so restart the three Deployments after rotating one:

```shell
kubectl rollout restart deployment -l luml.ai/satellite-id=my-satellite
```

Rotate a compromised derivation key deliberately with `--set-string satellite.derivationKey=...`. The chart workloads restart, and reconciliation replaces owned model pods whose derivation-key fingerprint is stale. Sidecars continue serving cached authorization and secrets during the restart allowance.

### GPU and shared cache

GPU fields are not offered by default. Enabling `gpu.enabled` exposes GPU use, count and resource-name fields within the configured limits. Placement settings are emitted only for deployments that select GPU use.

Enabling `sharedCache.enabled` creates a release-scoped claim with `ReadWriteMany` by default and exposes the shared-cache deployment setting. Use `sharedCache.existingClaim` to reuse a provisioned claim. Confirm that the storage class supports the chosen access modes.

## Monitoring store modes

The default `monitoring.store.mode=standalone` runs a single GreptimeDB StatefulSet and Service. Its data claim is controlled by `monitoring.store.persistence`. This is the simplest starting point for one satellite.

For larger persistent installations, keep standalone mode and enable `monitoring.store.objectStorage`. Configure its endpoint, bucket and region, then provide access keys directly or through `objectStorage.existingSecret`. The local data volume remains available for runtime state and caching.

To use an independently operated GreptimeDB cluster, select `monitoring.store.mode=external`, set `host`, `port` and `database`, and provide credentials directly or with `monitoring.store.existingSecret`. External mode removes only the in-chart store workload, Service and volume, and rewires the dashboard, worker, collector and network-policy egress to the external store.

## Network policy and meshes

The enabled-by-default policy selects only pods carrying this release's `luml.ai/satellite-id` label, including model pods created later by the satellite. It permits traffic within the release, public serving on port 8000, DNS, outbound HTTP/HTTPS for platform, artifact and package access, the Kubernetes API on `networkPolicy.apiServerPort`, and the configured external-store port. It does not select unrelated namespace workloads or another satellite release.

The satellite reaches the API through the `kubernetes` service address, but the service port is translated to the API server's own port before the policy is evaluated, so the policy has to permit that port rather than 443. The default 6443 matches kubeadm clusters. Set `networkPolicy.apiServerPort` to the port the API server listens on, or clear it on installations whose API server answers on 443.

With a service mesh, exclude the satellite's internal port 8001 from public ingress and preserve direct access among the satellite, sidecars, dashboard and worker. The model Service exposes only the sidecar's `http` and `internal` ports; the model-server port is never exposed.
