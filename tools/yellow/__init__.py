"""Undertale Yellow merge helpers.

The Yellow decompilation is a GameMaker Studio 2 project; this port converts a
GameMaker 1.4 ``.gmx`` checkout. This package is the Studio 2 front end: it reads
the pinned source, recovers Yellow's own numeric asset IDs from two independent
records inside that source, and emits assets in the record shape the existing
LÖVE runtime already consumes.

See ``docs/YELLOW.md`` for the five-piece plan and the deviations each piece
records instead of hiding.
"""
from __future__ import annotations

from .gms2 import GMS2Error  # noqa: F401 - re-exported for callers
from .registry import YELLOW_BASE, Registry  # noqa: F401

__all__ = ["GMS2Error", "Registry", "YELLOW_BASE"]
