"""Part catalogue, joints, holes and fasteners for the step-by-step assembly guide.

Standard library only. Units are inches in Fusion axes: x across (bed 0-86.75, bookcase
86.75-116.75), y from the wall (0) to the room side (16), z up.
"""

import json
from dataclasses import dataclass, replace
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
    boxes: tuple = ()  # ((lo, hi), ...): one box for wood, one or more for a steel shape
    host: object = None  # steel and hardware travel with this part's pose
    representative: bool = False  # steel shape not dimensioned by the manual

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
        parts[pid] = replace(parts[pid], boxes=((parts[pid].min, parts[pid].max),))
    if set(parts) != {spec[0] for spec in PART_SPECS}:
        raise ValueError("drawing-geometry.json does not hold all 27 parts")
    parts.update(STEEL)
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
    joint: str  # joint or pattern id
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
    located: str = "rule"  # 'rule' | 'rockler' | 'stud' | 'transfer'
    aligned: bool = False  # position taken from alignment on Rockler's drawing, not a printed dimension
    example: object = None  # (x, y, z) used only to draw a stud/transfer hole at an example position
    name: object = None  # Rockler's hole name, e.g. 'A1' on a wall bracket


@dataclass(frozen=True)
class Joint:
    id: str
    side: str  # the part that takes the face holes and the screw clearance holes
    panel: str  # the part whose edge takes the edge dowel holes and the screw pilots
    dowels: list  # distances from the joint's datum along its run
    screws: list
    band: object = None  # (low, high) up the side, inches, for joints that must stay inside a band
    hold: object = None  # open-decision id that holds this joint


@dataclass(frozen=True)
class JointGeometry:
    contact_axis: int  # axis normal to the contact plane
    contact: float  # the contact plane's coordinate on that axis
    direction: int  # +1/-1: from the side into the panel along contact_axis
    run_axis: int  # axis the holes are spaced along
    datum: float  # coordinate the run is measured from
    run_sign: int  # +1/-1: direction of increasing distance from the datum
    centre: tuple  # centre of the contact patch; holes sit on it in the third axis
    datum_name: str


AXIS_NAMES = "xyz"
# Name of the reference a side's `v` is measured from, by the axis it lies along.
V_REFERENCE = {0: "end at M01", 1: "wall edge", 2: "bottom end"}


def _bookcase_joint(panel, side, band, hold=None):
    return Joint(f"{panel}-{side}", side, panel, [4, 12], [2, 8, 14], band=band, hold=hold)


def _side_joint(panel, side):
    return Joint(f"{panel}-{side}", side, panel, [4, 12], [2, 8, 14])


_LENGTHS = {pid: length for pid, _key, _label, _w, length, _t in PART_SPECS}


def headboard_joint(panel, side):
    """A headboard edge into the top or bottom: dowels at 1/4, 1/2, 3/4; screws 3 in from each end and
    at 1/3 and 2/3 of the run."""
    run = _LENGTHS[panel]
    return Joint(f"{panel}-{side}", side, panel, [run / 4, run / 2, 3 * run / 4],
                 [3, run / 3, 2 * run / 3, run - 3])


JOINTS = {j.id: j for j in (
    _bookcase_joint("L04", "L01", (2.5, 3.25)),
    _bookcase_joint("L04", "L02", (2.5, 3.25)),
    _bookcase_joint("L07", "L01", (14.0, 14.75), hold="slide"),
    _bookcase_joint("L07", "L02", (14.0, 14.75), hold="slide"),
    _bookcase_joint("L03", "L01", (63.25, 64.0)),
    _bookcase_joint("L03", "L02", (63.25, 64.0)),
    _side_joint("M03", "M01"), _side_joint("M04", "M01"), _side_joint("M05", "M01"), _side_joint("M06", "M01"),
    _side_joint("M03", "M02"), _side_joint("M04", "M02"), _side_joint("M05", "M02"), _side_joint("M06", "M02"),
    headboard_joint("M05", "M03"),
    headboard_joint("M06", "M04"),
)}


def joint_geometry(joint, parts):
    """Where the side meets the panel: the contact plane, the run the holes are spaced along and its datum.

    The parts must meet face to face: touching on one axis with a positive overlap on both others.
    """
    side, panel = parts[joint.side], parts[joint.panel]
    for axis in range(3):
        if abs(side.max[axis] - panel.min[axis]) < EPS:
            contact, direction = side.max[axis], 1
        elif abs(side.min[axis] - panel.max[axis]) < EPS:
            contact, direction = side.min[axis], -1
        else:
            continue
        others = [k for k in range(3) if k != axis]
        lo = {k: max(side.min[k], panel.min[k]) for k in others}
        hi = {k: min(side.max[k], panel.max[k]) for k in others}
        if any(hi[k] - lo[k] <= EPS for k in others):
            continue
        run = max(others, key=lambda k: hi[k] - lo[k])
        centre = [0.0, 0.0, 0.0]
        centre[axis] = contact
        for k in others:
            centre[k] = (lo[k] + hi[k]) / 2
        if run == 1:
            datum, sign, name = hi[run], -1, "front edge"
        elif run == 2:
            datum, sign, name = lo[run], 1, "lower end"
        else:
            datum, sign, name = lo[run], 1, "end at M01"
        return JointGeometry(axis, contact, direction, run, datum, sign, tuple(centre), name)
    raise ValueError(f"{joint.id}: {joint.side} and {joint.panel} do not meet face to face")


def joint_holes(joint, parts):
    side, panel = parts[joint.side], parts[joint.panel]
    g = joint_geometry(joint, parts)
    third = 3 - g.contact_axis - g.run_axis
    into_side, into_panel = [0, 0, 0], [0, 0, 0]
    into_side[g.contact_axis], into_panel[g.contact_axis] = -g.direction, g.direction
    into_side, into_panel = tuple(into_side), tuple(into_panel)
    holes = []

    def add(part, surface, kind, through, diameter, depth, countersink, distance, axis):
        on_side = part is side
        world = [0.0, 0.0, 0.0]
        world[g.contact_axis] = g.contact
        world[g.run_axis] = g.datum + g.run_sign * distance
        world[third] = g.centre[third]
        holes.append(Hole(
            joint=joint.id, part=part.id, surface=surface, kind=kind, through=through,
            diameter=diameter, depth=depth, countersink=countersink,
            ref_edge=g.datum_name,
            ref_end=V_REFERENCE[third] if on_side else f"end at {joint.side}",
            u=distance,
            v=(world[third] - part.min[third]),
            world=tuple(world), axis=axis))

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


def _wall_errors(hole, part, name):
    if hole.through:
        return []
    i = _axis_index(hole.axis)
    if hole.surface == "face":
        left = drilling_thickness(part) - hole.depth
    else:
        left = min(edge_wall(hole, part), part.size[i] - hole.depth)
    if left < MIN_WALL - EPS:
        return [f"{name} leaves {left:.3f} in, less than 1/8 in"]
    return []


def _hole_errors(hole, part):
    name = f"{hole.joint} {hole.kind} hole in {hole.part}"
    i = _axis_index(hole.axis)
    entry = part.min[i] if hole.axis[i] > 0 else part.max[i]
    r = hole.diameter / 2
    inside = all(part.min[k] - EPS <= hole.world[k] - r and hole.world[k] + r <= part.max[k] + EPS
                 for k in range(3) if k != i)
    if abs(hole.world[i] - entry) > EPS or not inside:
        return [f"{name} at {hole.world} is not on its {hole.surface}"]
    return _wall_errors(hole, part, name)


def check_holes(holes, parts, held_joints):
    """Position, wall and spacing rules. Stud-located holes (no cabinet position) get only the wall
    rule; holes in the wall itself get none."""
    errors = []
    located = [h for h in holes if h.world is not None and h.part != "wall"]
    for hole in holes:
        if hole.world is None and hole.part != "wall":
            errors += _wall_errors(hole, parts[hole.part], f"{hole.joint} {hole.kind} hole in {hole.part}")
    for hole in located:
        errors += _hole_errors(hole, parts[hole.part])
        joint = JOINTS.get(hole.joint)
        if joint and joint.band and hole.part == joint.side:
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
# Hole patterns: holes that belong to no joint (Rockler's insert layout, stud-located anchoring)

# Stud-located holes follow the actual studs. These x positions place them in the 3D view only;
# they are never checked or dimensioned.
EXAMPLE_STUDS = (11.375, 43.375, 75.375)
STEEL_THICKNESS = 0.1875


@dataclass(frozen=True)
class Fixing:
    code: str  # fastener catalogue code
    kind: str  # glyph: 'insert' | 'screw' | 'lag' | 'bolt'
    at: object  # 'all' (one per hole) or a tuple of hole names (one per named hole, per stud)


@dataclass(frozen=True)
class Pattern:
    id: str
    part: str
    holes: list  # Hole templates in the part frame (u, v); pattern_holes places them
    hardware: list  # Fixing
    hold: object = None
    source: str = ""
    frame: str = "inside-face"  # 'inside-face' | 'front-face' | 'top-face'


def _template(kind, diameter, depth, through, ref_edge, ref_end, u, v, verified, located="rockler",
              aligned=False, name=None, part=None):
    return Hole(joint="", part=part or "", surface="face", kind=kind, through=through, diameter=diameter,
                depth=depth, countersink=False, ref_edge=ref_edge, ref_end=ref_end, u=u, v=v, world=None,
                axis=(0, 0, 0), verified=verified, located=located, aligned=aligned, name=name)


def _insert_holes():
    # (u from the front edge, v up from the bottom end, aligned): Rockler p. 8 drilling guide.
    at = [(9 + 7 / 16, 11 + 7 / 16, False), (9 + 7 / 16, 17 + 11 / 16, True), (9 + 7 / 16, 25.25, True),
          (9 + 7 / 16, 27.75, True), (9 + 7 / 16, 30.25, True), (3.125, 11 + 7 / 16, True),
          (3.125, 13 + 7 / 8, False), (6 + 15 / 16, 17 + 11 / 16, False)]
    return [_template("insert", 27 / 64, 9 / 16, False, "front edge", "bottom end", u, v, "Rockler p. 8",
                      aligned=aligned) for u, v, aligned in at]


def _lag_holes(ref_end):
    return [_template("lag", 0.1875, 0.75, True, "stud line", ref_end, None, 3.0, "Rockler p. 11",
                      located="stud")]


def _bracket_holes():
    # v from the wall along the stud line on the top's upper face: Rockler p. 12, Fig. 6.
    cabinet = [("A1", "steel-dowel", 13 / 64, False, 4.625), ("A2", "bolt", 0.3125, True, 4.0),
               ("A3", "pilot", 0.125, False, 2.75), ("A4", "pilot", 0.125, False, 1.5)]
    holes = [_template(kind, d, 0.5 if not through else 0.75, through, "stud line", "wall", None, v,
                       "Rockler p. 12", located="stud", name=name)
             for name, kind, d, through, v in cabinet]
    # A5/A6: lag pilots in the wall, marked through the fitted bracket's leg (no Rockler dimension).
    holes += [_template("pilot", 0.1875, None, False, "stud line", "bracket leg", None, None, "Rockler p. 12",
                        located="transfer", name=name, part="wall") for name in ("A5", "A6")]
    return holes


WALL_HOLE_HEIGHTS = {"A5": 65.0, "A6": 66.5}  # example positions on the bracket leg, 3D only

PATTERNS = {p.id: p for p in (
    Pattern("inserts-M01", "M01", _insert_holes(),
            [Fixing("T", "insert", "all"), Fixing("U", "screw", "all")], source="Rockler p. 8"),
    Pattern("inserts-M02", "M02", _insert_holes(),
            [Fixing("T", "insert", "all"), Fixing("U", "screw", "all")], source="Rockler p. 8"),
    Pattern("lag-M05", "M05", _lag_holes("top edge"), [Fixing("KK", "lag", "all")], source="Rockler p. 11",
            frame="front-face"),
    Pattern("lag-M06", "M06", _lag_holes("bottom edge"), [Fixing("KK", "lag", "all")], source="Rockler p. 11",
            frame="front-face"),
    Pattern("brackets-M03", "M03", _bracket_holes(),
            [Fixing("II", "bolt", ("A2",)), Fixing("JJ", "screw", ("A3", "A4")), Fixing("KK", "lag", ("A5", "A6"))],
            hold="pilot-depth", source="Rockler p. 12", frame="top-face"),
)}


def _inside_face(part):
    """x of a bed side's inside face and the axis pointing into the side from it."""
    if part.centre[0] < 43.375:
        return part.max[0], (-1, 0, 0)
    return part.min[0], (1, 0, 0)


def pattern_holes(pattern_id, parts):
    """The pattern's holes placed on its part: located holes get `world`; stud and wall holes get an
    `example` at each example stud and no `world`."""
    pattern = PATTERNS[pattern_id]
    part = parts[pattern.part]
    holes = []
    for t in pattern.holes:
        if pattern.frame == "inside-face":
            x, axis = _inside_face(part)
            holes.append(replace(t, joint=pattern.id, part=part.id, axis=axis,
                                 world=(x, part.max[1] - t.u, part.min[2] + t.v)))
            continue
        for stud in EXAMPLE_STUDS:
            if t.part == "wall":
                example, axis = (stud, 0.0, WALL_HOLE_HEIGHTS[t.name]), (0, -1, 0)
                holes.append(replace(t, joint=pattern.id, axis=axis, example=example))
                continue
            if pattern.frame == "front-face":
                z = part.max[2] - t.v if t.ref_end == "top edge" else part.min[2] + t.v
                example, axis = (stud, part.max[1], z), (0, -1, 0)
            else:  # top-face, v from the wall
                example, axis = (stud, part.min[1] + t.v, part.max[2]), (0, 0, -1)
            holes.append(replace(t, joint=pattern.id, part=part.id, axis=axis, example=example))
    if pattern.frame != "inside-face":
        names = [t.name for t in pattern.holes]
        if any(names):  # group per stud, in template order: A1..A6 at stud 1, then stud 2, ...
            holes.sort(key=lambda h: (EXAMPLE_STUDS.index(h.example[0]), names.index(h.name)))
    return holes


def fixing_holes(fixing, holes):
    """Holes a fixing goes into: every hole, or the named ones in hole order and then stud order."""
    if fixing.at == "all":
        return holes
    return [h for name in fixing.at for h in holes if h.name == name]


def fixing_direction(fixing, hole):
    """The way a fastener travels: into its hole, except a bolt, which comes up through it from below."""
    if fixing.kind == "bolt":
        return tuple(-a for a in hole.axis)
    return hole.axis


def pattern_fixings(pattern_id, parts):
    """[(fixing, node name, hole)] for a pattern's hardware; nodes are <pattern>-<code>-<n>."""
    holes = pattern_holes(pattern_id, parts)
    out = []
    for fixing in PATTERNS[pattern_id].hardware:
        for n, hole in enumerate(fixing_holes(fixing, holes), 1):
            out.append((fixing, f"{pattern_id}-{fixing.code}-{n}", hole))
    return out


# ---------------------------------------------------------------------------
# Steel: one simplified shape per Rockler part, carried with its host part

def _steel(sid, host, boxes):
    lo = tuple(min(b[0][k] for b in boxes) for k in range(3))
    hi = tuple(max(b[1][k] for b in boxes) for k in range(3))
    return Part(id=sid, label=f"Rockler {sid.split('-')[0]}", assembly="bed", min=lo, max=hi,
                stock=STEEL_THICKNESS, finish="steel", stage="bed-cabinet", boxes=tuple(boxes), host=host,
                representative=True)


def _plate(sid, host, face, outward):
    """Mounting plate I on a side's inside face: a column, a foot and a brace, (u, v) from the front and
    bottom."""
    x0, x1 = sorted((face, face + outward * STEEL_THICKNESS))
    boxes = []
    # Column, foot and brace together cover all eight insert holes (representative shape).
    for (u0, u1), (v0, v1) in (((8.75, 10.125), (10.875, 31.0)), ((2.5, 10.125), (10.875, 14.5)),
                               ((6.25, 8.75), (14.5, 18.5))):
        boxes.append(((x0, 16.0 - u1, v0), (x1, 16.0 - u0, v1)))
    return _steel(sid, host, boxes)


def _wall_bracket(n, stud):
    x0, x1 = stud - 0.625, stud + 0.625
    foot = ((x0, 0.0, 64.0), (x1, 5.25, 64.0 + STEEL_THICKNESS))
    leg = ((x0, 0.0, 64.0 + STEEL_THICKNESS), (x1, STEEL_THICKNESS, 67.0))
    return _steel(f"HH-{n}", "M03", [foot, leg])


STEEL = {s.id: s for s in (
    _plate("I-R", "M01", 0.75, 1),
    _plate("I-L", "M02", 86.0, -1),
    *(_wall_bracket(n, stud) for n, stud in enumerate(EXAMPLE_STUDS, 1)),
)}


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
