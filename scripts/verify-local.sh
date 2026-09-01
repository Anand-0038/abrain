#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_URL="${ABRAIN_VERIFY_FRONTEND_URL:-http://127.0.0.1:3125/}"
BACKEND_HEALTH_URL="${ABRAIN_VERIFY_HEALTH_URL:-http://127.0.0.1:8000/api/health}"

cd "$ROOT_DIR"

if ! command -v corepack >/dev/null 2>&1; then
  echo "corepack is required" >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for the runtime boundary checks" >&2
  exit 1
fi

echo "Checking backend health: $BACKEND_HEALTH_URL"
health="$(curl --fail --silent --show-error "$BACKEND_HEALTH_URL")"
case "$health" in
  *'"status":"ok"'*) ;;
  *)
    echo "Backend health response did not report status=ok: $health" >&2
    exit 1
    ;;
esac

echo "Checking frontend response: $FRONTEND_URL"
curl --fail --silent --show-error --head "$FRONTEND_URL" >/dev/null

echo "Checking public-boundary files"
if git ls-files | grep -E '(^|/)\.env($|\.(local|development|production))|(^|/)hack/|(^|/).*\.sqlite3?$' >/dev/null; then
  echo "A private environment, hack, or SQLite file is tracked" >&2
  exit 1
fi

echo "Running static, test, build, and diff gates"
corepack pnpm format:check
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test
corepack pnpm build
git diff --check

echo "LOCAL ACCEPTANCE PASS"
echo "memory_boundary=sibyl_local"
echo "frontend=$FRONTEND_URL"
echo "backend_health=$BACKEND_HEALTH_URL"
