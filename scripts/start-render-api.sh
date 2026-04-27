#!/usr/bin/env bash
set -euo pipefail

if command -v tor >/dev/null 2>&1; then
  tor --SocksPort 9050 --RunAsDaemon 1 || true
fi

exec uvicorn backend.app:app --host 0.0.0.0 --port "${PORT:-10000}"
