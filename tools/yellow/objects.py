"""Yellow's objects: metadata, parents, masks, collision targets and every event.

A GameMaker Studio 2 object is a ``.yy`` record plus one ``.gml`` file per event
in the same folder. This module turns each of Yellow's 3 224 objects into the
same module shape ``tools/convert.py`` writes for Undertale — a metadata table
plus ``object.events["kind:number"]`` — so ``port/runtime.lua`` loads either game
without knowing which one it is looking at.

Four Studio 2 facts have no GameMaker 1.4 equivalent, and each is recorded
rather than quietly reinterpreted:

* **No object depth.** Studio 2 removed the per-object depth; an instance takes
  the depth of the room layer it sits on. Objects are therefore converted with
  ``depth = 0`` and ``yellow.depth_source`` says where the real value comes from;
  piece 4 (rooms) assigns it. Inventing a depth per object would be a guess.
* **Physics objects.** Ten Yellow objects are Box2D fixtures (the seesaw and
  piston puzzles). The runtime has no physics, so the whole physics record is
  kept in ``yellow.physics`` and ``Runtime:create`` stops with the object's name
  instead of dropping the instance into a world that will not move it.
* **Object variables** (``properties``) would have to become Create-event
  prologue code. Yellow declares none, so an encounter is a hard error rather
  than a silent omission.
* **Events the runtime does not deliver.** Every event is converted — none is
  dropped — and the report names the subtypes nothing dispatches (Yellow's Async
  HTTP poll and its sprite-frame Broadcast Messages), so an object that only
  reacts to one of them is visibly inert instead of mysteriously so.

Event numbers are GameMaker's own and identical in both engines, so a converted
Yellow event keeps its Studio 2 numbers; only collision events are renumbered,
from the target's *name* to its merged ``YELLOW_BASE`` ID, exactly as
``tools/convert.py`` renumbers Undertale's ``ename`` targets.
"""
from __future__ import annotations

from pathlib import Path

try:  # imported as ``tools.yellow.objects`` from the repository root
    from ..convert import lua
    from ..gml import quote
    from ..gml2 import CompileError, compile_gml2_event, function_expression
except ImportError:  # loaded through ``tools/`` on sys.path, as the converter does
    from convert import lua
    from gml import quote
    from gml2 import CompileError, compile_gml2_event, function_expression

from .gms2 import GMS2Error, read, ref_name
from .registry import YELLOW_BASE, Registry

#: Studio 2 event type -> the folder name its code file uses. GameMaker 1.4
#: numbers its events the same way, so these are also the runtime's event kinds.
EVENT_NAMES = {0: "Create", 1: "Destroy", 2: "Alarm", 3: "Step", 4: "Collision",
               5: "Keyboard", 6: "Mouse", 7: "Other", 8: "Draw", 9: "KeyPress",
               10: "KeyRelease", 11: "Trigger", 12: "CleanUp", 13: "Gesture", 14: "PreCreate"}

#: Subtype names used in the conversion report. These are GameMaker's own event
#: subtype numbers (the same table in 1.4 and Studio 2); none is invented here.
STEP_SUBTYPES = {0: "Step", 1: "Begin Step", 2: "End Step"}
OTHER_SUBTYPES = {0: "Outside Room", 1: "Intersect Boundary", 2: "Game Start", 3: "Game End",
                  4: "Room Start", 5: "Room End", 6: "No More Lives", 7: "Animation End",
                  8: "End of Path", 9: "No More Health", 30: "Close Button",
                  58: "Animation Update", 59: "Animation Event",
                  60: "Async - Image Loaded", 61: "Async - Sound Loaded", 62: "Async - HTTP",
                  63: "Async - Dialog", 66: "Async - In-App Purchase", 67: "Async - Cloud",
                  68: "Async - Networking", 69: "Async - Steam", 70: "Async - Social",
                  71: "Async - Push Notification", 72: "Async - Save/Load",
                  73: "Async - Audio Recording", 74: "Async - Audio Playback",
                  75: "Async - System", 76: "Broadcast Message"}
DRAW_SUBTYPES = {0: "Draw", 64: "Draw GUI", 65: "Resize", 72: "Draw Begin", 73: "Draw End",
                 74: "Draw GUI Begin", 75: "Draw GUI End", 76: "Pre Draw", 77: "Post Draw"}
MOUSE_SUBTYPES = {0: "Left Button", 1: "Right Button", 2: "Middle Button", 3: "No Button",
                  4: "Left Pressed", 5: "Right Pressed", 6: "Middle Pressed",
                  7: "Left Released", 8: "Right Released", 9: "Middle Released",
                  10: "Mouse Enter", 11: "Mouse Leave", 50: "Global Left Button",
                  51: "Global Right Button", 52: "Global Middle Button", 53: "Global Left Pressed",
                  54: "Global Right Pressed", 55: "Global Middle Pressed", 56: "Global Left Released",
                  57: "Global Right Released", 58: "Global Middle Released",
                  60: "Mouse Wheel Up", 61: "Mouse Wheel Down"}
SUBTYPE_NAMES = {3: STEP_SUBTYPES, 6: MOUSE_SUBTYPES, 7: OTHER_SUBTYPES, 8: DRAW_SUBTYPES}

#: Event subtypes ``port/runtime.lua`` and ``port/graphics.lua`` deliver.
#: ``None`` means "any subtype": the key-driven events are dispatched from
#: ``manifest.keys``, whatever key codes the converted objects use.
DELIVERED = {
    0: {0},                       # Create
    1: {0},                       # Destroy
    2: set(range(12)),            # Alarm 0-11
    3: {0, 1, 2},                 # Step / Begin Step / End Step
    4: None,                      # Collision, keyed by the target's merged ID
    5: None, 9: None, 10: None,   # Key Down / Pressed / Released
    # No Button (3), Mouse Enter (10) and Mouse Leave (11) have no dispatch.
    6: {0, 1, 2, 4, 5, 6, 7, 8, 9} | set(range(50, 59)),
    7: {0, 1, 2, 4, 5, 7} | set(range(10, 26)),
    8: {0, 64, 72, 73, 74, 75, 76, 77},
    12: {0},                      # Clean Up
}
#: Why an undelivered event is undelivered, where this port knows a reason.
NOT_DELIVERED = {
    (6, 3): "No Button: fires every step while no button is held; no Yellow object uses it",
    (6, 10): "Mouse Enter: a pointer edge event; no Yellow object uses it",
    (6, 11): "Mouse Leave: a pointer edge event; no Yellow object uses it",
    (7, 62): "Async HTTP: the runtime has no networking, and Yellow's only user is GMLive's own poll",
    (7, 76): "Broadcast Message: sprite frame events are not converted, so nothing broadcasts",
    (8, 65): "Resize: the LÖVE layer owns the window; the runtime draws into a canvas",
}
FALLBACK_REASON = "this Studio 2 event subtype has no dispatch in port/runtime.lua or port/graphics.lua"

PHYSICS_FIELDS = {"physicsSensor": "sensor", "physicsShape": "shape", "physicsDensity": "density",
                  "physicsRestitution": "restitution", "physicsGroup": "group",
                  "physicsLinearDamping": "linear_damping", "physicsAngularDamping": "angular_damping",
                  "physicsFriction": "friction", "physicsKinematic": "kinematic",
                  "physicsStartAwake": "start_awake"}


def event_file(kind: int, number: int, target: str | None) -> str:
    """The Studio 2 code file name for one event of one object."""
    if kind == 4:
        # Collision code is named after the *other* object, without the subtype.
        return f"Collision_{target}.gml"
    return f"{EVENT_NAMES[kind]}_{number}.gml"


def delivered(kind: int, number: int) -> bool:
    """Does this runtime dispatch this event subtype at all?"""
    if kind not in DELIVERED:
        return False
    allowed = DELIVERED[kind]
    return True if allowed is None else number in allowed


def delivered_reason(kind: int, number: int) -> str | None:
    """``None`` when the runtime delivers this event, else why it does not."""
    if delivered(kind, number):
        return None
    return NOT_DELIVERED.get((kind, number), FALLBACK_REASON)


def label(kind: int, number: int) -> str:
    """A readable event name for the report, e.g. ``Other/Animation End (7:7)``."""
    name = EVENT_NAMES.get(kind, f"Type {kind}")
    if kind == 4:
        return f"Collision with {number}"
    subtype = SUBTYPE_NAMES.get(kind, {}).get(number)
    if subtype is None and kind in (5, 9, 10):
        subtype = f"key {number}"
    if subtype is None and kind == 2:
        subtype = f"alarm {number}"
    if subtype is None and kind == 7 and 10 <= number <= 25:
        subtype = f"User {number - 10}"
    return f"{name}/{subtype} ({kind}:{number})" if subtype else f"{name} ({kind}:{number})"


class ObjectConverter:
    """Every Yellow object and event, in the runtime's own module shape."""

    def __init__(self, registry: Registry, root: Path, provenance: dict, prefix: str):
        self.registry = registry
        self.source = registry.source
        self.root = root
        self.provenance = provenance
        self.prefix = prefix
        #: Same name map the script front end uses, so an event resolves assets
        #: exactly like the scripts that call into it.
        self.resolver: dict[str, int | str] = {}
        for category in ("sprites", "objects", "rooms", "sounds", "backgrounds", "fonts", "paths"):
            self.resolver.update(registry.names(category))
        for name in registry.project_order.get("scripts", []):
            self.resolver[name] = name
        self.names = list(registry.project_order.get("objects", []))
        #: merged object ID -> generated module path
        self.modules: dict[int, str] = {}
        #: merged object ID -> the metadata the runtime reads
        self.metadata: dict[int, dict] = {}
        self.findings: list[dict] = []
        self.compile_errors: list[dict] = []
        self.events = 0
        self.source_lines = 0
        self.keys: set[int] = set()
        self.mouse_subtypes: set[int] = set()
        self.parents: dict[int, int] = {}

    # -- helpers ---------------------------------------------------------
    def note(self, kind: str, **fields) -> None:
        self.findings.append({"kind": kind, **fields})

    def reference(self, category: str, value, name: str, field: str) -> int:
        """A Yellow asset reference as a merged ID, or -1 for "no asset"."""
        target = ref_name(value)
        if target is None:
            return -1
        index = self.registry.id_of(category, target)
        if index is None:
            raise GMS2Error(f"objects/{name}: {field} names {target}, which has no recovered "
                            f"Yellow {category} ID; not inventing one")
        return YELLOW_BASE + index

    # -- one object ------------------------------------------------------
    def convert(self, name: str) -> tuple[dict, dict[str, str]]:
        folder = self.source / "objects" / name
        record_path = folder / f"{name}.yy"
        if not record_path.is_file():
            raise GMS2Error(f"objects/{name}: pinned object ID has no folder in the source")
        data = read(record_path)
        if data.get("name") != name:
            raise GMS2Error(f"objects/{name}: the record calls itself {data.get('name')!r}")
        if data.get("properties") or data.get("overriddenProperties"):
            raise GMS2Error(f"objects/{name}: Studio 2 object variables are not converted; "
                            "they would have to become Create-event prologue code")
        if data.get("isDnD") or any(entry.get("isDnD") for entry in data.get("eventList") or []):
            raise GMS2Error(f"objects/{name}: Drag and Drop events have no GML to convert")
        sprite = self.reference("sprites", data.get("spriteId"), name, "spriteId")
        mask = self.reference("sprites", data.get("spriteMaskId"), name, "spriteMaskId")
        parent = self.reference("objects", data.get("parentObjectId"), name, "parentObjectId")
        merged = self.registry.merged("objects", name)
        self.parents[merged] = parent
        physics = None
        if data.get("physicsObject"):
            physics = {target: data.get(source) for source, target in PHYSICS_FIELDS.items()}
            physics["shape_points"] = [[point.get("x"), point.get("y")]
                                       for point in data.get("physicsShapePoints") or []]
            self.note("physics-object", object=name, merged_id=merged, shape=physics.get("shape"))

        events: dict[tuple[int, int], str] = {}
        collisions: list[dict] = []
        locals_: dict[str, list[str]] = {}
        inert: list[str] = []
        for entry in data.get("eventList") or []:
            kind, number = int(entry["eventType"]), int(entry["eventNum"])
            if kind not in EVENT_NAMES:
                raise GMS2Error(f"objects/{name}: unknown Studio 2 event type {kind}")
            target = ref_name(entry.get("collisionObjectId")) if kind == 4 else None
            if kind == 4:
                if target is None:
                    raise GMS2Error(f"objects/{name}: collision event without a target object")
                index = self.registry.id_of("objects", target)
                if index is None:
                    raise GMS2Error(f"objects/{name}: collision target {target} has no recovered "
                                    "Yellow object ID; not inventing one")
                collisions.append({"object": target, "merged_id": YELLOW_BASE + index})
            file_name = event_file(kind, number, target)
            key = (4, YELLOW_BASE + index) if kind == 4 else (kind, number)
            if key in events:
                raise GMS2Error(f"objects/{name}: duplicate event {key[0]}:{key[1]}")
            code_path = folder / file_name
            if not code_path.is_file():
                raise GMS2Error(f"objects/{name}: event {key[0]}:{key[1]} is listed but "
                                f"{file_name} is missing from the pinned source")
            source = code_path.read_text(encoding="utf-8-sig", errors="replace")
            self.source_lines += len(source.splitlines())
            origin = f"objects/{name}/{file_name}"
            try:
                module, _, declared = compile_gml2_event(source, origin, self.resolver)
            except (CompileError, RecursionError) as exc:
                self.compile_errors.append({"object": name, "event": f"{key[0]}:{key[1]}",
                                            "source": origin, "error": str(exc)})
                continue
            self.events += 1
            if kind in (5, 9, 10):
                self.keys.add(number)
            if kind == 6 and number < 12:
                # Per-instance mouse events need the pointer over the instance;
                # the global 50-58 family does not. Both come from one gate.
                self.mouse_subtypes.add(number)
            if declared:
                locals_[f"{key[0]}:{key[1]}"] = sorted(declared)
                self.note("local-function", object=name, event=f"{key[0]}:{key[1]}", functions=sorted(declared))
            reason = delivered_reason(kind, number)
            if reason:
                inert.append(label(kind, number))
                self.note("undispatched-event", object=name, event=label(kind, number), reason=reason)
            events[key] = function_expression(module)

        meta = {
            "name": name,
            "id": merged,
            "sprite": sprite,
            "mask": mask,
            "parent": parent,
            "solid": int(bool(data.get("solid"))),
            "visible": int(bool(data.get("visible"))),
            "persistent": int(bool(data.get("persistent"))),
            # Studio 2 has no object depth; piece 4 assigns it from the room layer.
            "depth": 0,
            "physics": 1 if physics else 0,
            "yellow": {
                "id": self.registry.id_of("objects", name),
                "depth_source": "room layer (piece 4)",
                "collision_events": [entry["merged_id"] for entry in collisions],
                "local_functions": locals_,
                "undispatched_events": sorted(inert),
                "physics": physics,
            },
        }
        return meta, {f"{kind}:{number}": events[(kind, number)] for kind, number in sorted(events)}

    def module_text(self, meta: dict, events: dict[str, str]) -> str:
        lines = ["-- Generated Yellow object; IDs are 1000000 + the pinned Asset_Order ID.",
                 "local object = " + lua(meta), "object.events = {}"]
        for key, expression in events.items():
            lines.append(f"object.events[{quote(key)}] = {expression}")
        lines.append("return object\n")
        return "\n".join(lines)

    # -- all objects -----------------------------------------------------
    def run(self, writer) -> dict:
        expected = set(self.registry.ids["objects"])
        if set(self.names) != expected:
            raise GMS2Error("the pinned project order and the pinned ID list disagree about which "
                            f"objects exist: {sorted(expected - set(self.names))[:5]} / "
                            f"{sorted(set(self.names) - expected)[:5]}")
        for name in sorted(self.names):
            meta, events = self.convert(name)
            writer.write(f"objects/{name}.lua", self.module_text(meta, events))
            self.modules[meta["id"]] = f"{self.prefix}.objects.{name}"
            self.metadata[meta["id"]] = meta
        if self.compile_errors:
            raise CompileError(f"{len(self.compile_errors)} Yellow object events failed; "
                               "see the conversion report")
        self._check_parents()
        return self.summary()

    def _check_parents(self) -> None:
        """A parent loop would hang ``Runtime:isA`` and ``findEvent``, so refuse it."""
        for merged in sorted(self.parents):
            path, index = [], merged
            while index is not None and index >= 0:
                if index in path:
                    names = [self.registry.yellow_name("objects", step) or str(step) for step in path + [index]]
                    raise GMS2Error("Yellow object parents form a loop: " + " -> ".join(names))
                path.append(index)
                index = self.parents.get(index, -1)

    def summary(self) -> dict:
        kinds: dict[str, int] = {}
        for finding in self.findings:
            kinds[finding["kind"]] = kinds.get(finding["kind"], 0) + 1
        inert: dict[str, dict] = {}
        locals_: dict[str, dict] = {}
        for finding in self.findings:
            if finding["kind"] == "undispatched-event":
                entry = inert.setdefault(finding["event"], {"objects": 0, "reason": finding["reason"]})
                entry["objects"] += 1
            if finding["kind"] == "local-function":
                locals_.setdefault(finding["object"], {})[finding["event"]] = finding["functions"]
        return {
            "converted": len(self.modules),
            "expected": len(self.registry.ids["objects"]),
            "events": self.events,
            "source_lines": self.source_lines,
            "compile_errors": self.compile_errors,
            "with_parent": sum(1 for meta in self.metadata.values() if meta["parent"] >= 0),
            "with_sprite": sum(1 for meta in self.metadata.values() if meta["sprite"] >= 0),
            "with_mask": sum(1 for meta in self.metadata.values() if meta["mask"] >= 0),
            "solid": sum(1 for meta in self.metadata.values() if meta["solid"]),
            "invisible": sum(1 for meta in self.metadata.values() if not meta["visible"]),
            "persistent": sum(1 for meta in self.metadata.values() if meta["persistent"]),
            "physics_objects": sorted(self.registry.yellow_name("objects", merged) or str(merged)
                                      for merged, meta in self.metadata.items() if meta["physics"]),
            "collision_events": sum(len(meta["yellow"]["collision_events"]) for meta in self.metadata.values()),
            "keyboard_keys": sorted(self.keys),
            "mouse_subtypes": sorted(self.mouse_subtypes),
            "undispatched_events": dict(sorted(inert.items())),
            #: complete, not a sample: a scope-local function that went missing
            #: would turn into an unknown-function stop at runtime.
            "local_functions": dict(sorted(locals_.items())),
            "findings": kinds,
            "finding_examples": {kind: [f for f in self.findings if f["kind"] == kind][:5]
                                 for kind in sorted(kinds)},
        }
