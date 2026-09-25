# LUML Kubernetes satellite chart

This chart installs one LUML satellite, its monitoring processes and the namespaced RBAC that
manages model workloads. It uses standard Kubernetes resources. It supports vanilla Kubernetes
and OpenShift.

## Install

Install with a satellite token and the public host that routes to the chart's Ingress:

```shell
helm install my-satellite ./chart \
  --namespace luml --create-namespace \
  --set-string satellite.token="$SATELLITE_TOKEN" \
  --set satellite.host=models.example.com
```

For OpenShift, add `-f chart/values-openshift.yaml`. The OpenShift preset:

1. Leaves user and group IDs unset, so that the security context constraint assigns them.
2. Selects the `openshift-default` ingress class.
3. Adds edge termination.
4. Still renders a standard Ingress, not a Route.

The release name is the satellite identity inside its namespace. Use a different release name
and host for each satellite that you install in the same namespace.

## Values

| Group | Purpose |
|---|---|
| `satellite` | Token or existing token Secret, derivation key, platform URL, host/base URL, slug, image, pull secrets and resources |
| `model`, `sidecar` | Model and serving images, sidecar authorization cache, recording defaults and resources |
| `deploymentLimits` | User-visible replica, CPU, memory and health-check limits sent in the satellite capability declaration |
| `gpu` | Whether the chart offers GPU fields, their limits, node selector, tolerations and runtime class |
| `sharedCache` | Optional artifact-cache claim, size, storage class and access modes |
| `ingress` | Ingress class, annotations and optional TLS Secret |
| `podSecurity` | `vanilla` or `openshift` preset plus pod/container context overrides |
| `monitoring` | Dashboard, worker, collector, session, retention and store configuration |
| `networkPolicy`, `rbac`, `serviceAccount` | Namespaced access controls |
| `probes` | Timeout and failure threshold for every probe this chart renders, including the ones the satellite gives model pods |

`satellite.baseUrl` overrides URL derivation. Without it, the chart uses `https://` when you
configure an Ingress TLS Secret or select the OpenShift preset. Otherwise it uses `http://`.

### Probes

Kubernetes gives an unset probe timeout one second. That is too little for a container that
has to start a process to answer. The chart applies `probes.timeoutSeconds` and
`probes.failureThreshold` to every probe it renders:

1. satellite
2. dashboard
3. worker
4. collector
5. store

The chart also passes both values to the satellite. The model and sidecar probes it creates
carry them too. A change to either value changes the workload fingerprint that the satellite
puts on those pods. Reconciliation then reapplies the model Deployments that already run.
Both values fall back to the chart defaults when you upgrade a release that predates this
group. The chart probes the worker through `luml-monitoring-probe`. That entry point reads
the heartbeat file and imports nothing else from the kit.

### Security presets

The vanilla preset pins user 10001, group 0 and file-system group 10001. Both presets require
non-root containers, runtime-default seccomp and no privilege escalation. Both drop all Linux
capabilities. You may override the context maps for installations with additional policy
requirements.

### Secrets and rotation

Set `satellite.existingSecret` and `satellite.existingSecretKey` to read the satellite token
from an existing Secret. Otherwise the chart creates a token Secret from `satellite.token`.
The chart rolls the satellite, dashboard and worker when that value changes.

The chart always keeps the derivation key in a separate Secret. Set `satellite.derivationKey`
to supply one. When the value is empty, Helm generates a key on the first install and reads
the existing key during upgrades. Helm keeps that Secret when you remove the release. Back it
up before you uninstall.

A rotation of the satellite token alone leaves the derivation key and the model pods
unchanged. Helm cannot checksum an existing token Secret. After you rotate one, restart the
three Deployments:

```shell
kubectl rollout restart deployment -l luml.ai/satellite-id=my-satellite
```

To rotate a compromised derivation key, set `--set-string satellite.derivationKey=...` on
purpose. The chart workloads restart. Reconciliation then replaces the owned model pods whose
derivation-key fingerprint is stale. Sidecars continue to serve cached authorization and
secrets during the restart allowance.

### GPU and shared cache

The chart does not offer GPU fields by default. `gpu.enabled=true` exposes the GPU use, count
and resource-name fields within the configured limits. The satellite emits placement settings
only for deployments that select GPU use.

`sharedCache.enabled=true` creates a release-scoped claim with `ReadWriteMany` by default and
exposes the shared-cache deployment setting. Use `sharedCache.existingClaim` to reuse a
provisioned claim. Check that the storage class supports the chosen access modes.

## Monitoring store modes

The default `monitoring.store.mode=standalone` runs a single GreptimeDB StatefulSet and
Service. `monitoring.store.persistence` controls its data claim. This is the simplest starting
point for one satellite.

For larger persistent installations, keep standalone mode and enable
`monitoring.store.objectStorage`. Configure its endpoint, bucket and region. Then provide
access keys directly or through `objectStorage.existingSecret`. The local data volume remains
available for runtime state and caching.

To use a GreptimeDB cluster that you operate yourself:

1. Select `monitoring.store.mode=external`.
2. Set `host`, `port` and `database`.
3. Provide credentials directly or with `monitoring.store.existingSecret`.

External mode removes only the in-chart store workload, its Service and its volume. It points
the dashboard, worker, collector and network-policy egress at the external store.

## Network policy and meshes

The policy is on by default. It selects only the pods that carry this release's
`luml.ai/satellite-id` label. That includes the model pods the satellite creates later. The
policy permits:

1. Traffic within the release.
2. Public serving on port 8000.
3. DNS.
4. Outbound HTTP and HTTPS for platform, artifact and package access.
5. The configured external-store port.

The policy does not select unrelated namespace workloads or another satellite release.

The satellite reaches the Kubernetes API through the `kubernetes` service address. Kubernetes
translates the service port to the API server's own port before it evaluates the policy. A
separate policy therefore permits that port, for the satellite pod alone. It does not select
model pods, and model pods mount no service-account token either.

The default port 6443 matches kubeadm clusters. Set `networkPolicy.apiServerPort` to the port
the API server listens on. Set it to 0 on installations whose API server answers on 443 and
need no rule of their own. A release that predates this value keeps the default on upgrade.
It does not lose the rule.

With a service mesh, exclude the satellite's internal port 8001 from public ingress. Keep
direct access among the satellite, sidecars, dashboard and worker. The model Service exposes
only the `http` and `internal` ports of the sidecar. It never exposes the model-server port.
