# Kubernetes satellite

This directory holds the Kubernetes satellite package, its Helm chart (`chart/`) and the kind
scenario (`e2e/`). `RELEASE_CHECKLIST.md` lists what a real OpenShift cluster still has to
prove before a release.

## Local stand on kind

This stand starts one satellite in a kind cluster and pairs it with a Platform on the same
machine. You can then drive deployments, inference and monitoring from the local UI.

You need Docker, `kind`, `helm`, `kubectl` and `python3`. CI pins Helm 3.17.3. We did not test
newer Helm against this chart.

The stand takes about 15 minutes to start the first time. Later starts take about 5 minutes,
because Docker keeps the images in its cache.

### 1. Build the images

The chart never pulls from a registry here. Build every image locally, then load it into the
cluster in step 2.

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

`luml-random-svc` is the model server the Docker satellite runs. Deployments therefore behave
the same way on both stands.

### 2. Create the cluster

The e2e kind configuration does three things:

1. It disables the default CNI, so that Calico can enforce NetworkPolicy the way a real
   cluster does.
2. It labels the node for ingress. The ingress controller then terminates the satellite's
   public URL.
3. It maps port 80 of the node to port 18080 on the host.

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

### 3. Start the Platform

The satellite pairs with the local backend. The backend must run the current branch with its
migrations applied. Point `backend/.env` at the local database, then:

```shell
cd backend
uv run --frozen alembic upgrade head
uv run --frozen uvicorn luml.server:app --host 0.0.0.0 --port 8000
```

Migration `040_satellite_contract` adds the `kit` field to `/satellites/v1/pair`. A backend
that started before you applied it answers the pairing request without that field. The
satellite then never pairs. Start the frontend dev server as usual for the UI on port 5173.

### 4. Create the satellite in the UI

1. Open the orbit's **Satellites** tab.
2. Press **Connect a new satellite**.
3. Give it a name and create it.
4. Copy the API key from the dialog. The dialog shows the key once. The chart needs this key.

You can only replace the key later by regenerating it, and regeneration invalidates the old
key.

Nothing in the dialog selects Docker or Kubernetes. The satellite reports
`kit.kind=kubernetes` when it pairs, and the Platform records the kind from there.

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

Three values need an explanation.

**`satellite.platformUrl`.** Pods reach the host on Docker Desktop through
`host.docker.internal`. The gateway address of the cluster does not lead to the host's ports.

**`monitoring.store.persistence`.** The command keeps the default claim of the monitoring
store. If you set `monitoring.store.persistence.enabled=false`, the data lives in an
`emptyDir`. A restarted store pod then comes back without the recorded inferences, and the
dashboard shows nothing.

**`networkPolicy.enabled=false`.** A development backend listens on port 8000. The policy
permits outbound 80 and 443, the Kubernetes API port and traffic within the release. With
the policy on, the satellite cannot reach a Platform on port 8000, and pairing fails with
`platform request failed`. To keep the policy on, serve the Platform on port 80 or 443, or
place it inside the release the way the kind scenario does with its fake platform.

### 6. Check the pairing

```shell
kubectl -n luml get pods
kubectl -n luml logs -l app.kubernetes.io/component=satellite --tail=50 | grep pair
```

The satellite logs `POST /satellites/v1/pair "HTTP/1.1 200 OK"` and then a compatible
contract. The Platform marks the satellite paired with its base URL, slug and kit. The UI
then offers it as a deployment target. Inference and the monitoring dashboard answer on
`http://localhost:18080`.

### Upgrade the release

Upgrade with `--reset-then-reuse-values`, not with `--reuse-values`. The second flag keeps the
previous values verbatim. A value that the chart gained after the install then renders as
null.

Kubernetes forbids a change to the claim template of a StatefulSet. To switch the store's
persistence on or off after the install:

1. Remove the StatefulSet with `kubectl -n luml delete statefulset <release>-store`.
2. Run the upgrade again.

### Remove the stand

```shell
helm uninstall local --namespace luml
kind delete cluster --name luml-local
```

`helm uninstall` keeps the derivation-key Secret, as the chart README describes. Removing the
cluster removes the Secret with everything else.

## End-to-end scenario

`e2e/run.sh` builds the images, creates its own cluster and installs the chart against an
in-cluster fake platform. It then checks the full path:

1. Pairing, deployment and public inference.
2. Serving while the satellite is down.
3. Replicas and the blocked model port.
4. Monitoring sessions and a chart upgrade.
5. Orphan rules and undeploy.

```shell
bash satellite/implementations/kubernetes/e2e/run.sh vanilla
bash satellite/implementations/kubernetes/e2e/run.sh openshift
```

One run takes about 10 minutes. The script removes the cluster when the run ends. Set
`KEEP_KIND_CLUSTER=1` to keep the cluster for inspection. A failed run prints pod, log and
resource diagnostics before it removes anything.
