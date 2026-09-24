"""The live "Proceed ❤️" objective list must stay findable and unambiguous.

The cross-session trigger works only if a brand-new session (branched from
``master``, no chat history) can read ``AGENTS.md`` → the live queue → the ordered
piece list and know what to do. On 2026-09-24 the owner replaced the finished
unified-fusion queue with their debug & repair brief, so two things can now go
wrong quietly:

* ``AGENTS.md`` keeps pointing at a finished queue instead of the live one, and a
  session re-does completed work;
* the queue's §1 ("next ⬜ piece") drifts from its §3 table, or a piece is dropped.

These checks are offline: they parse the Markdown the repo actually renders.
"""

import re

from conftest import ROOT

AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
QUEUE = (ROOT / "docs/DEBUG_QUEUE.md").read_text(encoding="utf-8")
BRIEF = (ROOT / "docs/DEBUG_SPEC.md").read_text(encoding="utf-8")
FUSION = (ROOT / "docs/FUSION_STATUS.md").read_text(encoding="utf-8")

#: Every brief section the queue must map to a piece (the owner's 12 sections).
BRIEF_SECTIONS = range(1, 13)


def section(text: str, heading: str) -> str:
    """The body of one Markdown heading, up to the next heading of any level."""
    body = text.split(f"{heading}\n", 1)
    assert len(body) == 2, f"heading not found: {heading!r}"
    return body[1].split("\n## ", 1)[0]


def piece_table(text: str) -> list[dict[str, str]]:
    """Rows of the queue's §3 piece table, keyed by their header cells."""
    table = section(text, "## 3. Ordered piece list")
    rows = [line for line in table.splitlines() if line.startswith("|")]
    header = [cell.strip() for cell in rows[0].strip("|").split("|")]
    out = []
    for line in rows[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        if not re.fullmatch(r"\**D\d+[a-z]?\**", cells[0]):
            continue
        out.append({k: v for k, v in zip(header, cells)})
    return out


def test_agents_standing_instruction_names_the_live_debug_queue():
    instruction = section(AGENTS, '## Standing instruction: when the user says "Proceed ❤️"')
    assert "docs/DEBUG_QUEUE.md" in instruction, (
        "the 'Proceed ❤️' instruction must name the live queue a new session follows"
    )
    assert "docs/DEBUG_SPEC.md" in instruction, (
        "the instruction must name the owner's binding brief behind that queue"
    )
    assert "docs/FUSION_STATUS.md" in instruction, (
        "the finished fusion queue stays reachable as the history/invariants record"
    )


def test_the_finished_fusion_queue_is_recorded_as_frozen_and_points_forward():
    head = FUSION[:4000]
    assert "COMPLETE AND FROZEN" in head, "FUSION_STATUS.md must say it is no longer live"
    assert "docs/DEBUG_QUEUE.md" in head, "and must point at the live queue that replaced it"
    assert "✅" in section(FUSION, "## 3. Ordered piece list"), (
        "the frozen record still shows the completed piece rows"
    )


def test_the_live_queue_lists_the_debug_pieces_in_order():
    rows = piece_table(QUEUE)
    ids = [row["#"].strip("*") for row in rows]
    assert ids == ["D0", "D1a", "D1b", "D2", "D3", "D4", "D5", "D6"], (
        "the queue's piece order is the contract a session follows: " + repr(ids)
    )
    for row in rows:
        assert row["Status"].strip("*") in {"✅", "⬜", "🚧"}, row["Status"]
        assert re.search(r"§\d+", row["brief §"]), f"piece {row['#']} must cite its brief section"
        assert "`" in row["Primary files (inspect → change)"], (
            f"piece {row['#']} must name the files it touches"
        )
        assert row["Evidence (PR / test)"], f"piece {row['#']} must record evidence once done"
    assert any(row["Status"].strip("*") == "⬜" for row in rows), (
        "an unfinished queue has at least one pending piece; if the debug plan is ever "
        "finished, record that in the queue and update this test in the same commit"
    )


def test_the_queue_and_the_brief_cover_every_brief_section():
    for number in BRIEF_SECTIONS:
        assert f"\n## {number}. " in BRIEF, f"the brief lost its section {number}"
        assert re.search(rf"\| {number} \|", QUEUE), (
            f"brief §{number} is not mapped to a piece anywhere in the queue"
        )
    assert "TEST F" in BRIEF and "TEST F" in QUEUE, (
        "the repeated-transition check (brief §11) must survive in the brief and the queue"
    )


def test_the_queue_says_a_piece_merges_only_when_complete():
    rules = section(QUEUE, "## 2. Non-negotiable rules (do not re-litigate, do not weaken)")
    assert "One piece/section per PR, merged only when complete" in rules, (
        "the owner's merge rule must be a stated rule, not folklore"
    )
    assert "never merge a partial one" in AGENTS, (
        "AGENTS.md must repeat the merge-only-when-complete rule for a fresh session"
    )


def test_next_pending_piece_in_the_progress_table_matches_the_piece_list():
    progress = section(QUEUE, "## 1. Where completed work lives (read this first)")
    cell = next(line for line in progress.splitlines() if line.startswith("| next ⬜ piece |"))
    declared = re.search(r"\*\*(D\d+[a-z]?)\*\*", cell)
    pending = [row["#"].strip("*") for row in piece_table(QUEUE) if row["Status"].strip("*") != "✅"]
    if pending:
        assert declared and declared.group(1) == pending[0], (
            f"§1 says {declared and declared.group(1)!r} but the first pending piece is {pending[0]!r}"
        )
    else:
        assert "none" in cell.lower(), "with nothing pending, §1 must say so"


def test_the_readme_points_a_reader_at_the_live_queue_not_only_the_finished_one():
    assert "docs/DEBUG_QUEUE.md" in README and "docs/DEBUG_SPEC.md" in README, (
        "the repo page must tell readers where the live work is recorded"
    )
