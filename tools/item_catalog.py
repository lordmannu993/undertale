#!/usr/bin/env python3
"""Extract the shared item catalog from both games' own item scripts (piece 5b).

One inventory needs one catalog.  Every name, kind, heal amount, equip stat and
use message in the generated catalog is parsed out of this checkout's own
Undertale GML and the pinned Yellow source -- nothing is hand-typed and nothing
is invented.  Where the damaged Undertale export reversed its switch labels,
this tool reuses the *same* audited repair as the converter
(``tools/source_repairs.repair_script``), so the numeric IDs here are exactly
the IDs the runtime executes.

Sources (per item):

  Undertale (``scripts/``)
    scr_itemnamelist   display name                 (switch labels repaired)
    scr_itemnameb      8-char menu name + serious   (switch labels repaired)
    scr_itemvalue      shop value                   (switch labels repaired)
    scr_itemuseb       kind / heal / first message  (switch labels repaired)
    scr_weaponeq       weapon attack, armour weapon bonus
    scr_armoreq        armour defense
  Yellow (``yellow_src/scripts/``)
    scr_item_use       kind / heal / first message (string switch, undamaged)
    scr_item_stats_weapon / _armor / _weapon_mod / _armor_mod / _heal

Items that exist in both games under the *same source name* (exact string
match) are paired; the inventory adapters project one token to the other
game's spelling through that pairing.  No pairing is ever guessed.

Usage::

    python3 tools/item_catalog.py                  # write generated/merged/items.lua
    python3 tools/item_catalog.py --check          # verify without writing
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_repairs import repair_script  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
UT = ROOT / "scripts"
YELLOW = ROOT / "yellow_src" / "scripts"

CASE = re.compile(r"^(\s*case )(-?\d+|\"[^\"]+\")(:)", re.M)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _repaired(name: str) -> str:
    """The label-restored source the runtime actually compiles."""
    return repair_script(name, _read(UT / f"{name}.gml"), {"repairs": []})


def _case_blocks(source: str, numeric: bool = True):
    """Yield (label:int|str, body) in file order for a switch statement."""
    matches = list(CASE.finditer(source))
    for index, match in enumerate(matches):
        label = match.group(2)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        body = source[match.end():end]
        yield (int(label) if numeric else label.strip('"')), body


def _assignments(body: str, pattern: str):
    return re.findall(pattern, body)


def _runs(blocks, marker):
    """Group GMS2 fall-through labels with the body they share.

    ``case "A": case "B": <body>`` records one body under two labels; the body
    textually attaches to B.  Both labels name the same item behaviour, so both
    get the same record -- derived from that body, never invented.
    """
    pending, out = [], []
    for label, body in blocks:
        pending.append(label)
        if re.search(marker, body):
            out.append((list(pending), body))
            pending = []
    return out


# ---------------------------------------------------------------------------
# Undertale extraction
# ---------------------------------------------------------------------------

def ut_names() -> dict:
    out = {}
    for item_id, body in _case_blocks(_repaired("scr_itemnamelist")):
        found = re.search(r'global\.itemname\[i\]=\s*"([^"]*)"', body)
        if found:
            out[item_id] = found.group(1).replace("\\\\", "\\").replace("\\'", "'")
    return out


def ut_short_names() -> dict:
    out = {}
    for item_id, body in _case_blocks(_repaired("scr_itemnameb")):
        names = re.findall(r'global\.itemnameb\[i\]=\s*"([^"]*)"', body)
        if names:
            out[item_id] = {"short": names[0]}
            if len(names) > 1:
                out[item_id]["short_serious"] = names[-1]
    return out


def ut_values() -> dict:
    out = {}
    for item_id, body in _case_blocks(_repaired("scr_itemvalue")):
        found = re.search(r"value\[i\]=\s*(-?\d+)", body)
        if found:
            out[item_id] = int(found.group(1))
    return out


def ut_use() -> dict:
    out = {}
    for item_id, body in _case_blocks(_repaired("scr_itemuseb")):
        if item_id > 64:
            continue  # 201-221 are phone entries (scr_phonename), not items
        record = {}
        messages = {}
        for slot, text in re.findall(r'global\.msg\[(\d+)\]=\s*"((?:[^"\\]|\\.)*)"', body):
            messages.setdefault(int(slot), text.replace("\\\\", "\\").replace("\\'", "'"))
        if messages:
            record["messages"] = [messages[i] for i in sorted(messages)]
            record["message"] = record["messages"][0]
        heal = re.search(r"scr_recoitem \*/,\s*(\d+)\)", body)
        if heal:
            record["heal"] = int(heal.group(1))
        if re.search(r"global\.hp=\s*global\.maxhp", body):
            record["heal"] = "max"
        if re.search(r"scr_weaponeq\(argument0, argument1\)", body):
            record["kind"] = "weapon"
        elif re.search(r"scr_armoreq\(argument0, argument1\)", body):
            record["kind"] = "armor"
        elif "heal" in record:
            record["kind"] = "consume"
        elif re.search(r"scr_itemshift\(\s*argument0", body):
            record["kind"] = "consume"
        else:
            record["kind"] = "key"
        out[item_id] = record
    return out


def ut_equipment() -> tuple:
    """(weapon_strength, armor_defense, armor_weapon_bonus) from the equip ifs."""
    weapon, armor, bonus = {}, {}, {}
    for item_id, value in _assignments(_read(UT / "scr_weaponeq.gml"),
                                      r"global\.weapon == (\d+)\)\s*global\.wstrength=\s*(\d+)"):
        weapon[int(item_id)] = int(value)
    for item_id, value in _assignments(_read(UT / "scr_weaponeq.gml"),
                                      r"global\.armor == (\d+)\)\s*global\.wstrength\+=\s*(\d+)"):
        bonus[int(item_id)] = int(value)
    source = _read(UT / "scr_armoreq.gml")
    for item_id, value in _assignments(source,
                                       r"global\.armor == (\d+)\)\s*global\.adef=\s*(\d+)"):
        armor[int(item_id)] = int(value)
    for item_id, value in _assignments(source,
                                       r"global\.armor == (\d+)\)\s*\{\s*\n\s*global\.adef=\s*(\d+)"):
        armor[int(item_id)] = int(value)
    return weapon, armor, bonus


def undertale_catalog() -> dict:
    names, shorts, values, uses = ut_names(), ut_short_names(), ut_values(), ut_use()
    weapons, armors, bonuses = ut_equipment()
    items = {}
    for item_id in sorted(names):
        if item_id == 0:
            continue  # the empty-slot sentinel has no catalog entry
        entry = dict(uses.get(item_id, {"kind": "key", "heal": 0}))
        if item_id in names:
            entry["name"] = names[item_id]
        if item_id in shorts:
            entry.update(shorts[item_id])
        if item_id in values:
            entry["value"] = values[item_id]
        if item_id in weapons:
            entry["kind"] = "weapon"
            entry["weapon_strength"] = weapons[item_id]
        if item_id in armors:
            entry["kind"] = "armor"
            entry["armor_defense"] = armors[item_id]
        if item_id in bonuses:
            entry["armor_weapon_bonus"] = bonuses[item_id]
        entry.setdefault("heal", 0)
        items[item_id] = entry
    return items


# ---------------------------------------------------------------------------
# Yellow extraction
# ---------------------------------------------------------------------------

def yellow_script(name: str) -> str:
    return _read(YELLOW / name / f"{name}.gml")


def yellow_use() -> dict:
    out = {}
    source = yellow_script("scr_item_use")
    # GMS2 switch over string item names; labels are undamaged.
    for labels, body in _runs(_case_blocks(source, numeric=False), r"item_type\s*="):
        record = {}
        messages = {}
        for slot, text in re.findall(r'use_msg\[(\d+)\]\s*=\s*"((?:[^"\\]|\\.)*)"', body):
            messages.setdefault(int(slot), text.replace('\\"', '"'))
        if messages:
            record["messages"] = [messages[i] for i in sorted(messages)]
            record["message"] = record["messages"][0]
        heal = re.search(r"heal_value\s*=\s*(\d+)", body)
        if heal:
            record["heal"] = int(heal.group(1))
        if re.search(r"heal_value\s*=\s*clamp\(global\.max_hp_self", body):
            record["heal"] = "max"
        for field, key in (("pp_value", "pp"), ("sp_value", "sp"), ("rp_value", "rp")):
            found = re.search(rf"{field}\s*=\s*(\d+)", body)
            if found and int(found.group(1)):
                record[key] = int(found.group(1))
        atk = re.search(r"atk_value\s*=\s*(\d+)", body)
        if atk:
            record["atk"] = int(atk.group(1))
        deff = re.search(r"def_value\s*=\s*(\d+)", body)
        if deff:
            record["def"] = int(deff.group(1))
        kind = re.search(r"item_type\s*=\s*(\d)", body)
        kind_map = {"1": "consume", "2": "ammo", "3": "accessory", "4": "weapon", "0": "key"}
        record["kind"] = kind_map.get(kind.group(1) if kind else "", "key")
        record["use"] = True
        for name in labels:
            out.setdefault(name, dict(record))
    return out


def yellow_stats(script: str) -> dict:
    out = {}
    for labels, body in _runs(_case_blocks(yellow_script(script), numeric=False), r"\breturn\b"):
        found = re.search(r"return (-?\d+)", body)
        if found:
            for name in labels:
                out.setdefault(name, int(found.group(1)))
    return out


def yellow_catalog() -> dict:
    items = yellow_use()
    tables = {
        "weapon_strength": yellow_stats("scr_item_stats_weapon"),
        "armor_defense": yellow_stats("scr_item_stats_armor"),
        "weapon_mod_strength": yellow_stats("scr_item_stats_weapon_mod"),
        "armor_mod_defense": yellow_stats("scr_item_stats_armor_mod"),
        "heal": yellow_stats("scr_item_stats_heal"),
    }
    for field, table in tables.items():
        for name, value in table.items():
            entry = items.setdefault(name, {"kind": "key", "heal": 0})
            entry[field] = value
            if field == "weapon_strength":
                entry["kind"] = "weapon"
            elif field == "armor_defense":
                entry["kind"] = "armor"
            elif field == "weapon_mod_strength":
                entry.setdefault("atk", value)
                if entry["kind"] == "key":
                    entry["kind"] = "ammo"
            elif field == "armor_mod_defense":
                entry.setdefault("def", value)
                if entry["kind"] == "key":
                    entry["kind"] = "accessory"
            elif field == "heal" and entry.get("heal", 0) == 0 and value > 0:
                entry["heal"] = value
    return items


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build() -> dict:
    ut = undertale_catalog()
    yellow = yellow_catalog()
    pairs = {}
    for item_id, entry in ut.items():
        name = entry.get("name")
        if name and name in yellow:
            pairs[item_id] = name
    return {
        "ut": ut,
        "yellow": yellow,
        "pairs": pairs,
        "provenance": {
            "undertale": "this checkout's scripts/ (switch labels via tools/source_repairs.py)",
            "yellow": "pinned Yellow source fetched by tools/fetch_yellow.py",
        },
    }


def to_lua(data: dict) -> str:
    def lua(value):
        if value is None:
            return "nil"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, (list, tuple)):
            return "{" + ",".join(lua(v) for v in value) + "}"
        if isinstance(value, dict):
            parts = []
            for key in sorted(value, key=lambda k: str(k)):
                k = f"[{lua(key)}]" if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(key)) else key
                parts.append(f"{k}={lua(value[key])}")
            return "{" + ",".join(parts) + "}"
        raise TypeError(value)

    return (
        "-- Generated by tools/item_catalog.py from both games' own item scripts.\n"
        "-- Every value is parsed from source; nothing here is hand-typed.\n"
        f"return {lua(data)}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "generated" / "merged" / "items.lua")
    parser.add_argument("--check", action="store_true",
                        help="verify the checked-in output matches the sources")
    args = parser.parse_args()

    data = build()
    if not data["ut"] or not data["yellow"]:
        print("item catalog: one of the source games produced no items", file=sys.stderr)
        return 1
    text = to_lua(data)
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != text:
            print(f"item catalog: {args.output} is out of date; re-run tools/item_catalog.py",
                  file=sys.stderr)
            return 1
        print(f"item catalog: {args.output.relative_to(ROOT)} matches both sources "
              f"({len(data['ut'])} Undertale + {len(data['yellow'])} Yellow items, "
              f"{len(data['pairs'])} paired)")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(f"item catalog: {args.output.relative_to(ROOT)} "
          f"({len(data['ut'])} Undertale items, {len(data['yellow'])} Yellow items, "
          f"{len(data['pairs'])} paired by shared name)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
