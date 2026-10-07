---
sidebar_position: 5
---

# How To Run A Satellite On Kubernetes

The Kubernetes Satellite runs each model deployment as a Deployment, Service and Ingress in one namespace of your cluster. It is installed with a Helm chart and supports vanilla Kubernetes and OpenShift.

First register the Satellite in Luml and copy its token, as described in [How To Connect A Satellite](./satellite.md#register-the-satellite-in-luml). The Satellite reports that it runs on Kubernetes when it pairs.

## What gets installed

The chart is published to GitHub Container Registry as an OCI artifact, `oci://ghcr.io/luml-ai/charts/luml-satellite-kubernetes`. It installs:

| Component | Image | Purpose |
|---|---|---|
| Satellite | `ghcr.io/luml-ai/luml-satellite-kubernetes` | Pairs with Luml, polls for tasks and manages model workloads through the Kubernetes API |
| Serving sidecar | `ghcr.io/luml-ai/luml-satellite-serving` | Runs next to every model, authorizes and records inference requests |
| Model | `ghcr.io/luml-ai/luml-model-server` | The image every model pod starts from |
| Monitoring dashboard and worker | `ghcr.io/luml-ai/luml-satellite-monitoring` | Computes monitoring results and serves the dashboard shown in Luml |
| Collector | `otel/opentelemetry-collector-contrib` | Receives inference traces |
| Store | GreptimeDB StatefulSet | Keeps inference events and monitoring results |

Each chart version pins matching image versions, so installing or upgrading the chart moves all components together.

## Requirements

- Kubernetes 1.27 or newer, or OpenShift.
- Helm 3.
- An ingress controller and a public host name that routes to it. Inference endpoints and the monitoring dashboard are served under this host.
- A default storage class, unless you disable persistence of the monitoring store.
- Outbound HTTPS from the cluster to `api.luml.ai`, to your buckets and to package indexes.

## Install

```bash
helm install my-satellite oci://ghcr.io/luml-ai/charts/luml-satellite-kubernetes \
  --namespace luml --create-namespace \
  --set-string satellite.token="$SATELLITE_TOKEN" \
  --set satellite.host=models.example.com \
  --set ingress.className=nginx \
  --set monitoring.frameAncestors=https://app.luml.ai
```

Without `--version`, Helm installs the latest chart. Pass `--version <x.y.z>` to install a specific release.

| Value | Meaning |
|---|---|
| `satellite.token` | Token issued by Luml. Use `satellite.existingSecret` and `satellite.existingSecretKey` to read it from an existing Secret instead. |
| `satellite.host` | Public host that routes to the chart's Ingress. |
| `satellite.baseUrl` | Full public URL, if it differs from the one derived from the host. Without it the chart uses `https://` when a TLS Secret is configured, otherwise `http://`. |
| `ingress.className`, `ingress.tls.secretName` | Ingress class and optional TLS Secret. |
| `monitoring.frameAncestors` | Origins allowed to embed the monitoring dashboard. Set it to `https://app.luml.ai`. |
| `networkPolicy.enabled` | On by default. Limits traffic of the Satellite and its models to what they need. |

The release name is the Satellite's identity inside its namespace. To run several Satellites in one namespace, give each its own release name, token and host.

Check that the Satellite paired:

```bash
kubectl -n luml get pods
kubectl -n luml logs -l app.kubernetes.io/component=satellite --tail=50
```

The Satellite's status in Luml switches to *Connected*, and it becomes available as a deployment target.

## OpenShift

Add the OpenShift preset to the install command:

```bash
  --set podSecurity.preset=openshift \
  --set ingress.className=openshift-default \
  --set-string ingress.annotations."route\.openshift\.io/termination"=edge
```

The preset leaves user and group IDs to the security context constraint and keeps a standard Ingress, from which OpenShift creates a Route.

## Upgrade

```bash
helm upgrade my-satellite oci://ghcr.io/luml-ai/charts/luml-satellite-kubernetes \
  --namespace luml --reuse-values
```

Values missing from an older release fall back to the defaults of the new chart.

## Keys and secrets

The chart keeps a derivation key in a separate Secret. Helm generates it on the first install and keeps it when you uninstall the release. Back it up before you uninstall.

After you rotate the token in an existing Secret, restart the Satellite:

```bash
kubectl -n luml rollout restart deployment -l luml.ai/satellite-id=my-satellite
```

## More options

GPU placement, a shared artifact cache, an external GreptimeDB or object storage for the monitoring store, probe timeouts and security contexts are configured through chart values. See the [chart README](https://github.com/luml-ai/luml/blob/main/satellite/implementations/kubernetes/chart/README.md) for the full list.
