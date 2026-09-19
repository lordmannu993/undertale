#!/usr/bin/env python3
"""Alpha bounding box of a PNG, using only the standard library.

``tools/recover_sprite_offsets.py`` has to compare this checkout's exported
sprite images against the original canvases the events draw into, and the CI
image only installs lupa and pytest, so there is no imaging library to lean on.
The decoder below handles the forms the Undertale export actually contains
(8-bit greyscale, greyscale+alpha, RGB and RGBA, stored/ZIP deflate, all five
PNG filter types) and raises on anything else instead of guessing.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


class PngError(Exception):
    """The file is not a PNG form this decoder certifies."""


def _chunks(blob: bytes):
    offset = 8
    while offset < len(blob):
        length = int.from_bytes(blob[offset:offset + 4], "big")
        kind = blob[offset + 4:offset + 8]
        data = blob[offset + 8:offset + 8 + length]
        if len(data) != length:
            raise PngError("truncated chunk")
        yield kind, data
        offset += 12 + length


def _unfilter(raw: bytes, width: int, height: int, bpp: int) -> list[bytes]:
    stride = width * bpp
    if len(raw) != (stride + 1) * height:
        raise PngError(f"image data is {len(raw)} bytes, expected {(stride + 1) * height}")
    rows: list[bytearray] = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        kind = raw[offset]
        line = bytearray(raw[offset + 1:offset + 1 + stride])
        offset += stride + 1
        if kind == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif kind == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif kind == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif kind == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up = previous[i]
                upleft = previous[i - bpp] if i >= bpp else 0
                estimate = left + up - upleft
                pa, pb, pc = abs(estimate - left), abs(estimate - up), abs(estimate - upleft)
                nearest = left if (pa <= pb and pa <= pc) else (up if pb <= pc else upleft)
                line[i] = (line[i] + nearest) & 0xFF
        elif kind != 0:
            raise PngError(f"unknown PNG filter type {kind}")
        rows.append(line)
        previous = line
    return [bytes(row) for row in rows]


def load_alpha(path: Path) -> tuple[int, int, list[bytes]]:
    """Return width, height and one alpha byte per pixel, row major."""
    blob = Path(path).read_bytes()
    if blob[:8] != PNG_SIGNATURE:
        raise PngError(f"{path}: not a PNG")
    width = height = None
    depth = None
    channels = None
    interlaced = 0
    palette: list[tuple[int, int, int, int]] = []
    transparency = None
    data = b""
    for kind, chunk in _chunks(blob):
        if kind == b"IHDR":
            width, height, depth, colour, _, _, interlaced = struct.unpack(">IIBBBBB", chunk)
            if interlaced:
                raise PngError(f"{path}: interlaced PNGs are not decoded")
            if depth != 8:
                raise PngError(f"{path}: {depth}-bit PNGs are not decoded")
            if colour == 3:
                channels = 1
            elif colour in CHANNELS:
                channels = CHANNELS[colour]
            else:
                raise PngError(f"{path}: colour type {colour} is not decoded")
            colour_type = colour
        elif kind == b"PLTE":
            palette = [tuple(chunk[i:i + 3]) + (255,) for i in range(0, len(chunk), 3)]
        elif kind == b"tRNS":
            transparency = chunk
        elif kind == b"IDAT":
            data += chunk
        elif kind == b"IEND":
            break
    if width is None or height is None:
        raise PngError(f"{path}: missing IHDR")
    if transparency is not None:
        if colour_type == 3:
            for index, alpha in enumerate(transparency):
                if index < len(palette):
                    palette[index] = palette[index][:3] + (alpha,)
        else:
            raise PngError(f"{path}: tRNS on colour type {colour_type} is not decoded (RGBA export expected)")
    if colour_type == 3 and not palette:
        raise PngError(f"{path}: indexed PNG without a palette")
    rows = _unfilter(zlib.decompress(data), width, height, channels)
    alpha: list[bytes] = []
    for row in rows:
        if colour_type == 6:
            alpha.append(row[3::4])
        elif colour_type == 4:
            alpha.append(row[1::2])
        elif colour_type == 0:
            alpha.append(bytes([255]) * width)
        elif colour_type == 2:
            alpha.append(bytes([255]) * width)
        elif colour_type == 3:
            alpha.append(bytes(palette[value][3] for value in row))
    return width, height, alpha


def alpha_bbox(path: Path, threshold: int = 1) -> tuple[int, int, int, int] | None:
    """Inclusive (left, top, right, bottom) of pixels with alpha >= threshold."""
    width, height, alpha = load_alpha(path)
    left, top, right, bottom = width, height, -1, -1
    for y, row in enumerate(alpha):
        if max(row, default=0) < threshold:
            continue
        top = min(top, y)
        bottom = max(bottom, y)
        for x, value in enumerate(row):
            if value >= threshold:
                left = min(left, x)
                right = max(right, x)
    if bottom < 0 or right < 0:
        return None
    return left, top, right, bottom


def png_size(path: Path) -> tuple[int, int]:
    """Width and height from the IHDR alone (cheap size check)."""
    header = Path(path).read_bytes()[:33]
    if len(header) < 33 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise PngError(f"{path}: not a PNG with an IHDR chunk")
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
