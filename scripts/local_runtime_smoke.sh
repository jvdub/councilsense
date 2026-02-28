#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.local.yml"

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
WEB_BASE_URL="${WEB_BASE_URL:-http://localhost:3000}"
AUTH_SESSION_SECRET="${AUTH_SESSION_SECRET:-local-runtime-secret}"
export AUTH_SESSION_SECRET
CITY_ID="city-eagle-mountain-ut"
MEETING_ID="meeting-local-runtime-smoke-001"

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "docker compose or docker-compose is required" >&2
  exit 1
fi

cleanup() {
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" down --remove-orphans >/dev/null 2>&1 || true
}

wait_for_url() {
  local url="$1"
  local label="$2"
  for _ in $(seq 1 60); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "ready: ${label} (${url})"
      return 0
    fi
    sleep 1
  done
  echo "timeout waiting for ${label} at ${url}" >&2
  exit 1
}

api_request() {
  local method="$1"
  local path="$2"
  local body="${3:-}"

  if [[ -n "${body}" ]]; then
    curl -fsS -X "${method}" \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: application/json" \
      "${API_BASE_URL}${path}" \
      -d "${body}"
    return
  fi

  curl -fsS -X "${method}" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${API_BASE_URL}${path}"
}

TOKEN="$(python3 - <<'PY'
import base64
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta


def b64url(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


secret = os.environ["AUTH_SESSION_SECRET"]
header = b64url({"alg": "HS256", "typ": "JWT"})
exp = int((datetime.now(tz=UTC) + timedelta(minutes=30)).timestamp())
payload = b64url({"sub": "user-local-runtime-smoke", "exp": exp})
signing_input = f"{header}.{payload}"
digest = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
print(f"{signing_input}.{signature}")
PY
)"

cleanup
"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" up -d --build

wait_for_url "${API_BASE_URL}/docs" "api"
wait_for_url "${WEB_BASE_URL}" "web"

api_request GET "/v1/me" | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["home_city_id"] is None'
api_request PATCH "/v1/me/bootstrap" '{"home_city_id":"city-eagle-mountain-ut"}' \
  | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["home_city_id"] == "city-eagle-mountain-ut"'

"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" exec -T api python -m councilsense.app.local_runtime process-fixture >/tmp/process-fixture-1.json
api_request GET "/v1/cities/${CITY_ID}/meetings" \
  | python3 -c 'import json,sys; data=json.load(sys.stdin); assert len(data["items"]) >= 1'
api_request GET "/v1/meetings/${MEETING_ID}" \
  | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["id"] == "meeting-local-runtime-smoke-001"'

for _ in $(seq 1 30); do
  state_json="$("${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" exec -T api python -m councilsense.app.local_runtime smoke-state | tail -n 1)"
  sent_count="$(printf '%s' "${state_json}" | python3 -c 'import json,sys; s=json.loads(sys.stdin.read()); print(s["state"]["outbox_status_counts"].get("sent",0))')"
  if [[ "${sent_count}" -ge 1 ]]; then
    break
  fi
  sleep 1
done

state_json="$("${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" exec -T api python -m councilsense.app.local_runtime smoke-state | tail -n 1)"
printf '%s' "${state_json}" | python3 -c 'import json,sys; s=json.loads(sys.stdin.read()); assert s["state"]["outbox_status_counts"].get("sent",0) == 1'

"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" exec -T api python -m councilsense.app.local_runtime process-fixture >/tmp/process-fixture-2.json
"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" exec -T api python -m councilsense.app.local_runtime worker-once >/tmp/worker-once-2.json

state_json="$("${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" exec -T api python -m councilsense.app.local_runtime smoke-state | tail -n 1)"
printf '%s' "${state_json}" | python3 -c 'import json,sys; s=json.loads(sys.stdin.read()); assert s["state"]["outbox_status_counts"].get("sent",0) == 1'

echo "local runtime smoke passed"
