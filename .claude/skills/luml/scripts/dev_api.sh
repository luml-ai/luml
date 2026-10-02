# Curl helpers for the LUML dev stack. Source it, don't run it:
#
#   source ~/.claude/skills/luml/scripts/dev_api.sh
#   a "$API/v1/organizations/$ORG/orbits" | jq
#
# Env overrides: API (default http://localhost:8000), DEV_EMAIL, DEV_PASSWORD,
# COMPOSE_FILE (default dev/docker-compose.yml relative to the repo root).
# Works in zsh and bash.

API="${API:-http://localhost:8000}"
DEV_EMAIL="${DEV_EMAIL:-admin@example.com}"
DEV_PASSWORD="${DEV_PASSWORD:-admin12345}"
COMPOSE_FILE="${COMPOSE_FILE:-dev/docker-compose.yml}"

# login <email> <password> → prints the access token (from Set-Cookie).
login() {
  curl -s -D - -o /dev/null -X POST "$API/v1/auth/signin" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}" \
    | tr -d '\r' | sed -n 's/^[Ss]et-[Cc]ookie: access_token=\([^;]*\).*/\1/p'
}

# login_cookies <email> <password> → prints "access_token=…; refresh_token=…" for a Cookie: header.
login_cookies() {
  curl -s -D - -o /dev/null -X POST "$API/v1/auth/signin" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}" \
    | tr -d '\r' | sed -n 's/^[Ss]et-[Cc]ookie: \(\(access\|refresh\)_token=[^;]*\).*/\1/p' \
    | paste -sd ';' - | sed 's/;/; /g'
}

# a  → curl -s with bearer; A → curl -i -s with bearer. Both pass args through.
a() { curl -s -H "Authorization: Bearer $TOKEN" "$@"; }
A() { curl -i -s -H "Authorization: Bearer $TOKEN" "$@"; }

# j  → same as a, but JSON body: j POST "$API/v1/…" '{"name":"x"}'
j() { curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -X "$1" "$2" -d "$3"; }

# psql inside the postgres container; extra args go to psql (-c, -tA, …).
psql() { docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U user -d df_studio "$@"; }

# backend_errors [since] → app-level frames + final exception of recent 500s.
backend_errors() {
  docker compose -f "$COMPOSE_FILE" logs --no-log-prefix --since "${1:-5m}" backend 2>&1 \
    | grep -E '/app/luml|^(sqlalchemy|asyncpg|python_http_client)\.|Error:|" 500 '
}

TOKEN="$(login "$DEV_EMAIL" "$DEV_PASSWORD")"
if [ -z "$TOKEN" ]; then
  echo "dev_api.sh: sign-in failed at $API (is the backend up?)" >&2
else
  ORG="$(a "$API/v1/users/me/organizations" | jq -r '.[0].id')"
  ORBIT="$(a "$API/v1/organizations/$ORG/orbits" | jq -r '.[0].id')"
  echo "API=$API ORG=$ORG ORBIT=$ORBIT (helpers: login login_cookies a A j psql backend_errors)"
fi
