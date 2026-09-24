#!/usr/bin/env bash
# Native Linux LÖVE regression; no Android/device-fidelity claim.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p port-test-output
command -v love >/dev/null || { echo 'Install LOVE, xvfb and xauth for native validation.' >&2; exit 1; }
set +e
# The wall timeout covers the scripted Undertale opening plus the fused-world
# section (three rooms, two crossings, three captures) on a merged archive; it
# was raised when the fused gates were added - keep it raised, or the gate flakes.
ALSOFT_DRIVERS=null LIBGL_ALWAYS_SOFTWARE=1 timeout 600s \
  xvfb-run -a -s '-screen 0 1600x900x24' \
  love "${1:-artifacts/undertale-love-experimental.love}" --smoke-test \
  >port-test-output/native.log 2>&1
status=$?
set -e
cat port-test-output/native.log
if [[ "$status" != 0 ]]; then
  python3 - <<'PY'
from pathlib import Path
p=Path('port-test-output/native-error.txt')
text=p.read_text() if p.exists() else Path('port-test-output/native.log').read_text()[-5000:]
text=('Native LOVE regression failed.\n'+text).replace('%','%25').replace('\r','%0D').replace('\n','%0A')
print('::error title=Native LOVE regression::'+text)
PY
  exit "$status"
fi
grep -q 'NATIVE SMOKE PASS' port-test-output/native.log
# native-toriel-walk is the recovered-path gate: Toriel must be drawn where
# path_torielwalk1 walked her, not where room_ruins1 placed her. The
# native-fusion-* captures are the merged-build gates: the fused boat ride,
# Frisk rendered in Yellow, snow drawn in the Snowdin forest, and the
# versioned merged save. The smoke driver only produces them for a merged
# archive, and both CI jobs package merged.
for image in native-flowers native-corridor native-greeting native-flowey native-integer-scale native-toriel-walk native-fusion-yellow native-fusion-snowdin native-fusion-back; do
  test -s "port-test-output/$image.png"
done
grep -q 'fused boat ride' port-test-output/native.log || {
  echo 'The native gate never ran the fused-world section; a merged archive must cross between the games.' >&2
  exit 1
}
# Piece 5a's packaged-runtime state probe is required, not merely logged.
grep -q 'CORE PLAYER PASS' port-test-output/native-unified-player.txt
# Piece 8's acceptance probe: the carried item and equipped gear crossed with
# the player through the packaged archive's own River Person and whale rides.
grep -q 'ACCEPTANCE PASS' port-test-output/native-acceptance.txt
