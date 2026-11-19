"""Hand-edited step data for the step-by-step assembly guide.

This is the one place to edit guide content. Parts are named by tape-label ID. `move` and poses
are in Fusion axes (x across, y from the wall to the room side, z up), inches.
To resolve an open decision, edit the joint/step data here and in assembly_parts.py and remove its
entry from OPEN_DECISIONS: the HOLD disappears.
"""

ACTIVE_ASSEMBLIES = {"bookcase"}

BOOKCASE_OUTER_X = 116.75  # the outer face of L02
BENCH_OFFSETS = {"bench-1": 30.0, "bench-2": 50.0}
POSES = {
    "installed": "In place in the bookcase.",
    "bench-1": "Lying inside face up on the floor, 30 in beyond the bookcase's outer end.",
    "bench-2": "Lying inside face up on the floor, 50 in beyond the bookcase's outer end.",
}

_CENTRE_X = 101.75  # midway between the sides' inner faces


def _rotation(part):
    """Turn a side so its inside face points up and its length runs along y."""
    if part.centre[0] < _CENTRE_X:  # L01: inside face points +x
        return ((0, 1, 0), (0, 0, 1), (1, 0, 0))
    return ((0, -1, 0), (0, 0, 1), (-1, 0, 0))  # L02: inside face points -x


def _corners(part):
    return [(x, y, z) for x in (part.min[0], part.max[0]) for y in (part.min[1], part.max[1])
            for z in (part.min[2], part.max[2])]


def _apply(r, p):
    return tuple(sum(r[i][k] * p[k] for k in range(3)) for i in range(3))


def pose_matrix(part, pose):
    """4x4 row-major matrix (Fusion inches) taking the installed part to `pose`."""
    if pose == "installed":
        return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    if pose not in BENCH_OFFSETS:
        raise ValueError(f"Unknown pose {pose}")
    r = _rotation(part)
    turned = [_apply(r, c) for c in _corners(part)]
    low = [min(c[i] for c in turned) for i in range(3)]
    target = (BOOKCASE_OUTER_X + BENCH_OFFSETS[pose], 0.0, 0.0)
    t = [target[i] - low[i] for i in range(3)]
    return [list(r[i]) + [t[i]] for i in range(3)] + [[0, 0, 0, 1]]


def pose_box(part, pose):
    m = pose_matrix(part, pose)
    moved = [tuple(sum(m[i][k] * c[k] for k in range(3)) + m[i][3] for i in range(3)) for c in _corners(part)]
    return (tuple(min(c[i] for c in moved) for i in range(3)), tuple(max(c[i] for c in moved) for i in range(3)))


GLUE_DOWELS = "Glue in the dowels and the panel edge, fit the panel, then drive the screws snug, not tight."
TEST_DEPTH = "Set the depth stop and test every hole size on scrap first."

STEPS = [
    {
        "id": "bookcase-drill", "assembly": "bookcase",
        "title": "Drill the bottom and top joint holes in both sides",
        "adds": ["L01", "L02"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [{"joint": "L04-L01", "part": "L01"}, {"joint": "L03-L01", "part": "L01"},
                  {"joint": "L04-L02", "part": "L02"}, {"joint": "L03-L02", "part": "L02"}],
        "pose": {"L01": "bench-1", "L02": "bench-2"},
        "move": [0, 0, -1],
        "camera": {"azimuth": 30, "elevation": 55, "distance": 2.6, "target": "L02"},
        "text": [
            "Lay both sides inside face up: L01 (the side against the bed) and L02 (the outer end).",
            "Mark each row from the front edge and the bottom end, as dimensioned in the drawing.",
            "Drill the two 3/8 in dowel holes 1/2 in deep, then the three 3/16 in screw holes right through.",
            "Turn each side over and countersink the screw holes on the outside face.",
        ],
        "warnings": [TEST_DEPTH, "Keep shelf-pin rows and slide screws out of the joint bands."],
        "hold": None, "requires": [], "source": None,
    },
    {
        "id": "bookcase-drill-shelf", "assembly": "bookcase",
        "title": "Drill the fixed-shelf joint holes in both sides",
        "adds": [], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [{"joint": "L07-L01", "part": "L01"}, {"joint": "L07-L02", "part": "L02"}],
        "pose": {},
        "move": [0, 0, -1],
        "camera": {"azimuth": 30, "elevation": 55, "distance": 2.6, "target": "L02"},
        "text": [
            "On both sides, mark the fixed-shelf row 14 to 14 3/4 in up from the bottom end.",
            "Drill the dowel and screw holes as for the bottom and top rows.",
        ],
        "warnings": [TEST_DEPTH],
        "hold": None, "requires": ["bookcase-drill"], "source": None,
    },
    {
        "id": "bookcase-bottom", "assembly": "bookcase",
        "title": "Fix the bottom L04 to the side against the bed, L01",
        "adds": ["L04"], "joints": ["L04-L01"], "fasteners": {}, "consumables": ["glue"],
        "drill": [], "pose": {"L01": "installed"},
        "move": [-1, 0, 0],
        "camera": {"azimuth": 35, "elevation": 30, "distance": 1.8, "target": "L04"},
        "text": [
            "Stand L01 on its back edge, inside face toward you.",
            "Drill L04's end at L01: two 3/8 in dowel holes 1 1/16 in deep and three 1/8 in pilots "
            "1 1/4 in deep, centred in the thickness (use the dowel jig).",
            GLUE_DOWELS,
        ],
        "warnings": ["Check the bottom is square to the side before the glue sets."],
        "hold": None, "requires": ["bookcase-drill"], "source": None,
    },
    {
        "id": "bookcase-plinth", "assembly": "bookcase",
        "title": "Fit the recessed plinth L05 under the bottom",
        "adds": ["L05"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 20, "elevation": 15, "distance": 1.6, "target": "L05"},
        "text": ["Set L05 under L04, 3/4 in back from the front edge."],
        "warnings": [],
        "hold": "plinth", "requires": ["bookcase-bottom"], "source": None,
    },
    {
        "id": "bookcase-shelf", "assembly": "bookcase",
        "title": "Fix the shelf above the drawer, L07, to L01",
        "adds": ["L07"], "joints": ["L07-L01"], "fasteners": {}, "consumables": ["glue"],
        "drill": [], "pose": {},
        "move": [-1, 0, 0],
        "camera": {"azimuth": 35, "elevation": 30, "distance": 1.9, "target": "L07"},
        "text": [
            "Drill L07's end at L01 as for the bottom.",
            "L07 is 1/4 in shallower than the sides: keep its front edge flush with the front.",
            GLUE_DOWELS,
        ],
        "warnings": [],
        "hold": None, "requires": ["bookcase-drill-shelf", "bookcase-bottom"], "source": None,
    },
    {
        "id": "bookcase-top", "assembly": "bookcase",
        "title": "Fix the top L03 to L01",
        "adds": ["L03"], "joints": ["L03-L01"], "fasteners": {}, "consumables": ["glue"],
        "drill": [], "pose": {},
        "move": [-1, 0, 0],
        "camera": {"azimuth": 35, "elevation": 40, "distance": 2.4, "target": "L03"},
        "text": [
            "Drill L03's end at L01 as for the bottom.",
            "Fit L03 flush with the top end of L01.",
            GLUE_DOWELS,
        ],
        "warnings": [],
        "hold": None, "requires": ["bookcase-bottom"], "source": None,
    },
    {
        "id": "bookcase-right-side", "assembly": "bookcase",
        "title": "Fit the outer end L02 over the bottom, shelf and top",
        "adds": [], "joints": ["L04-L02", "L07-L02", "L03-L02"], "fasteners": {}, "consumables": ["glue"],
        "drill": [], "pose": {"L02": "installed"},
        "move": [-1, 0, 0],
        "camera": {"azimuth": 50, "elevation": 30, "distance": 2.6, "target": "L02"},
        "text": [
            "Drill the free ends of L04, L07 and L03 as before.",
            "Glue all six dowels and the three panel ends, then lower L02 on together.",
            "Drive all nine screws snug, then check the case is square by measuring both diagonals.",
        ],
        "warnings": ["You need a helper to lower L02 onto all three panels at once."],
        "hold": None, "requires": ["bookcase-shelf", "bookcase-top"], "source": None,
    },
    {
        "id": "bookcase-back", "assembly": "bookcase",
        "title": "Fit the back L06",
        "adds": ["L06"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, 1, 0],
        "camera": {"azimuth": 210, "elevation": 25, "distance": 2.6, "target": "L06"},
        "text": ["Check the case is square, then fit L06 to the wall side."],
        "warnings": [],
        "hold": "back", "requires": ["bookcase-right-side"], "source": None,
    },
    {
        "id": "bookcase-drawer-box", "assembly": "bookcase",
        "title": "Build the drawer box L11 to L15",
        "adds": ["L11", "L12", "L13", "L14", "L15"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 30, "elevation": 35, "distance": 1.6, "target": "L15"},
        "text": ["Join the drawer sides L11 and L12 to the back L13 and inner front L14, "
                 "and support the bottom L15."],
        "warnings": [],
        "hold": "drawer-box", "requires": ["bookcase-right-side"], "source": None,
    },
    {
        "id": "bookcase-slides", "assembly": "bookcase",
        "title": "Fit the slides, the drawer box and the drawer face L16",
        "adds": ["L16"], "joints": [], "fasteners": {"screw-8x1-washer": 4}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 20, "elevation": 20, "distance": 1.8, "target": "L16"},
        "text": [
            "Fit the slides to the sides and the drawer box.",
            "Fix the face L16 from inside the box with four #8 x 1 in washer-head screws.",
        ],
        "warnings": [],
        "hold": "slide", "requires": ["bookcase-right-side"], "source": None,
    },
    {
        "id": "bookcase-drawer-pull", "assembly": "bookcase",
        "title": "Fit the drawer pull",
        "adds": [], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 15, "elevation": 15, "distance": 1.4, "target": "L16"},
        "text": ["Drill the pull holes through L16 and fix the pull."],
        "warnings": [],
        "hold": "pulls", "requires": ["bookcase-right-side"], "source": None,
    },
    {
        "id": "bookcase-shelves", "assembly": "bookcase",
        "title": "Drill the shelf-pin holes and set the shelves L08 to L10",
        "adds": ["L08", "L09", "L10"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 25, "elevation": 20, "distance": 2.6, "target": "L09"},
        "text": ["Drill the shelf-pin rows in both sides, then set the three adjustable shelves."],
        "warnings": ["Keep shelf-pin holes out of the joint bands."],
        "hold": "shelf-pins", "requires": ["bookcase-right-side"], "source": None,
    },
    {
        "id": "bookcase-place", "assembly": "bookcase",
        "title": "Place the bookcase beside the bed and restrain it to the wall",
        "adds": [], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 30, "elevation": 20, "distance": 4.0, "target": "L03"},
        "text": ["Stand the bookcase with L01 against the bed's left side M02 and fix it to the wall."],
        "warnings": ["A tall bookcase must be restrained before use."],
        "hold": "restraint", "requires": ["bookcase-right-side"], "source": None,
    },
]
