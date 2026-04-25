#!/bin/sh
set -e
BASE="${OBJATHOR_ASSETS_BASE_DIR:-/root/.objathor-assets}"
DISPLAY_VALUE="${DISPLAY:-:99}"


if [ -d "$BASE/2023_09_23" ] && [ ! -e "$BASE/holodeck/2023_09_23" ]; then
  mkdir -p "$BASE/holodeck"
  ln -sfn "../2023_09_23" "$BASE/holodeck/2023_09_23"
fi

# AI2-THOR needs a valid X11 display (even in containers). Start Xvfb if absent.
if command -v Xvfb >/dev/null 2>&1; then
  rm -f /tmp/.X${DISPLAY_VALUE#:}-lock
  Xvfb "${DISPLAY_VALUE}" -screen 0 1280x720x24 -nolisten tcp &
  sleep 1
fi

export DISPLAY="${DISPLAY_VALUE}"

python -c "
from ai2thor.build import Build
from ai2thor.platform import Linux64
for cid in ['3213d486cd09bcbafce33561997355983bdf8d1a', '8524eadda94df0ab2dbb2ef5a577e4d37c712897']:
    b = Build(Linux64, cid, False)
    if not b.exists():
        print(f'Downloading AI2-THOR build {cid}...')
        b.download()
    else:
        print(f'AI2-THOR build {cid} already cached')
" &

"$@"
