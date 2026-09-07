"""Audited repairs for this specific damaged GMX export, not general GML rules.

The decompiler paired descending switch labels with ascending branch bodies.
Independent anchors: item 1=Candy, 3=Stick, phone 201=Hello, MSC 200=Flowey,
MSC 666=SOUL, and old damage/Sans/Papyrus font callers. Keep branch bodies and
fall-through untouched. Hash guards refuse to rewrite a different source export.

The export also negated obj_dialoguer's obj_face cleanup guards in two events.
The shipped game (checked against the verified data.win decompilation) destroys
the dialogue face portraits when the dialoguer ends. With the guard negated the
faces leak: Flowey's face survives into and out of the tutorial battle, stacks
on top of Toriel's face afterwards, and the leftover Toriel face then blocks
obj_floweytrigger's `!instance_exists(obj_torface)` check forever (softlock).
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


# obj_dialoguer events whose obj_face cleanup guard the export negated.
DIALOGUER_FACE_CLEANUP = {
    # Destroy: shipped game runs `if (instance_exists(obj_face) == 1) with (obj_face) instance_destroy()`.
    "1:0": "8b7b4f3b91494833adc79c4beb78c3001d42f01b2707f9fe5f884ea6cf020e11",
    # Step, facechoice == 0 branch: shipped game runs the same guarded cleanup.
    "3:0": "19b1c7e31952cce4f6f6de61515dc1e1d10b2d0b08b9bd6b5e2a86fa2d3526ad",
}
FACE_CLEANUP_BROKEN = re.compile(
    r"if\(!instance_exists\(774/\* obj_face \*/\)\)"
    r"(\s*\{\s*\n\s*// obj_face\n\s*with\(774\) instance_destroy\(\);\s*\n\s*\})"
)


def repair_object_event(name, event_key, source, report):
    if name == "obj_dialoguer" and event_key in DIALOGUER_FACE_CLEANUP:
        digest = DIALOGUER_FACE_CLEANUP[event_key]
        normalized = source.replace("\r\n", "\n")
        if hashlib.sha256(normalized.encode()).hexdigest() != digest:
            raise CompileError(f"obj_dialoguer event {event_key}: source changed; review the face-cleanup repair instead of applying it blindly")
        repaired, count = FACE_CLEANUP_BROKEN.subn(r"if(instance_exists(774/* obj_face */))\1", normalized)
        if count != 1:
            raise CompileError(f"obj_dialoguer event {event_key}: expected exactly one negated obj_face cleanup guard, found {count}")
        report['repairs'].append(
            f"obj_dialoguer event {event_key}: restored the negated obj_face cleanup guard so dialogue faces are destroyed "
            f"when the dialoguer ends, matching the shipped game (source SHA-256 {digest})."
        )
        return repaired
    return source
