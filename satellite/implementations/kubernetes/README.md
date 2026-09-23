# Kubernetes satellite

This directory holds the Kubernetes satellite package, its Helm chart (`chart/`), and the
kind scenario (`e2e/`). `RELEASE_CHECKLIST.md` covers what a real OpenShift cluster still
has to prove before a release.

## Local stand on kind

This brings one satellite up in a kind cluster and pairs it with a Platform running on the
same machine, so deployments, inference and monitoring can be driven from the local UI.

Requires Docker, `kind`, `helm`, `kubectl` and `python3`. CI pins Helm 3.17.3; newer Helm
is untested against this chart.

### 1. Build the images

The chart never pulls from a registry here, so every image is built locally and loaded into
the cluster.

```shell
cd <repository root>
docker build --tag luml-local/kubernetes:local \
  --file satellite/implementations/kubernetes/Dockerfile satellite
docker build --tag luml-local/serving:local \
  --file satellite/kit/Dockerfile.serving satellite/kit
docker build --tag luml-local/monitoring:local \
  --file satellite/kit/Dockerfile.monitoring satellite/kit
docker build --tag luml-random-svc:latest model_servers/default
```

`luml-random-svc` is the same model server the Docker satellite runs, so deployments behave
the way they do on the Docker stand.

### 2. Create the cluster

The e2e kind configuration disables the default CNI, labels the node for ingress and maps
the node's port 80 to 18080 on the host. Calico enforces NetworkPolicy the way a real
cluster does, and the ingress controller terminates the satellite's public URL.

```shell
kind create cluster --name luml-local --image kindest/node:v1.32.2 \
  --config satellite/implementations/kubernetes/e2e/kind-config.yaml

kubectl apply -f \
  https://raw.githubusercontent.com/projectcalico/calico/v3.29.3/manifests/calico.yaml
kubectl -n kube-system rollout status daemonset/calico-node --timeout=5m
kubectl wait node --all --for=condition=Ready --timeout=5m

kubectl apply -f \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/kind/deploy.yaml
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller --timeout=5m

for image in luml-local/kubernetes:local luml-local/serving:local \
             luml-local/monitoring:local luml-random-svc:latest; do
  kind load docker-image "$image" --name luml-local
done
```

### 3. Bring the Platform up

The satellite pairs against the local backend, so the backend has to run the current branch
with its migrations applied. Point `backend/.env` at the local database, then:

```shell
cd backend
uv run --frozen alembic upgrade head
uv run --frozen uvicorn luml.server:app --host 0.0.0.0 --port 8000
```

Migration `040_satellite_contract` is what adds the `kit` field to `/satellites/v1/pair`. A
backend started before it is applied answers the pairing request without that field and the
satellite never pairs. Run the frontend dev server as usual for the UI on port 5173.

### 4. Create the satellite in the UI

Open the orbit's **Satellites** tab, press **Connect a new satellite**, give it a name and
create it. The dialog then shows the API key once; that key is the value the chart needs.
It can only be replaced afterwards, by regenerating it, which invalidates the old one.

Nothing in the dialog selects Docker or Kubernetes. The satellite reports
`kit.kind=kubernetes` when it pairs, and the Platform records it from there.

### 5. Install the chart

```shell
helm upgrade --install local satellite/implementations/kubernetes/chart \
  --namespace luml --create-namespace \
  --set-string satellite.token="$SATELLITE_TOKEN" \
  --set satellite.platformUrl=http://host.docker.internal:8000 \
  --set satellite.host=localhost \
  --set satellite.baseUrl=http://localhost:18080 \
  --set satellite.image.repository=luml-local/kubernetes \
  --set satellite.image.tag=local \
  --set satellite.image.pullPolicy=Never \
  --set sidecar.image.repository=luml-local/serving \
  --set sidecar.image.tag=local \
  --set sidecar.image.pullPolicy=Never \
  --set monitoring.image.repository=luml-local/monitoring \
  --set monitoring.image.tag=local \
  --set monitoring.image.pullPolicy=Never \
  --set model.image.repository=luml-random-svc \
  --set model.image.tag=latest \
  --set model.image.pullPolicy=Never \
  --set monitoring.frameAncestors=http://localhost:5173 \
  --set ingress.className=nginx \
  --set networkPolicy.enabled=false \
  --wait --timeout 8m
```

`host.docker.internal` is how pods reach the host on Docker Desktop; the cluster's own
gateway address does not lead to the host's ports.

The monitoring store keeps its default claim. With `monitoring.store.persistence.enabled=false`
its data lives in an `emptyDir`, so a restarted store pod comes back without the recorded
inferences and the dashboard reads empty.

Upgrade this release with `--reset-then-reuse-values` rather than `--reuse-values`: the latter
keeps the previous values verbatim and a value added to the chart since the install renders as
null. Switching the store's persistence on or off afterwards replaces the claim template of a
StatefulSet, which Kubernetes forbids; delete the StatefulSet and upgrade again.

The network policy is disabled because a development backend listens on port 8000, while
the policy permits outbound 80 and 443, the Kubernetes API port and traffic within the
release. With the policy enabled the satellite cannot reach a Platform on 8000 and pairing
fails with `platform request failed`. Serve the Platform on 80 or 443 to keep the policy
on, or place it inside the release the way the kind scenario does with its fake platform.

### 6. Confirm the pairing

```shell
kubectl -n luml get pods
kubectl -n luml logs -l app.kubernetes.io/component=satellite --tail=50 | grep pair
```

The satellite logs `POST /satellites/v1/pair "HTTP/1.1 200 OK"` followed by a compatible
contract, and the Platform marks the satellite paired with its base URL, slug and kit. The
UI then offers it as a deployment target. Inference and the monitoring dashboard answer on
`http://localhost:18080`.

### Tear down

```shell
helm uninstall local --namespace luml
kind delete cluster --name luml-local
```

Uninstalling retains the derivation-key Secret, as the chart README describes. Deleting the
cluster removes it with everything else.

## End-to-end scenario

`e2e/run.sh` builds the images, creates its own cluster, installs the chart against an
in-cluster fake platform and asserts the full path: pairing, deployment, public inference,
satellite outage, replicas, monitoring sessions, chart upgrade, orphan rules and undeploy.

```shell
bash satellite/implementations/kubernetes/e2e/run.sh vanilla
bash satellite/implementations/kubernetes/e2e/run.sh openshift
```

The cluster is deleted when the run ends. Set `KEEP_KIND_CLUSTER=1` to keep it for
inspection; a failed run prints pod, log and resource diagnostics first.
