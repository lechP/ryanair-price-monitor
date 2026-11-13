#!/usr/bin/env bash
# Fetch current prices for config/trips.json and send them to ntfy.
# Reads NTFY_TOPIC (and optional NTFY_SERVER, NTFY_TOKEN) from .env in the repository root.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${NTFY_TOPIC:-}" ]]; then
  echo "NTFY_TOPIC is empty. Put your topic in $repo_root/.env (see .env.example)." >&2
  exit 1
fi

uv run python -m ryanair_price_monitor.cli --notify "$@"
