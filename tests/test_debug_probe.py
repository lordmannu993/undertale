"""D0's deliverable must keep running: the headless reproduction harness.

``tools/debug_probe.py`` is the evidence base the debug pieces D1-D5 diff
against (see ``docs/DEBUG_BASELINE.md``). This test runs its ``--quick``
budget and asserts the harness completes and reports every symptom section.
It deliberately does NOT assert the bugs are present: D1-D5 fix them one by
one, each with its own failing-without-the-fix test, and the probe's output
then simply records the fixed state.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LIVE = (ROOT / "yellow_src").is_dir()
live = pytest.mark.skipif(not LIVE, reason="needs the pinned Yellow source: tools/fetch_yellow.py")


@pytest.fixture(scope="module")
def probe_output():
    """One quick-mode run, with the pipeline re-asserted exactly like the other
    Yellow gates do (the suite's own tests downgrade generated/yellow/)."""
    if not LIVE:
        pytest.skip("needs the pinned Yellow source: tools/fetch_yellow.py")
    report = ROOT / "generated/yellow/conversion-report.json"
    stage = json.loads(report.read_text())["stage"] if report.is_file() else None
    if stage != "rooms":
        subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "rooms"],
                       cwd=ROOT, check=True)
        subprocess.run([sys.executable, "tools/merge.py"], cwd=ROOT, check=True)
    run = subprocess.run([sys.executable, "tools/debug_probe.py", "--quick"],
                         cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert run.returncode == 0, f"probe failed:\n{run.stdout}\n{run.stderr}"
    return run.stdout


SECTIONS = ["[boot]", "[font-text]", "[performance]", "[player-identity]",
            "[boat-destination]", "[summary]"]


def test_the_harness_runs_every_evidence_section(probe_output):
    for header in SECTIONS:
        assert f"== {header} ==" in probe_output, f"missing section {header}"
    assert "probe completed:" in probe_output


def test_the_harness_reports_each_reported_symptom(probe_output):
    # The five owner-reported symptoms each leave a traceable line, whether
    # reproduced (SYMPTOM ...), quantified (performance ratios) or narrowed
    # down (player census, boat cases). D1-D5 change what these lines say.
    assert "draw_set_font:" in probe_output, "font evidence section ran"
    assert "layout of the marker under active font" in probe_output, "wrap evidence ran"
    assert "us/tick=" in probe_output, "performance table ran"
    assert "max simultaneous player instances across all crossings:" in probe_output
    assert "boat destination cases:" in probe_output


def test_the_harness_keeps_the_fusion_invariants(probe_output):
    # Whatever the probe finds, it must not observe a broken fusion: exactly
    # one Player at every census and no more than one at once.
    assert "max simultaneous player instances across all crossings: 1" in probe_output
    for line in probe_output.splitlines():
        if "frisk=" in line and "clover=" in line:
            frisk = int(line.split("frisk=")[1].split()[0])
            clover = int(line.split("clover=")[1].split()[0])
            assert frisk + clover == 1, f"a census saw {frisk}+{clover} players: {line}"


def test_the_probe_boots_in_its_cheapest_phase(probe_output):
    """The boot-only phase is the harness's own smoke: manifest, world seed and
    two ticks, nothing else. (The driver refuses to run at all when the Yellow
    conversion report is not at stage 'rooms'; the module fixture re-asserts
    that stage first, exactly like the other Yellow gates.)"""
    run = subprocess.run([sys.executable, "tools/debug_probe.py", "--quick",
                          "--phases", "boot"], cwd=ROOT, capture_output=True,
                         text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    assert "== [boot] ==" in run.stdout
    assert "== [font-text] ==" not in run.stdout, "phase filter must skip other sections"
    assert "probe completed:" in run.stdout
