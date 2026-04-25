#!/bin/sh
set -e
BASE="${OBJATHOR_ASSETS_BASE_DIR:-/root/.objathor-assets}"
DISPLAY_VALUE="${DISPLAY:-:99}"

# ObLLoMov expects holodeck/<version>/...; objathor tar often unpacks to <version>/assets only.
if [ -d "$BASE/2023_09_23" ] && [ ! -e "$BASE/holodeck/2023_09_23" ]; then
  mkdir -p "$BASE/holodeck"
  ln -sfn "../2023_09_23" "$BASE/holodeck/2023_09_23"
fi

# AI2-THOR needs a valid X11 display (even in containers). Start Xvfb if absent.
if command -v Xvfb >/dev/null 2>&1; then
  if ! pgrep -f "Xvfb ${DISPLAY_VALUE}" >/dev/null 2>&1; then
    Xvfb "${DISPLAY_VALUE}" -screen 0 1280x720x24 -nolisten tcp &
    # Give the virtual display a moment to come up.
    sleep 1
  fi
fi

export DISPLAY="${DISPLAY_VALUE}"
exec "$@"
