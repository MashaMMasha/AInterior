#!/bin/sh
set -e
BASE="${OBJATHOR_ASSETS_BASE_DIR:-/root/.objathor-assets}"
# ObLLoMov expects holodeck/<version>/...; objathor tar often unpacks to <version>/assets only.
if [ -d "$BASE/2023_09_23" ] && [ ! -e "$BASE/holodeck/2023_09_23" ]; then
  mkdir -p "$BASE/holodeck"
  ln -sfn "../2023_09_23" "$BASE/holodeck/2023_09_23"
fi
exec "$@"
