"""Part catalogue, joints, holes and fasteners for the step-by-step assembly guide.

Standard library only. Units are inches in Fusion axes: x across (bed 0-86.75, bookcase
86.75-116.75), y from the wall (0) to the room side (16), z up.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import generate_cut_layouts
from generate_cut_layouts import PART_SPECS

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = ROOT / "output" / "drawing-geometry.json"

NATURAL_PARTS = {"L11", "L12", "L13", "L14", "L15"}
CABINET_PARTS = {"M01", "M02", "M03", "M04", "M05", "M06"}
STAGES = ("bed-cabinet", "bed-mechanism", "bookcase")


def part_stage(pid):
    if pid.startswith("L"):
        return "bookcase"
    return "bed-cabinet" if pid in CABINET_PARTS else "bed-mechanism"
FINISH_COLOURS = {"navy": "#182B49", "natural": "rgb(217,191,151)"}


@dataclass(frozen=True)
class Part:
    id: str
    label: str
    assembly: str  # 'bed' | 'bookcase'
    min: tuple
    max: tuple
    stock: float
    finish: str  # 'navy' | 'natural'
    stage: str  # 'bookcase' | 'bed-cabinet' | 'bed-mechanism'

    @property
    def centre(self):
        return tuple((a + b) / 2 for a, b in zip(self.min, self.max))

    @property
    def size(self):
        return tuple(b - a for a, b in zip(self.min, self.max))


def model_key(name):
    """Fusion body name -> PART_SPECS key."""
    key = name.split(" |", 1)[0].split(" —", 1)[0].strip()
    if key.startswith("SC "):
        key = "Left cabinet: " + key[3:]
    return key


_SPECS = {key: (pid, label, thickness) for pid, key, label, _w, _l, thickness in PART_SPECS}


def part_id_for(name):
    key = model_key(name)
    if key not in _SPECS:
        raise ValueError(f"Unknown model part: {name}")
    return _SPECS[key][0]


def load_parts(geometry=GEOMETRY):
    data = json.loads(Path(geometry).read_text(encoding="utf-8"))
    if data.get("units") != "inches":
        raise ValueError("drawing-geometry.json must be in inches")
    parts = {}
    for body in data["wood"]:
        key = model_key(body["name"])
        if key not in _SPECS:
            raise ValueError(f"Unknown model part: {body['name']}")
        pid, label, thickness = _SPECS[key]
        if pid in parts:
            raise ValueError(f"Duplicate model part: {body['name']}")
        parts[pid] = Part(
            id=pid, label=label,
            assembly="bookcase" if pid.startswith("L") else "bed",
            min=tuple(float(v) for v in body["min"]),
            max=tuple(float(v) for v in body["max"]),
            stock=thickness,
            finish="natural" if pid in NATURAL_PARTS else "navy",
            stage=part_stage(pid),
        )
    if set(parts) != {spec[0] for spec in PART_SPECS}:
        raise ValueError("drawing-geometry.json does not hold all 27 parts")
    return dict(sorted(parts.items()))


def drilling_thickness(part):
    """Thickness used for wall checks: measured minimum for 3/4 stock, nominal - 1/32 otherwise."""
    if part.stock == 0.75:
        return generate_cut_layouts.MEASURED_34[0]  # measured minimum; one source for every generator
    return part.stock - 1 / 32


# ---------------------------------------------------------------------------
# Joints and holes

EPS = 1e-6
MIN_WALL = 0.125
MIN_SPACING = 1.0
DOWEL_DIAMETER = 0.375
DOWEL_FACE_DEPTH = 0.5
DOWEL_EDGE_DEPTH = 1.0625
CLEARANCE_DIAMETER = 0.1875
PILOT_DIAMETER = 0.125
PILOT_DEPTH = 1.25


@dataclass(frozen=True)
class Hole:
    joint: str
    part: str
    surface: str  # 'face' | 'edge'
    kind: str  # 'dowel' | 'clearance' | 'pilot' | 'transfer' | 'stud'
    through: bool
    diameter: float
    depth: float
    countersink: bool
    ref_edge: str
    ref_end: str
    u: object  # float | None (None only for transfer/stud holes)
    v: object
    world: object  # (x, y, z) on the part's surface | None
    axis: tuple  # unit vector pointing into the part
    verified: object = None  # page reference for a transcribed pattern


@dataclass(frozen=True)
class Joint:
    id: str
    side: str
    panel: str
    band: tuple  # (low, high) up the side, inches
    dowels: list  # distances from the datum (front edge, y = 16)
    screws: list
    hold: object = None  # open-decision id that holds this joint


def _bookcase_joint(panel, side, band, hold=None):
    return Joint(f"{panel}-{side}", side, panel, band, [4, 12], [2, 8, 14], hold)


JOINTS = {j.id: j for j in (
    _bookcase_joint("L04", "L01", (2.5, 3.25)),
    _bookcase_joint("L04", "L02", (2.5, 3.25)),
    _bookcase_joint("L07", "L01", (14.0, 14.75), hold="slide"),
    _bookcase_joint("L07", "L02", (14.0, 14.75), hold="slide"),
    _bookcase_joint("L03", "L01", (63.25, 64.0)),
    _bookcase_joint("L03", "L02", (63.25, 64.0)),
)}


def joint_contact(joint, parts):
    """Contact plane x and the direction (+1/-1) from the side into the panel."""
    side, panel = parts[joint.side], parts[joint.panel]
    if abs(side.max[0] - panel.min[0]) < EPS:
        return side.max[0], 1
    if abs(side.min[0] - panel.max[0]) < EPS:
        return side.min[0], -1
    raise ValueError(f"{joint.id}: {joint.side} does not touch {joint.panel}")


def joint_holes(joint, parts):
    side, panel = parts[joint.side], parts[joint.panel]
    x, direction = joint_contact(joint, parts)
    z = panel.centre[2]
    front = side.max[1]
    into_side, into_panel = (-direction, 0, 0), (direction, 0, 0)
    holes = []

    def add(part, surface, kind, through, diameter, depth, countersink, distance, axis):
        on_side = part is side
        holes.append(Hole(
            joint=joint.id, part=part.id, surface=surface, kind=kind, through=through,
            diameter=diameter, depth=depth, countersink=countersink,
            ref_edge="front edge",
            ref_end="bottom end" if on_side else f"end at {joint.side}",
            u=distance,
            v=(z - part.min[2]),
            world=(x, front - distance, z), axis=axis))

    for d in joint.dowels:
        add(side, "face", "dowel", False, DOWEL_DIAMETER, DOWEL_FACE_DEPTH, False, d, into_side)
    for d in joint.screws:
        add(side, "face", "clearance", True, CLEARANCE_DIAMETER, side.stock, True, d, into_side)
    for d in joint.dowels:
        add(panel, "edge", "dowel", False, DOWEL_DIAMETER, DOWEL_EDGE_DEPTH, False, d, into_panel)
    for d in joint.screws:
        add(panel, "edge", "pilot", False, PILOT_DIAMETER, PILOT_DEPTH, False, d, into_panel)
    return holes


def _axis_index(axis):
    return max(range(3), key=lambda i: abs(axis[i]))


def edge_wall(hole, part):
    """Material left on each side of an edge hole across the panel's thickness."""
    return (drilling_thickness(part) - hole.diameter) / 2


def _hole_errors(hole, part):
    errors = []
    name = f"{hole.joint} {hole.kind} hole in {hole.part}"
    i = _axis_index(hole.axis)
    entry = part.min[i] if hole.axis[i] > 0 else part.max[i]
    inside = all(part.min[k] - EPS <= hole.world[k] <= part.max[k] + EPS for k in range(3) if k != i)
    if abs(hole.world[i] - entry) > EPS or not inside:
        errors.append(f"{name} at {hole.world} is not on its {hole.surface}")
        return errors
    if hole.through:
        return errors
    if hole.surface == "face":
        left = drilling_thickness(part) - hole.depth
    else:
        left = min(edge_wall(hole, part), part.size[i] - hole.depth)
    if left < MIN_WALL - EPS:
        errors.append(f"{name} leaves {left:.3f} in, less than 1/8 in")
    return errors


def check_holes(holes, parts, held_joints):
    errors = []
    located = [h for h in holes if h.world is not None]
    for hole in located:
        errors += _hole_errors(hole, parts[hole.part])
        joint = JOINTS.get(hole.joint)
        if joint and hole.part == joint.side:
            low, high = joint.band
            z, r = hole.world[2], hole.diameter / 2
            if z - r < low - EPS or z + r > high + EPS:
                errors.append(f"{hole.joint} {hole.kind} hole in {hole.part} at z = {z:.3f} "
                              f"is outside joint band {low}-{high}")
    for n, a in enumerate(located):
        for b in located[n + 1:]:
            if a.part != b.part:
                continue
            if a.joint in held_joints or b.joint in held_joints or (a.verified and b.verified):
                continue
            gap = sum((p - q) ** 2 for p, q in zip(a.world, b.world)) ** 0.5
            if gap < MIN_SPACING - EPS:
                errors.append(f"{a.joint} {a.kind} and {b.joint} {b.kind} holes in {a.part} "
                              f"are {gap:.3f} in apart, closer than 1 in")
    return errors


# ---------------------------------------------------------------------------
# Fasteners

import csv  # noqa: E402

INVENTORY = ROOT / "output" / "rockler-kit-inventory.csv"
BOM = ROOT / "output" / "bill-of-materials.csv"
FASTENER_GROUP = "Fasteners and adhesives"
KIT_FASTENERS = ("T", "U", "V", "W", "Z", "AA", "BB", "DD", "EE", "FF", "II", "JJ", "KK", "OO")
CONSUMABLES = {"glue": "Wood glue", "threadlocker": "Removable threadlocker"}

# Kit codes fitted while building the bed cabinet; every other kit code belongs to the mechanism.
KIT_STAGE = {"T": "bed-cabinet", "U": "bed-cabinet", "KK": "bed-cabinet", "II": "bed-cabinet",
             "JJ": "bed-cabinet"}

# BOM Item -> (code, name, source, used per stage)
BOM_FASTENERS = {
    "3/8 x 1-1/2-inch dowels": ("dowel", "3/8 x 1-1/2 in dowel", "bought",
                                {"bed-cabinet": 22, "bookcase": 12}),
    "#8 x 2-inch wood/cabinet screws": ("screw-8x2", "#8 x 2 in screw", "bought",
                                        {"bed-cabinet": 32, "bookcase": 18}),
    "#8 x 1-1/4-inch wood screws": ("screw-8x1.25", "#8 x 1-1/4 in screw", "bought", {"bed-mechanism": 4}),
    "#8 x 1-inch washer-head wood screws": ("screw-8x1-washer", "#8 x 1 in washer-head screw", "bought",
                                            {"bookcase": 4}),
    "#6 x 1-1/4-inch wood screws": ("screw-6x1.25", "#6 x 1-1/4 in screw", "bought", {}),
    "#6 x 3/4-inch panel-attachment screws": ("screw-6x0.75", "#6 x 3/4 in screw", "bought", {}),
    "Slide mounting screws": ("screw-slide", "Slide mounting screw", "bundled", {}),
}
BUNDLED = {"screw-pull": "Pull screw", "restraint-fasteners": "Wall restraint fastener"}


@dataclass(frozen=True)
class Fastener:
    code: str
    name: str
    source: str  # 'kit' | 'bought' | 'bundled'
    used: dict  # stage -> count
    bought: int
    supplied: object  # int | None (None = unknown until the hardware is chosen)


DISCREPANCIES = {
    "BB": {
        "used": 34, "supplied": 34,
        "question": "Rockler's inventory lists M8 x 45 mm BB bolts; the frame assembly page calls for 50 mm.",
        "clear_when": ["on-hand-34", "length-confirmed"],
        "recorded": [],
    },
    "W": {
        "used": 88, "supplied": 56,
        "question": ("The assembly uses 88 W screws (32 for the 16 door brackets + 56 through the frame "
                     "tabs) but Rockler's inventory lists 56."),
        "clear_when": ["on-hand-88"],
        "recorded": [],
    },
    "OO": {
        "used": 4, "supplied": 0,
        "question": "The foot bar needs 4 OO M6 nuts, missing from Rockler's inventory table.",
        "clear_when": ["on-hand-4"],
        "recorded": [],
    },
}


def discrepancy_holds(table=None):
    """Code -> HOLD banner for every kit discrepancy not yet cleared."""
    table = DISCREPANCIES if table is None else table
    banners = {}
    for code, entry in table.items():
        if all(c in entry["recorded"] for c in entry["clear_when"]):
            continue
        short = entry["used"] - entry["supplied"]
        confirmed = f"confirmed-supply-{entry['supplied']}" in entry["recorded"]
        text = f"{code}: {entry['question']} Uses {entry['used']}, supplied {entry['supplied']}."
        if short > 0 and confirmed:
            text += f" Rockler confirmed {entry['supplied']}: buy {short} more before this step."
        elif short > 0:
            text += f" Possible shortage of {short} — confirm with Rockler."
        else:
            text += " Confirm with Rockler before this step."
        banners[code] = text.replace("Possible shortage", "possible shortage")
    return banners


def load_fasteners(inventory=INVENTORY, bom=BOM):
    fasteners = {}
    with Path(inventory).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            code = row["Code"]
            if code not in KIT_FASTENERS:
                continue
            quantity = int(row["Queen_quantity"])
            if code in DISCREPANCIES:
                used, supplied = DISCREPANCIES[code]["used"], DISCREPANCIES[code]["supplied"]
            else:
                used, supplied = quantity, quantity
            stage = KIT_STAGE.get(code, "bed-mechanism")
            fasteners[code] = Fastener(code, row["Item"], "kit", {stage: used}, 0, supplied)
    missing = set(KIT_FASTENERS) - set(fasteners)
    if missing:
        raise ValueError(f"Kit inventory is missing fastener codes: {sorted(missing)}")
    with Path(bom).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["Group"] != FASTENER_GROUP or row["Item"] in CONSUMABLES.values():
                continue
            if row["Item"] not in BOM_FASTENERS:
                raise ValueError(f"Unmapped fastener row in the BOM: {row['Item']}")
            code, name, source, used = BOM_FASTENERS[row["Item"]]
            bought = int(row["Buy_quantity"])
            supplied = None if source == "bundled" else 0
            fasteners[code] = Fastener(code, name, source, dict(used), bought if source == "bought" else 0,
                                       supplied)
    absent = {v[0] for v in BOM_FASTENERS.values()} - set(fasteners)
    if absent:
        raise ValueError(f"BOM is missing fastener rows: {sorted(absent)}")
    for code, name in BUNDLED.items():
        fasteners[code] = Fastener(code, name, "bundled", {}, 0, 0)
    return fasteners


def check_fasteners(totals, fasteners, stages):
    """totals: code -> {stage: count} summed over every step."""
    errors = []
    for code in sorted(set(totals) - set(fasteners)):
        errors.append(f"Unknown fastener code {code}")
    for code, entry in fasteners.items():
        if not any(a in entry.used for a in stages):
            continue  # HOLD-only or inactive-stage entries are checked when they become active
        for stage in sorted(stages):
            want = entry.used.get(stage, 0)
            got = totals.get(code, {}).get(stage, 0)
            if got != want:
                errors.append(f"{code}: steps use {got} in the {stage}, expected {want}")
        if code in DISCREPANCIES:
            continue  # a kit shortfall is a HOLD banner (discrepancy_holds), not a build error
        if entry.supplied is None:
            errors.append(f"{code}: used but its supplied quantity is unknown")
        elif sum(entry.used.values()) > entry.bought + entry.supplied:
            errors.append(f"{code}: used {sum(entry.used.values())} exceeds bought {entry.bought} "
                          f"+ supplied {entry.supplied}")
    return errors


# ---------------------------------------------------------------------------
# Open decisions (each shows as a HOLD until the owner records it in this data)

OPEN_DECISIONS = {
    "back": "Back L06 attachment not decided (inset with cleats and screws, rabbet or groove).",
    "slide": ("Drawer-slide model not chosen. It sets the slide screw pattern, the drawer-box clearance "
              "and the space under the fixed shelf L07."),
    "shelf-pins": "Shelf-pin hole layout not decided (rows, spacing, setback; outside the joint bands).",
    "restraint": "Wall restraint for the bookcase not chosen (hardware and position).",
    "plinth": "Plinth L05 attachment to the bottom L04 and the sides not decided.",
    "drawer-box": "Drawer box joints (L11-L14) and the drawer-bottom L15 support not decided.",
    "pulls": ("Pulls not chosen: model, fixing screws, height and edge offset, hole centres and "
              "clearance."),
    "pilot-depth": ("Rockler's 5/8 in blind holes leave about 0.08 in in 0.703 in stock; the guide "
                    "proposes 1/2 in. Owner to confirm."),
    "screw-tips": ("Screw-tip clearance: proposed #8 x 1-1/8 in screws for the stop M07; JJ screws "
                   "checked against the bracket thickness. Owner to confirm."),
    "kit": "Kit fastener discrepancies to confirm with Rockler (BB length, W count, OO nuts).",
}

# Every decision id the data may name, open or resolved. Resolving a decision deletes its entry from
# OPEN_DECISIONS (holds naming it then clear); a hold naming an id outside this set is a typo and
# fails validation. Kept as its own list so deleting an OPEN_DECISIONS entry never removes it here.
DECISION_IDS = frozenset({"back", "slide", "shelf-pins", "restraint", "plinth", "drawer-box", "pulls",
                          "pilot-depth", "screw-tips", "kit"})

# Parts whose own fixing is undecided: any step that adds them is held.
PART_HOLDS = {
    "L05": "plinth", "L06": "back",
    "L08": "shelf-pins", "L09": "shelf-pins", "L10": "shelf-pins",
    "L11": "drawer-box", "L12": "drawer-box", "L13": "drawer-box", "L14": "drawer-box",
    "L15": "drawer-box", "L16": "slide",
}
