#!/usr/bin/env bash
# Full-stack end-to-end suites for experiment snapshots: brings a disposable stack up, runs the
# browser specs against it and always tears it down (on success, failure and Ctrl-C).
#
#   frontend/tests/stack/run.sh [platform|flow|all] [extra playwright args...]
#
# platform: Postgres, Redis, MinIO and Azurite in Docker (own project name and free ports),
#   the backend from this worktree (uv), the frontend built from this worktree and served by
#   `vite preview`, experiments written with this SDK (and released luml-sdk 0.5.0 when
#   E2E_OLD_SDK_PYTHON points at a venv holding it) and published with this API client.
# flow: the Flow server from this worktree, its web bundle built from this worktree, on a
#   temporary store (see prepare_flow.py).
#
# Environment: E2E_STORAGES (default "s3,azure"), E2E_OLD_SDK_PYTHON, E2E_KEEP_WORK=1 keeps the
# work directory, E2E_SKIP_BUILD=1 reuses the extras dist and the last frontend (see
# E2E_FRONTEND_DIST) and Flow builds,
# E2E_PORT_BASE (default 41100) where the free-port search starts.
set -euo pipefail
set -m

SUITE="${1:-all}"
shift || true
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
FRONTEND="$REPO/frontend"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/luml-e2e-snap.XXXXXX")"
PROJECT="luml-e2e-snap-$(basename "$WORK" | cut -d. -f2 | tr '[:upper:]' '[:lower:]')"
LOGS="${E2E_LOG_DIR:-$WORK/logs}"
mkdir -p "$LOGS"
PIDS=()
COMPOSE_UP=0

log() { printf '[e2e] %s\n' "$*" >&2; }

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  # Each service runs in its own process group (set -m), so npx/uv and their children go too.
  for pid in "${PIDS[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${PIDS[@]}"; do wait "$pid" 2>/dev/null || true; done
  if [[ $COMPOSE_UP == 1 ]]; then
    docker compose -p "$PROJECT" -f "$HERE/compose.yml" logs --no-color >"$LOGS/compose.log" 2>&1 || true
    docker compose -p "$PROJECT" -f "$HERE/compose.yml" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
  if [[ "${E2E_KEEP_WORK:-0}" != 1 && -z "${E2E_LOG_DIR:-}" ]]; then
    rm -rf "$WORK"
  else
    find "$WORK" -mindepth 1 -maxdepth 1 ! -name logs -exec rm -rf {} + 2>/dev/null || true
    log "logs kept in $LOGS"
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

port_in_use() { ss -Hltn "sport = :$1" 2>/dev/null | grep -q .; }

# Sets the named variable to the next free port (no subshell, so the search moves on).
free_port() {
  local port=$NEXT_PORT
  while port_in_use "$port"; do port=$((port + 1)); done
  NEXT_PORT=$((port + 1))
  printf -v "$1" '%s' "$port"
  export "${1?}"
}
NEXT_PORT="${E2E_PORT_BASE:-41100}"

wait_for() {
  local what=$1 url=$2 seconds=${3:-120}
  local deadline=$((SECONDS + seconds))
  until curl -fsS -o /dev/null "$url" 2>/dev/null; do
    if ((SECONDS > deadline)); then
      log "$what did not answer at $url within ${seconds}s"
      return 1
    fi
    sleep 1
  done
}

EXTRAS_BUILT=0
build_extras() {
  if [[ "${E2E_SKIP_BUILD:-0}" == 1 || $EXTRAS_BUILT == 1 ]]; then return; fi
  EXTRAS_BUILT=1
  log "building @luml/experiments and @luml/attachments"
  (cd "$REPO/extras/js/packages/experiments" && npx vite build >"$LOGS/build-experiments.log" 2>&1)
  (cd "$REPO/extras/js/packages/attachments" && npx vite build >"$LOGS/build-attachments.log" 2>&1)
}

start_platform() {
  for name in E2E_POSTGRES_PORT E2E_REDIS_PORT E2E_MINIO_PORT E2E_AZURITE_PORT E2E_BACKEND_PORT \
    E2E_FRONTEND_PORT; do
    free_port "$name"
  done
  export E2E_COMPOSE_PROJECT="$PROJECT" E2E_COMPOSE_FILE="$HERE/compose.yml"
  log "project $PROJECT, ports pg=$E2E_POSTGRES_PORT redis=$E2E_REDIS_PORT minio=$E2E_MINIO_PORT azurite=$E2E_AZURITE_PORT backend=$E2E_BACKEND_PORT frontend=$E2E_FRONTEND_PORT"

  COMPOSE_UP=1
  docker compose -p "$PROJECT" -f "$HERE/compose.yml" up -d --wait postgres redis minio azurite >"$LOGS/compose-up.log" 2>&1
  docker compose -p "$PROJECT" -f "$HERE/compose.yml" run --rm minio-init >>"$LOGS/compose-up.log" 2>&1

  # The dev env file is docker-compose syntax (unquoted values with spaces), so not sourced.
  while IFS= read -r line; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    export "${line%%=*}=${line#*=}"
  done <"$REPO/dev/backend.env"
  export POSTGRESQL_DSN="postgresql+asyncpg://user:password@127.0.0.1:$E2E_POSTGRES_PORT/df_studio"
  export REDIS_URL="redis://127.0.0.1:$E2E_REDIS_PORT/0"
  export CORS_ORIGINS="http://127.0.0.1:$E2E_FRONTEND_PORT"
  export E2E_BACKEND_URL="http://127.0.0.1:$E2E_BACKEND_PORT"
  export E2E_FRONTEND_URL="http://127.0.0.1:$E2E_FRONTEND_PORT"
  # The seed's own secret is unused; the specs register theirs through the API.
  export DEV_BUCKET_ENDPOINT="127.0.0.1:$E2E_MINIO_PORT" DEV_BUCKET_NAME=seed-unused
  # Azurite's well-known development account; the container is created by azurite_setup.py.
  export E2E_AZURE_CONTAINER=e2e-snapshots
  export E2E_AZURE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:$E2E_AZURITE_PORT/devstoreaccount1;"

  log "migrating and seeding"
  (cd "$REPO/backend" && uv run --frozen alembic upgrade head >"$LOGS/migrate.log" 2>&1)
  (cd "$REPO/backend" && PYTHONPATH="$REPO/backend" uv run --frozen python "$REPO/dev/seed.py" >"$LOGS/seed.log" 2>&1)
  # The free plan allows one orbit; the suite needs one per storage, as a platform admin grants.
  docker compose -p "$PROJECT" -f "$HERE/compose.yml" exec -T postgres psql -U user -d df_studio \
    -c "UPDATE organizations SET orbits_limit = 10, artifacts_limit = 500" >>"$LOGS/seed.log" 2>&1
  (cd "$REPO/backend" && uv run --frozen python "$HERE/azurite_setup.py" \
    "$E2E_AZURE_CONNECTION_STRING" "$E2E_AZURE_CONTAINER" "$E2E_FRONTEND_URL" >"$LOGS/azurite-setup.log" 2>&1)

  log "starting the backend"
  (cd "$REPO/backend" && exec uv run --frozen uvicorn luml.server:app --host 127.0.0.1 \
    --port "$E2E_BACKEND_PORT" >"$LOGS/backend.log" 2>&1) &
  PIDS+=($!)

  build_extras
  # E2E_FRONTEND_DIST keeps the build between runs (with E2E_SKIP_BUILD=1); the backend URL is
  # compiled in, so it is rebuilt when that changed.
  local dist="${E2E_FRONTEND_DIST:-$WORK/frontend-dist}"
  if [[ "${E2E_SKIP_BUILD:-0}" != 1 || "$(cat "$dist/.api-url" 2>/dev/null)" != "$E2E_BACKEND_URL" ]]; then
    log "building the frontend"
    (cd "$FRONTEND" && VITE_API_URL="$E2E_BACKEND_URL" npx vite build --outDir "$dist" \
      --emptyOutDir >"$LOGS/build-frontend.log" 2>&1)
    echo "$E2E_BACKEND_URL" >"$dist/.api-url"
  fi
  (cd "$FRONTEND" && exec npx vite preview --outDir "$dist" --host 127.0.0.1 \
    --port "$E2E_FRONTEND_PORT" --strictPort >"$LOGS/frontend.log" 2>&1) &
  PIDS+=($!)
  wait_for backend "$E2E_BACKEND_URL/docs"
  wait_for frontend "$E2E_FRONTEND_URL/"

  log "writing and publishing experiments"
  export E2E_WORK_DIR="$WORK"
  export E2E_OLD_SDK_PYTHON="${E2E_OLD_SDK_PYTHON:-}"
  (cd "$REPO/sdk/python/sdk" && uv run --frozen python "$HERE/prepare_platform.py" 2>&1 | tee "$LOGS/prepare-platform.log" >&2)
}

start_flow() {
  free_port E2E_FLOW_PORT
  export E2E_FLOW_DIR="$WORK/flow"
  mkdir -p "$E2E_FLOW_DIR"
  build_extras
  if [[ "${E2E_SKIP_BUILD:-0}" != 1 || ! -f "$REPO/lumlflow/lumlflow/static/index.html" ]]; then
    log "building the Flow web app"
    (cd "$REPO/lumlflow/frontend" && npx vite build --outDir "$REPO/lumlflow/lumlflow/static" \
      --emptyOutDir >"$LOGS/build-flow.log" 2>&1)
  fi
  log "writing the Flow stores"
  export E2E_OLD_SDK_PYTHON="${E2E_OLD_SDK_PYTHON:-}"
  (cd "$REPO/sdk/python/sdk" && uv run --frozen python "$HERE/prepare_flow.py" "$E2E_FLOW_DIR" \
    2>&1 | tee "$LOGS/prepare-flow.log" >&2)
  log "starting the Flow server"
  # Own state dir: a Flow daemon of the user (or another run) is never discovered and reused.
  export E2E_FLOW_TOKEN="e2e-flow-session-token"
  export E2E_FLOW_URL="http://127.0.0.1:$E2E_FLOW_PORT"
  (cd "$REPO/lumlflow" && LUMLFLOW_STATE_DIR="$E2E_FLOW_DIR/state" LUMLFLOW_SESSION_TOKEN="$E2E_FLOW_TOKEN" \
    exec uv run --frozen lumlflow ui "$E2E_FLOW_DIR" --path "sqlite://$E2E_FLOW_DIR/store" \
    --host 127.0.0.1 --port "$E2E_FLOW_PORT" --no-browser >"$LOGS/flow.log" 2>&1) &
  PIDS+=($!)
  wait_for "Flow" "$E2E_FLOW_URL/"
}

export E2E_LOGS="$LOGS" E2E_REPO="$REPO" E2E_HERE="$HERE"
case "$SUITE" in
  platform) start_platform ;;
  flow) start_flow ;;
  all) start_platform; start_flow ;;
  *) log "unknown suite $SUITE (platform, flow or all)"; exit 2 ;;
esac

export E2E_SUITE="$SUITE"
if [[ "${E2E_HOLD:-0}" == 1 ]]; then
  # Debugging: keep the stack up and print the environment the specs need; Ctrl-C tears down.
  export -p | grep -E ' (E2E_|DEV_ADMIN_)' >"$WORK/env.sh"
  log "stack is up; source $WORK/env.sh and run: npx playwright test -c $HERE/playwright.config.ts"
  # `wait` returns on a signal, so the trap runs at once (a foreground sleep would delay it).
  while true; do sleep 3600 & wait $!; done
fi
log "running the browser specs"
cd "$FRONTEND"
# In the background and waited for, so Ctrl-C runs the trap at once, which stops it too.
npx playwright test -c "$HERE/playwright.config.ts" "$@" &
PIDS+=($!)
wait $!
