#!/usr/bin/env bash
# Deploy Nos to Railway (backend + frontend) using Redis Cloud from .env
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PROJECT_ID="${RAILWAY_PROJECT_ID:-1bf3c02a-27b4-462a-b68a-b8816c987216}"
BACKEND_SERVICE="${RAILWAY_BACKEND_SERVICE:-nos-backend}"
FRONTEND_SERVICE="${RAILWAY_FRONTEND_SERVICE:-Berkeley-AI-Hackathon}"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example and add REDIS_URL + API keys."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

echo "==> Setting backend variables on $BACKEND_SERVICE"
railway link -p "$PROJECT_ID" -e production -s "$BACKEND_SERVICE"
railway variable set \
  REDIS_URL="$REDIS_URL" \
  ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  DEEPGRAM_API_KEY="${DEEPGRAM_API_KEY:-}" \
  ANTHROPIC_MODEL_HANDOFF="${ANTHROPIC_MODEL_HANDOFF:-}" \
  ANTHROPIC_MODEL_TIMELINE="${ANTHROPIC_MODEL_TIMELINE:-}" \
  -s "$BACKEND_SERVICE" --skip-deploys

read_domain() {
  python3 -c "
import json, sys
data = json.load(sys.stdin)
if isinstance(data.get('domain'), str):
    print(data['domain'])
elif data.get('domains'):
    print(data['domains'][0])
else:
    raise SystemExit('no domain found in railway domain output')
"
}

echo "==> Deploying backend (FastAPI — uses backend/Dockerfile)"
cp railway.backend.toml railway.toml
railway up -y -d --no-gitignore -s "$BACKEND_SERVICE"

BACKEND_URL="$(railway domain -s "$BACKEND_SERVICE" --json | read_domain)"
echo "    Backend: $BACKEND_URL"

echo "==> Setting frontend variables on $FRONTEND_SERVICE"
railway link -p "$PROJECT_ID" -e production -s "$FRONTEND_SERVICE"
railway variable set PYTHON_BACKEND_URL="$BACKEND_URL" -s "$FRONTEND_SERVICE" --skip-deploys

echo "==> Deploying frontend (PYTHON_BACKEND_URL=$BACKEND_URL)"
cp railway.frontend.toml railway.toml
railway up -y -d --no-gitignore -s "$FRONTEND_SERVICE"

FRONTEND_URL="$(railway domain -s "$FRONTEND_SERVICE" --json | read_domain)"
echo "    Frontend: $FRONTEND_URL"

rm -f railway.toml
echo "==> Done. Open $FRONTEND_URL"
