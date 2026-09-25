#!/usr/bin/env bash
set -euo pipefail

PRESET="${1:-}"
if [[ "$PRESET" != "vanilla" && "$PRESET" != "openshift" ]]; then
  echo "usage: $0 <vanilla|openshift>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KUBERNETES_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPOSITORY_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
CHART="$KUBERNETES_ROOT/chart"
CLUSTER_NAME="luml-e2e-$PRESET"
NAMESPACE="luml-e2e-$PRESET"
RELEASE="luml-e2e"
HOST="$PRESET.satellite.example.test"
RANDOM_USER=10001
if [[ "$PRESET" == "openshift" ]]; then
  RANDOM_USER=1000710000
fi
WORK_DIR="$(mktemp -d)"

diagnostics() {
  kubectl get pods,deployments,statefulsets,services,ingresses,networkpolicies,pvc -A -o wide || true
  kubectl -n "$NAMESPACE" describe pods || true
  for pod in $(kubectl -n "$NAMESPACE" get pods -o name 2>/dev/null); do
    kubectl -n "$NAMESPACE" logs "$pod" --all-containers --tail=200 || true
  done
}

cleanup() {
  status=$?
  if [[ $status -ne 0 ]]; then
    diagnostics
  fi
  if [[ "${KEEP_KIND_CLUSTER:-0}" != "1" ]]; then
    kind delete cluster --name "$CLUSTER_NAME" >/dev/null 2>&1 || true
  fi
  rm -rf "$WORK_DIR"
  return "$status"
}
trap cleanup EXIT

for command in docker helm kind kubectl python3; do
  command -v "$command" >/dev/null || {
    echo "$command is required" >&2
    exit 1
  }
done

cd "$REPOSITORY_ROOT"

docker build \
  --tag luml-e2e/kubernetes:local \
  --file satellite/implementations/kubernetes/Dockerfile \
  satellite
docker build \
  --tag luml-e2e/serving:local \
  --file satellite/kit/Dockerfile.serving \
  satellite/kit
docker build \
  --tag luml-e2e/monitoring:local \
  --file satellite/kit/Dockerfile.monitoring \
  satellite/kit
docker build \
  --tag luml-e2e/stub-model:local \
  --file satellite/kit/Dockerfile.stub-model \
  satellite/kit

kind create cluster \
  --name "$CLUSTER_NAME" \
  --image kindest/node:v1.32.2 \
  --config "$SCRIPT_DIR/kind-config.yaml"

kubectl apply -f \
  https://raw.githubusercontent.com/projectcalico/calico/v3.29.3/manifests/calico.yaml
kubectl -n kube-system rollout status daemonset/calico-node --timeout=5m
kubectl wait node --all --for=condition=Ready --timeout=5m

kubectl apply -f \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/kind/deploy.yaml
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller --timeout=5m

for image in kubernetes serving monitoring stub-model; do
  kind load docker-image "luml-e2e/$image:local" --name "$CLUSTER_NAME"
done

kubectl create namespace "$NAMESPACE"
if [[ "$PRESET" == "openshift" ]]; then
  kubectl label namespace "$NAMESPACE" \
    pod-security.kubernetes.io/enforce=restricted \
    pod-security.kubernetes.io/enforce-version=latest
fi

PYTHONPATH="$KUBERNETES_ROOT" python3 -m e2e.create_state \
  "$REPOSITORY_ROOT/satellite/kit/e2e/fixtures/stub-model/stub.json" \
  "$WORK_DIR/state.json"
kubectl -n "$NAMESPACE" create configmap fake-platform-state \
  --from-file="$WORK_DIR/state.json"
sed \
  -e "s/__RUN_AS_USER__/$RANDOM_USER/g" \
  -e "s/__FS_GROUP__/$RANDOM_USER/g" \
  "$SCRIPT_DIR/fake-platform.yaml" | kubectl -n "$NAMESPACE" apply -f -
kubectl -n "$NAMESPACE" rollout status deployment/fake-platform --timeout=5m

HELM_ARGUMENTS=(
  upgrade --install "$RELEASE" "$CHART"
  --namespace "$NAMESPACE"
  --values "$CHART/ci/$PRESET-values.yaml"
  --set-string satellite.derivationKey=
  --set satellite.platformUrl=http://fake-platform:8090
  --set satellite.host="$HOST"
  --set satellite.pollIntervalSeconds=1
  --set satellite.image.repository=luml-e2e/kubernetes
  --set satellite.image.tag=local
  --set satellite.image.pullPolicy=Never
  --set model.image.repository=luml-e2e/stub-model
  --set model.image.tag=local
  --set model.image.pullPolicy=Never
  --set sidecar.image.repository=luml-e2e/serving
  --set sidecar.image.tag=local
  --set sidecar.image.pullPolicy=Never
  --set sidecar.cacheTtlSeconds=300
  --set monitoring.image.repository=luml-e2e/monitoring
  --set monitoring.image.tag=local
  --set monitoring.image.pullPolicy=Never
  --set monitoring.store.persistence.enabled=false
  --set monitoring.worker.intervalSeconds=5
  --set monitoring.worker.windowSeconds=60
  --set ingress.className=nginx
  --set sharedCache.enabled=false
  --set gpu.enabled=true
  --set deploymentLimits.cpuMillicores.minimum=100
  --set deploymentLimits.cpuMillicores.default=100
  --set-json 'deploymentLimits.memory.values=["128Mi"]'
  --set deploymentLimits.memory.default=128Mi
  --set deploymentLimits.healthCheckTimeoutSeconds.default=300
  --wait
  --timeout 10m
)
if [[ "$PRESET" == "openshift" ]]; then
  HELM_ARGUMENTS+=(
    --set-json "podSecurity.podContext={\"runAsNonRoot\":true,\"runAsUser\":$RANDOM_USER,\"fsGroup\":$RANDOM_USER,\"seccompProfile\":{\"type\":\"RuntimeDefault\"}}"
    --set-json "podSecurity.containerContext={\"runAsNonRoot\":true,\"runAsUser\":$RANDOM_USER,\"allowPrivilegeEscalation\":false,\"capabilities\":{\"drop\":[\"ALL\"]}}"
  )
fi
helm "${HELM_ARGUMENTS[@]}"

sed \
  -e "s/__RUN_AS_USER__/$RANDOM_USER/g" \
  -e "s/__FS_GROUP__/$RANDOM_USER/g" \
  "$SCRIPT_DIR/network-probe.yaml" | kubectl -n "$NAMESPACE" apply -f -
kubectl -n "$NAMESPACE" wait pod/network-probe --for=condition=Ready --timeout=2m

cd "$KUBERNETES_ROOT"
python3 -m e2e.test_kind \
  --preset "$PRESET" \
  --namespace "$NAMESPACE" \
  --release "$RELEASE" \
  --host "$HOST" \
  --chart "$CHART" \
  --random-user "$RANDOM_USER"
