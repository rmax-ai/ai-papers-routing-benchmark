#!/usr/bin/env bash
# Provider credentials are sourced from a local, unpublished env file (chmod 600)
# holding OPENAI_API_KEY, GEMINI_API_KEY, and DEEPSEEK_API_KEY. Point
# DQ84_ENV_FILE at it (default shown); the file is never committed.
set -euo pipefail
set -a
. "${DQ84_ENV_FILE:-$HOME/.config/dq84-live-env.sh}"
set +a
exec python3 bench.py run
