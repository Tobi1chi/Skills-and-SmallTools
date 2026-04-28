#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: capture-keats-auth-state.sh <course-url> <auth-state.json> [browser]" >&2
  exit 1
fi

course_url="$1"
auth_state="$2"
browser="${3:-chromium}"
script_dir="$(cd "$(dirname "$0")" && pwd)"

uv run --with playwright python "$script_dir/capture_keats_auth_state.py" \
  --course-url "$course_url" \
  --auth-state "$auth_state" \
  --browser "$browser"
