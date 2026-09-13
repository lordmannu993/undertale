"""Reader for GameMaker Studio 2's JSON dialect.

Yellow's ``.yy``/``.yyp`` files are JSON with two differences that break
``json.loads``: every object and array ends with a trailing comma, and the
format tolerates ``//`` comments. Both edits have to be made *outside* string
literals — a naive regex would happily rewrite dialogue or sample text that
contains ``, }`` — so the string spans are located first and the edits are
applied only in the gaps between them.

Anything else unexpected raises ``GMS2Error`` naming the file: this port stops
visibly rather than guessing what malformed input meant.
"""
from __future__ import annotations

import bisect
import json
from pathlib import Path
import re

STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"')
TRAILING_COMMA = re.compile(r",(?=\s*[}\]])")
LINE_COMMENT = re.compile(r"//[^\n]*")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)


class GMS2Error(RuntimeError):
    """A Yellow project file could not be read as documented."""


def _spans(text: str) -> tuple[list[int], list[int]]:
    """Start/end offsets of every string literal, for bisect lookups."""
    starts, ends = [], []
    for match in STRING.finditer(text):
        starts.append(match.start())
        ends.append(match.end())
    return starts, ends


def _inside(starts: list[int], ends: list[int], position: int) -> bool:
    index = bisect.bisect_right(starts, position) - 1
    return index >= 0 and position < ends[index]


def _remove(text: str, patterns: tuple[re.Pattern[str], ...]) -> str:
    """Apply every match of ``patterns`` that is not inside a string literal."""
    starts, ends = _spans(text)
    edits = [(m.start(), m.end()) for pattern in patterns for m in pattern.finditer(text)
             if not _inside(starts, ends, m.start())]
    if not edits:
        return text
    edits.sort()
    out, cursor = [], 0
    for start, end in edits:
        if start < cursor:  # overlapping match, already removed
            continue
        out.append(text[cursor:start])
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def json_text(text: str) -> str:
    """Strip comments first, then the trailing commas they may have been hiding.

    Order matters: ``{"a": 1, // note`` only has a *trailing* comma once the
    comment is gone, and both edits have to skip string literals, because Yellow's
    own font records carry sample text such as ``"abc, }"``.
    """
    return _remove(_remove(text, (LINE_COMMENT, BLOCK_COMMENT)), (TRAILING_COMMA,))


def loads(text: str, origin: str = "<text>"):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(json_text(text))
    except json.JSONDecodeError as exc:
        raise GMS2Error(f"{origin}: not readable GMS2 JSON ({exc})") from exc


def read(path: Path):
    """Read one ``.yy``/``.yyp``/``.room.yy`` record."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        raise GMS2Error(f"{path}: {exc}") from exc
    return loads(text, str(path))


def ref_name(value) -> str | None:
    """GMS2 references are ``{"name": ..., "path": ...}`` objects, or null."""
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    return name if isinstance(name, str) and name else None


def png_size(path: Path) -> tuple[int, int]:
    """Width and height from a PNG IHDR, without an imaging dependency."""
    with path.open("rb") as handle:
        header = handle.read(33)
    if len(header) < 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise GMS2Error(f"{path}: not a PNG with an IHDR chunk")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    if width <= 0 or height <= 0:
        raise GMS2Error(f"{path}: PNG reports a {width}x{height} image")
    return width, height
