#!/bin/sh
# Railway wrapper for nanobot (runs under Railway's init, not as PID 1).
#  1. railway_config.py writes the variable-driven parts of config.json on the
#     volume (WebUI auth, port, LLM keys, Telegram/Discord/Slack) and keeps
#     everything edited in the WebUI.
#  2. Upstream's entrypoint.sh chowns the volume, drops to the nanobot user
#     (UID 1000) and execs `nanobot <command> --config <file>`.
set -eu

config_dir="${HOME:-/home/nanobot}/.nanobot"
config="${config_dir}/config.json"

mkdir -p "$config_dir"
/app/.venv/bin/python /app/railway/railway_config.py "$config"

if [ "$#" -eq 0 ]; then
    set -- gateway
fi

exec /usr/local/bin/entrypoint.sh "$@" --config "$config"
