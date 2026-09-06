"""Audited repairs for this specific damaged GMX export, not general GML rules.

The decompiler paired descending switch labels with ascending branch bodies.
Independent anchors: item 1=Candy, 3=Stick, phone 201=Hello, MSC 200=Flowey,
MSC 666=SOUL, and old damage/Sans/Papyrus font callers. Keep branch bodies and
fall-through untouched. Hash guards refuse to rewrite a different source export.
"""
import hashlib
import re
try:
    from .gml import CompileError
except ImportError:  # invoked by tools/convert.py as a script
    from gml import CompileError

SWITCHES = {
    "SCR_TEXT": ("c8cb10f041e0b8a1d0d227ea9c59f73dd84a7a79604e11152a45e990d9ae0b15", 473, True),
    "scr_itemnamelist": ("fcd0681f1ba97c8ed1540b6cc720d320eea5f08ac447bb4849f70d88418990b6", 65, False),
    "scr_itemdesc": ("64f8bb73d998e2d5f627f34350490a076e73df3d43f78bbe8f779fb99d1d5787", 65, False),
    "scr_itemnameb": ("95f8b8a3605e09e50f3206c2b214f99f2fa9b4b7c7f48d283764e925e442b3e9", 64, False),
    "scr_itemvalue": ("18375eb7cc846eb86483856591073903faddb07df2629f11628aeddb16b9f5bc", 64, False),
    "scr_itemuseb": ("25f44f496c0c3d43b1b01a576a5b09289945146553952b802620995f03bbd20a", 74, False),
    "scr_phonename": ("d09887d0468504287192355aa1d059be1933ca6b6f1caea0a24fb91ee8d2b2c2", 9, False),
    "scr_battlegroup": ("b6bed0f4adf3c34dc00b75e8d3d42d5f1f4c53980b0b06c76ec8507e319b213c", 112, False),
    "scr_papcall": ("42462ead9c251b4c69453d1172cbd72bb2d466e1707bd595ceebd60eddcdafd9", 121, False),
}
CASE = re.compile(r"^(\s*case )(-?\d+)(:)", re.M)


def repair_script(name, source, report):
    if name in SWITCHES:
        digest, count, zero_last = SWITCHES[name]
        normalized = source.replace("\r\n", "\n")
        if hashlib.sha256(normalized.encode()).hexdigest() != digest:
            raise CompileError(f"{name}: source changed; review the switch-label repair instead of applying it blindly")
        labels = [int(m[2]) for m in CASE.finditer(source)]
        if len(labels) != count or len(set(labels)) != count:
            raise CompileError(f"{name}: unexpected switch structure")
        restored = sorted(labels)
        if zero_last:
            assert labels[-1] == 0 and restored[0] == 0
            restored = restored[1:] + [0]  # optional testlines.txt branch stays last
        values = iter(restored)
        source = CASE.sub(lambda m: m[1] + str(next(values)) + m[3], source)
        report['repairs'].append(f"{name}: restored {count} decompiler-reversed switch labels; branch bodies/fall-through unchanged (source SHA-256 {digest}).")
    if name in ("SCR_TEXTTYPE", "SCR_TEXTTYPE_f"):
        # A decimal comma in the shake argument became TWO arguments, shifting
        # speed, voice and line spacing. SCR_TEXTSETUP takes exactly ten args.
        source, count = re.subn(r", 1,([245]),", r", 1.\1,", source)
        if count:
            report['repairs'].append(f"{name}: repaired {count} decimal-comma shake arguments; retained ten-argument text setup.")
    return source
