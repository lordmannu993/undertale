"""D6: the owner's TEST A-F checklist runs end to end, headless and native.

Piece D6 (brief section 11/12) is the both-side regression pass. Its headless
half is a new ``acceptance`` phase in ``tools/debug_probe.py``: one fresh,
continuous session that plays the Undertale opening, crosses into Yellow the
packaged way, soaks there across rooms, opens Yellow's own dialogue, returns
through the whale and repeats the crossings - printing ``TEST X (...): PASS``
per scenario and ``DEBUG ACCEPTANCE PASS: A B C D E F`` at the end.

Its native half extends ``port/smoke.lua``: the soak counts real ``newImage``
texture decodes through the packaged renderer, the dialogue proof intercepts
fnt_main's glyph quads for one frame (a horizontal row shares one y; the D0
symptom stacked one word per y), and two more packaged round trips census the
player count on every tick. ``tools/native_smoke.sh`` refuses to pass without
``DEBUG ACCEPTANCE PASS`` and the capture it writes.

The acceptance run is also what found the two return-side bugs this piece
fixed (``tests/test_player_identity.py``): the crossing retired room_start's
persistent ``obj_time``/``obj_screen`` and leaked ``global.interact``, freezing
Undertale's player after one round trip.

Scope: headless converted flow (this test) plus the CI native gate (the
static wiring below). No Android device, audio or hand-played route is claimed.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = (ROOT / "yellow_src").is_dir()
live = pytest.mark.skipif(not LIVE, reason="needs the pinned Yellow source: tools/fetch_yellow.py")


@pytest.fixture(scope="module")
def acceptance_output():
    """One quick-budget acceptance run, with the pipeline re-asserted exactly
    like the other Yellow gates (the suite's own tests downgrade
    generated/yellow/)."""
    if not LIVE:
        pytest.skip("needs the pinned Yellow source: tools/fetch_yellow.py")
    import json
    report = ROOT / "generated/yellow/conversion-report.json"
    stage = json.loads(report.read_text())["stage"] if report.is_file() else None
    if stage != "rooms":
        subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "rooms"],
                       cwd=ROOT, check=True)
        subprocess.run([sys.executable, "tools/merge.py"], cwd=ROOT, check=True)
    run = subprocess.run([sys.executable, "tools/debug_probe.py", "--quick",
                          "--phases", "acceptance"],
                         cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert run.returncode == 0, f"the acceptance phase failed:\n{run.stdout}\n{run.stderr}"
    return run.stdout


@live
def test_every_scenario_of_the_owners_checklist_passes(acceptance_output):
    for letter, name in [("A", "Undertale"), ("B", "enter Yellow"), ("C", "Yellow soak"),
                         ("D", "Yellow text"), ("E", "return"), ("F", "repeated transitions")]:
        assert f"TEST {letter} ({name}): PASS" in acceptance_output, \
            f"TEST {letter} ({name}) is missing or did not pass"
    assert "DEBUG ACCEPTANCE PASS: A B C D E F" in acceptance_output


@live
def test_the_undertale_side_is_measured_against_the_d0_baseline(acceptance_output):
    """TEST A's regression gate: the corridor's structural cost (draws per
    frame) is pinned to the D0 baseline number, and every Undertale text draw
    uses an Undertale font record."""
    assert "corridor 48 draws/frame (D0 baseline: 48)" in acceptance_output
    assert "all Undertale font records" in acceptance_output


@live
def test_the_yellow_side_answers_its_two_symptoms_again(acceptance_output):
    """TEST D re-answers the owner's two text symptoms on the fixed build:
    Yellow's own dialogue font, and a layout wider than it is tall."""
    assert "Yellow's own fnt_main (merged " in acceptance_output
    assert "wider than tall (D0 symptom: 55x126)" in acceptance_output


@live
def test_repeated_crossings_keep_one_player_and_no_stale_world(acceptance_output):
    """TEST F's census lines: one player per hop, and instance counts that do
    not grow across the repeats."""
    assert "the every-tick census never saw more than one player" in acceptance_output
    assert "r1->Y players=1 instances=" in acceptance_output
    assert "r3->UT players=1 instances=" in acceptance_output


def test_the_native_gate_requires_the_debug_acceptance_outputs():
    """The CI native gate must fail without the D6 sections: the smoke driver
    has to print and write ``DEBUG ACCEPTANCE PASS``, capture Yellow's dialogue
    rendering, and ``tools/native_smoke.sh`` has to require all of it."""
    smoke = (ROOT / "port/smoke.lua").read_text()
    gate = (ROOT / "tools/native_smoke.sh").read_text()
    # The smoke driver produces the evidence...
    assert 'write("native-debug-acceptance.txt"' in smoke
    assert "DEBUG ACCEPTANCE PASS" in smoke
    assert 'capture("native-yellow-text")' in smoke
    assert "love.graphics.newImage" in smoke, "the soak's texture-decode counter is gone"
    # ...and the gate refuses to pass without it.
    assert "grep -q 'DEBUG ACCEPTANCE PASS' port-test-output/native.log" in gate
    assert "test -s port-test-output/native-debug-acceptance.txt" in gate
    assert "native-yellow-text" in gate
    assert "timeout 720s" in gate, "the wall timeout must cover the acceptance sections"
