#!/usr/bin/env bash
# Native Linux LÖVE regression; no Android/device-fidelity claim.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p port-test-output
command -v love >/dev/null || { echo 'Install LOVE, xvfb and xauth for native validation.' >&2; exit 1; }
set +e
ALSOFT_DRIVERS=null LIBGL_ALWAYS_SOFTWARE=1 timeout 420s \
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
# path_torielwalk1 walked her, not where room_ruins1 placed her.
for image in native-flowers native-corridor native-greeting native-flowey native-integer-scale native-toriel-walk; do
  test -s "port-test-output/$image.png"
done
