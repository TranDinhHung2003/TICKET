#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

export APP_BASE_URL="${APP_BASE_URL:-http://localhost:8080}"
export SEPAY_BANK="${SEPAY_BANK:-MB}"
export SEPAY_ACCOUNT="${SEPAY_ACCOUNT:-0910108069999}"
export SEPAY_ACCOUNT_NAME="${SEPAY_ACCOUNT_NAME:-MB BANK}"

echo "============================================"
echo " FB Poster - Token Shop (tu dong)"
echo " MB Bank STK: 0910108069999"
echo "============================================"

if command -v xdg-open >/dev/null 2>&1; then
  (sleep 3 && xdg-open "$APP_BASE_URL") >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
  (sleep 3 && open "$APP_BASE_URL") >/dev/null 2>&1 &
fi

if [[ -f target/token-shop-0.0.1-SNAPSHOT.jar ]]; then
  exec java -jar target/token-shop-0.0.1-SNAPSHOT.jar
fi

exec ./mvnw -DskipTests spring-boot:run
