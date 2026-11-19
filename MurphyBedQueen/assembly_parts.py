"""Part catalogue, joints, holes and fasteners for the step-by-step assembly guide.

Standard library only. Units are inches in Fusion axes: x across (bed 0-86.75, bookcase
86.75-116.75), y from the wall (0) to the room side (16), z up.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from generate_cut_layouts import PART_SPECS

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = ROOT / "output" / "drawing-geometry.json"

MEASURED_MIN_34 = 0.703  # measured minimum of the 3/4 in plywood
NATURAL_PARTS = {"L11", "L12", "L13", "L14", "L15"}
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
        )
    if set(parts) != {spec[0] for spec in PART_SPECS}:
        raise ValueError("drawing-geometry.json does not hold all 27 parts")
    return dict(sorted(parts.items()))


def drilling_thickness(part):
    """Thickness used for wall checks: measured minimum for 3/4 stock, nominal - 1/32 otherwise."""
    if part.stock == 0.75:
        return MEASURED_MIN_34
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
