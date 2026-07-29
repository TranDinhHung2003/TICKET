#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Chuyen sang Token Shop Java (MB Bank + SePay)..."
exec ./token-shop/start_shop.sh
