#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 4 ]]; then
  echo "Usage: download-keats-course.sh <course-url> <cookie-file> [output-dir]" >&2
  echo "       download-keats-course.sh <course-url> --auth-state <auth-state.json> [output-dir]" >&2
  exit 1
fi

course_url="$1"
cookie_arg="$2"
auth_state=""
cookie_file=""
output_dir=""
script_dir="$(cd "$(dirname "$0")" && pwd)"

if [[ "$cookie_arg" == "--auth-state" ]]; then
  if [[ $# -lt 3 ]]; then
    echo "Missing auth state file after --auth-state" >&2
    exit 1
  fi
  auth_state="$3"
  output_dir="${4:-}"
  if [[ ! -f "$auth_state" ]]; then
    echo "Auth state file not found: $auth_state" >&2
    exit 1
  fi
else
  cookie_file="$cookie_arg"
  output_dir="${3:-}"
  if [[ ! -f "$cookie_file" ]]; then
    echo "Cookie file not found: $cookie_file" >&2
    exit 1
  fi
fi

if [[ -z "$output_dir" ]]; then
  course_id="$(printf '%s' "$course_url" | sed -n 's/.*[?&]id=\([0-9][0-9]*\).*/\1/p')"
  if [[ -z "$course_id" ]]; then
    course_id="unknown"
  fi
  output_dir="$PWD/downloads/keats_${course_id}/weeks"
fi

if [[ -n "$auth_state" ]]; then
  uv run --with requests --with beautifulsoup4 python "$script_dir/download_keats_course.py" \
    --course-url "$course_url" \
    --auth-state "$auth_state" \
    --output-dir "$output_dir"
else
  uv run --with requests --with beautifulsoup4 python "$script_dir/download_keats_course.py" \
    --course-url "$course_url" \
    --cookie-file "$cookie_file" \
    --output-dir "$output_dir"
fi

printf 'Saved to %s\n' "$output_dir"
