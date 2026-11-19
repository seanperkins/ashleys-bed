"""Hand-edited step data for the step-by-step assembly guide.

This is the one place to edit guide content. Parts are named by tape-label ID. `move` and poses
are in Fusion axes (x across, y from the wall to the room side, z up), inches.
To resolve an open decision, edit the joint/step data here and in assembly_parts.py and remove its
entry from OPEN_DECISIONS: the HOLD disappears.
"""

ACTIVE_STAGES = {"bookcase", "bed-cabinet"}
PENDING_STAGES = {"bed-mechanism"}  # left out of the GLB and drawings until their steps exist

BOOKCASE_OUTER_X = 116.75  # the outer face of L02
BENCH_OFFSETS = {"bench-1": 30.0, "bench-2": 50.0}
POSES = {
    "installed": "In place in the cabinet.",
    "bench-1": "Lying inside face up on the floor, 30 in beyond the bookcase's outer end.",
    "bench-2": "Lying inside face up on the floor, 50 in beyond the bookcase's outer end.",
}

# Midway between each cabinet's two sides: a side left of it has its inside face toward +x.
STAGE_CENTRE_X = {"bookcase": 101.75, "bed-cabinet": 43.375}


def _rotation(part):
    """Turn a side so its inside face points up and its length runs along y."""
    centre = STAGE_CENTRE_X.get(part.stage, STAGE_CENTRE_X["bookcase"])
    if part.centre[0] < centre:  # L01 / M01: inside face points +x
        return ((0, 1, 0), (0, 0, 1), (1, 0, 0))
    return ((0, -1, 0), (0, 0, 1), (-1, 0, 0))  # L02 / M02: inside face points -x


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


def pose_box(part, pose, host=None):
    """`part`'s box in `pose`; a steel shape or fixing passes its host, whose matrix it shares."""
    m = pose_matrix(host or part, pose)
    moved = [tuple(sum(m[i][k] * c[k] for k in range(3)) + m[i][3] for i in range(3)) for c in _corners(part)]
    return (tuple(min(c[i] for c in moved) for i in range(3)), tuple(max(c[i] for c in moved) for i in range(3)))


GLUE_DOWELS = "Glue in the dowels and the panel edge, fit the panel, then drive the screws snug, not tight."
TEST_DEPTH = "Set the depth stop and test every hole size on scrap first."
EDGE_JIG = ("centred in the thickness (use the dowel jig): 3/8 in dowel holes 1 1/16 in deep and 1/8 in "
            "pilots 1 1/4 in deep")
ANCHOR_WARNINGS = [
    "Wooden studs only: do not use drywall anchors, and do not fix into masonry or metal studs.",
    "Fix into at least three studs.",
    "Drive the lag bolts with a socket wrench, not an impact driver, and do not overtighten them.",
]

BED_STEPS = [
    {
        "id": "bed-drill-sides", "stage": "bed-cabinet",
        "title": "Check the parts, then drill the joint holes in both bed sides",
        "adds": ["M01", "M02"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [{"joint": f"{panel}-{side}", "part": side} for side in ("M01", "M02")
                  for panel in ("M03", "M04", "M05", "M06")],
        "fix": [],
        "pose": {"M01": "bench-1", "M02": "bench-2"},
        "move": [0, 0, -1],
        "camera": {"azimuth": 30, "elevation": 55, "target": "M02"},
        "text": [
            "Check every part against the cut list (tape label, length, width and thickness) before you "
            "drill anything.",
            "Lay both sides inside face up: the right side M01, at the bed's open end, and the left side M02, "
            "which stands against the bookcase.",
            "On each side, mark the four joint rows as dimensioned in the drawing: the top and bottom rows "
            "from the front edge, the two headboard rows up from each headboard's lower end, 3/8 in from the "
            "wall edge.",
            "Drill the 3/8 in dowel holes 1/2 in deep, then the 3/16 in screw holes right through.",
            "Turn each side over and countersink the screw holes on the outside face.",
        ],
        "warnings": [TEST_DEPTH],
        "hold": None, "requires": [], "source": "Rockler p. 10",
    },
    {
        "id": "bed-inserts", "stage": "bed-cabinet",
        "title": "Fit the threaded inserts T and the mounting plates I to both sides",
        "adds": ["I-R", "I-L"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [{"pattern": "inserts-M01"}, {"pattern": "inserts-M02"}],
        "fix": ["inserts-M01", "inserts-M02"],
        "pose": {},
        "move": [0, 0, -1],
        "camera": {"azimuth": 30, "elevation": 60, "target": "M01"},
        "text": [
            "On each side's inside face, mark the eight insert holes from the front edge and up from the "
            "bottom end, as dimensioned in the drawing. Both sides use the same layout.",
            "Five of the holes are placed by alignment on Rockler's drawing, not by a printed dimension: "
            "lay the plate on the marks and check every hole lines up before drilling.",
            "Drill each hole 27/64 in, 9/16 in deep, square to the face.",
            "Drive a threaded insert T into each hole until it sits flush with the face.",
            "Fix the mounting plate I-R to M01 and I-L to M02, each with eight M8 x 16 mm screws U, snug.",
        ],
        "warnings": [TEST_DEPTH,
                     "Fix the mounting plates only with the inserts and the M8 screws: never use wood screws."],
        "hold": None, "requires": ["bed-drill-sides"], "source": "Rockler pp. 7-8",
    },
    {
        "id": "bed-top-headboard", "stage": "bed-cabinet",
        "title": "Join the upper headboard M05 to the top M03",
        "adds": ["M03", "M05"], "joints": ["M05-M03"], "fasteners": {}, "consumables": ["glue"],
        "drill": [{"joint": "M05-M03", "part": "M03"}],
        "fix": [],
        "pose": {},
        "move": [0, 0, -1],
        "camera": {"azimuth": 20, "elevation": 35, "target": "M05"},
        "text": [
            "Lay the top M03 inside face up (the face that points down into the cabinet), wall edge toward you.",
            "Mark the headboard row 3/8 in from the wall edge, from the end at M01, as dimensioned in the "
            "drawing: three dowel holes and four screw holes.",
            "Drill the 3/8 in dowel holes 1/2 in deep and the 3/16 in screw holes right through, then turn "
            "M03 over and countersink the screw holes on its outside face (the top's upper face once installed).",
            f"Drill the upper headboard M05's top edge {EDGE_JIG}.",
            GLUE_DOWELS,
        ],
        "warnings": ["Keep M05's ends flush with M03's ends: both must fit between the sides."],
        "hold": None, "requires": [], "source": "Rockler p. 9",
    },
    {
        "id": "bed-bottom-headboard", "stage": "bed-cabinet",
        "title": "Join the lower headboard M06 to the bottom M04",
        "adds": ["M04", "M06"], "joints": ["M06-M04"], "fasteners": {}, "consumables": ["glue"],
        "drill": [{"joint": "M06-M04", "part": "M04"}],
        "fix": [],
        "pose": {},
        "move": [0, 0, 1],
        "camera": {"azimuth": 20, "elevation": 25, "target": "M06"},
        "text": [
            "Lay the bottom M04 inside face up (the face that points up into the cabinet), wall edge toward you.",
            "Mark the headboard row 3/8 in from the wall edge, from the end at M01, as dimensioned in the "
            "drawing: three dowel holes and four screw holes.",
            "Drill the 3/8 in dowel holes 1/2 in deep and the 3/16 in screw holes right through, then turn "
            "M04 over and countersink the screw holes on its outside face (the bottom's underside once "
            "installed).",
            f"Drill the lower headboard M06's bottom edge {EDGE_JIG}.",
            GLUE_DOWELS,
        ],
        "warnings": ["Keep M06's ends flush with M04's ends: both must fit between the sides."],
        "hold": None, "requires": [], "source": "Rockler p. 9",
    },
    {
        "id": "bed-right-side", "stage": "bed-cabinet",
        "title": "Fit the right side M01 to the top, bottom and both headboards",
        "adds": [], "joints": ["M03-M01", "M04-M01", "M05-M01", "M06-M01"], "fasteners": {},
        "consumables": ["glue"],
        "drill": [],
        "fix": [],
        "pose": {"M01": "installed"},
        "move": [1, 0, 0],
        "camera": {"azimuth": -45, "elevation": 30, "target": "M01"},
        "text": [
            "Set the top and bottom assemblies on their front edges on the floor, 64 in apart outside to "
            "outside, headboards up, as they sit in the cabinet.",
            f"Drill the M01 ends of M03, M04, M05 and M06 {EDGE_JIG}.",
            "Glue the eight dowels and the four panel ends, then push the right side M01 onto them from the end, plate side in.",
            "Drive all twelve screws snug, then check the cabinet is square by measuring both diagonals.",
        ],
        "warnings": ["You need a helper to hold M01 square while you push it onto all four panels at once."],
        "hold": None, "requires": ["bed-inserts", "bed-top-headboard", "bed-bottom-headboard"],
        "source": "Rockler p. 10",
    },
    {
        "id": "bed-left-side", "stage": "bed-cabinet",
        "title": "Fit the left side M02 to the other ends",
        "adds": [], "joints": ["M03-M02", "M04-M02", "M05-M02", "M06-M02"], "fasteners": {},
        "consumables": ["glue"],
        "drill": [],
        "fix": [],
        "pose": {"M02": "installed"},
        "move": [-1, 0, 0],
        "camera": {"azimuth": 45, "elevation": 30, "target": "M02"},
        "text": [
            f"Drill the M02 ends of M03, M04, M05 and M06 {EDGE_JIG}.",
            "Glue the eight dowels and the four panel ends, then push the left side M02 onto them from the end, plate side in.",
            "Drive all twelve screws snug, then check both diagonals again.",
        ],
        "warnings": ["You need a helper to hold M02 square while you push it onto all four panels at once."],
        "hold": None, "requires": ["bed-right-side"], "source": "Rockler p. 10",
    },
    {
        "id": "bed-stand-up", "stage": "bed-cabinet",
        "title": "Stand the cabinet against the wall and find the studs",
        "adds": [], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [],
        "fix": [],
        "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 20, "elevation": 20, "target": "M03"},
        "text": [
            "Stand the cabinet upright with its wall side against the wall where the bed will go.",
            "Plumb the front edges of both sides with a level, with shims under the bottom where the floor "
            "is uneven.",
            "Find the stud centres behind the cabinet with a stud finder and mark each stud line on the wall "
            "above the cabinet and down the headboards' front faces.",
        ],
        "warnings": ["Two adults are needed to stand the cabinet up: it is heavy and top-heavy.",
                     "The cabinet must be fixed to at least three studs; find them before you go on."],
        "hold": None, "requires": ["bed-left-side"], "source": "Rockler p. 11",
    },
    {
        "id": "bed-lag-bolts", "stage": "bed-cabinet",
        "title": "Fix the headboards to the studs with six lag bolts KK",
        "adds": [], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [{"pattern": "lag-M05"}, {"pattern": "lag-M06"}],
        "fix": ["lag-M05", "lag-M06"],
        "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 15, "elevation": 15, "target": "M05"},
        "text": [
            "On each stud line, mark one hole 3 in down from the top edge of the upper headboard M05 and one "
            "3 in up from the bottom edge of the lower headboard M06.",
            "Drill each hole 3/16 in through the headboard and on into the stud.",
            "Drive a 1/4 x 3 in lag bolt KK into each hole until its washer head is snug on the headboard.",
        ],
        "warnings": ANCHOR_WARNINGS,
        "hold": None, "requires": ["bed-stand-up"], "source": "Rockler p. 11",
    },
    {
        "id": "bed-wall-brackets", "stage": "bed-cabinet",
        "title": "Fit the three wall brackets HH on top of the cabinet",
        "adds": ["HH-1", "HH-2", "HH-3"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [{"pattern": "brackets-M03"}],
        "fix": ["brackets-M03"],
        "pose": {},
        "move": [0, 0, -1],
        "camera": {"azimuth": 20, "elevation": 50, "target": "M03"},
        "text": [
            "Set a wall bracket HH on the top M03 at each stud line, flush on the top and flush to the wall.",
            "Mark A1 to A4 on each stud line, measured from the wall as dimensioned in the drawing, and drill "
            "them. A1 takes the bracket's own steel dowel.",
            "Mark A5 and A6 through the bracket onto the wall and drill 3/16 in pilots into the stud.",
            "Fix each bracket with all six fasteners: the 1/4-20 Allen-head screw II up through A2 from "
            "inside the cabinet, two #12 x 3/4 in screws JJ in A3 and A4, and two lag bolts KK through A5 "
            "and A6 into the stud.",
        ],
        "warnings": ANCHOR_WARNINGS + [
            "Each bracket must sit flush on the top and flush to the wall before any fastener is driven."],
        "hold": "screw-tips", "requires": ["bed-lag-bolts"], "source": "Rockler p. 12",
    },
]

BOOKCASE_STEPS = [
    {
        "id": "bookcase-drill", "stage": "bookcase",
        "title": "Drill the bottom and top joint holes in both sides",
        "adds": ["L01", "L02"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [{"joint": "L04-L01", "part": "L01"}, {"joint": "L03-L01", "part": "L01"},
                  {"joint": "L04-L02", "part": "L02"}, {"joint": "L03-L02", "part": "L02"}],
        "pose": {"L01": "bench-1", "L02": "bench-2"},
        "move": [0, 0, -1],
        "camera": {"azimuth": 30, "elevation": 55, "target": "L02"},
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
        "id": "bookcase-drill-shelf", "stage": "bookcase",
        "title": "Drill the fixed-shelf joint holes in both sides",
        "adds": [], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [{"joint": "L07-L01", "part": "L01"}, {"joint": "L07-L02", "part": "L02"}],
        "pose": {},
        "move": [0, 0, -1],
        "camera": {"azimuth": 30, "elevation": 55, "target": "L02"},
        "text": [
            "On both sides, mark the fixed-shelf row 14 to 14 3/4 in up from the bottom end.",
            "Drill the dowel and screw holes as for the bottom and top rows.",
        ],
        "warnings": [TEST_DEPTH],
        "hold": None, "requires": ["bookcase-drill"], "source": None,
    },
    {
        "id": "bookcase-bottom", "stage": "bookcase",
        "title": "Fix the bottom L04 to the side against the bed, L01",
        "adds": ["L04"], "joints": ["L04-L01"], "fasteners": {}, "consumables": ["glue"],
        "drill": [], "pose": {"L01": "installed"},
        "move": [-1, 0, 0],
        "camera": {"azimuth": 35, "elevation": 30, "target": "L04"},
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
        "id": "bookcase-plinth", "stage": "bookcase",
        "title": "Fit the recessed plinth L05 under the bottom",
        "adds": ["L05"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 20, "elevation": 15, "target": "L05"},
        "text": ["Set L05 under L04, 3/4 in back from the front edge."],
        "warnings": [],
        "hold": "plinth", "requires": ["bookcase-bottom"], "source": None,
    },
    {
        "id": "bookcase-shelf", "stage": "bookcase",
        "title": "Fix the shelf above the drawer, L07, to L01",
        "adds": ["L07"], "joints": ["L07-L01"], "fasteners": {}, "consumables": ["glue"],
        "drill": [], "pose": {},
        "move": [-1, 0, 0],
        "camera": {"azimuth": 35, "elevation": 30, "target": "L07"},
        "text": [
            "Drill L07's end at L01 as for the bottom.",
            "L07 is 1/4 in shallower than the sides: keep its front edge flush with the front.",
            GLUE_DOWELS,
        ],
        "warnings": [],
        "hold": None, "requires": ["bookcase-drill-shelf", "bookcase-bottom"], "source": None,
    },
    {
        "id": "bookcase-top", "stage": "bookcase",
        "title": "Fix the top L03 to L01",
        "adds": ["L03"], "joints": ["L03-L01"], "fasteners": {}, "consumables": ["glue"],
        "drill": [], "pose": {},
        "move": [-1, 0, 0],
        "camera": {"azimuth": 35, "elevation": 40, "target": "L03"},
        "text": [
            "Drill L03's end at L01 as for the bottom.",
            "Fit L03 flush with the top end of L01.",
            GLUE_DOWELS,
        ],
        "warnings": [],
        "hold": None, "requires": ["bookcase-bottom"], "source": None,
    },
    {
        "id": "bookcase-right-side", "stage": "bookcase",
        "title": "Fit the outer end L02 over the bottom, shelf and top",
        "adds": [], "joints": ["L04-L02", "L07-L02", "L03-L02"], "fasteners": {}, "consumables": ["glue"],
        "drill": [], "pose": {"L02": "installed"},
        "move": [-1, 0, 0],
        "camera": {"azimuth": 50, "elevation": 30, "target": "L02"},
        "text": [
            "Drill the free ends of L04, L07 and L03 as before.",
            "Glue all six dowels and the three panel ends, then lower L02 on together.",
            "Drive all nine screws snug, then check the case is square by measuring both diagonals.",
        ],
        "warnings": ["You need a helper to lower L02 onto all three panels at once."],
        "hold": None, "requires": ["bookcase-shelf", "bookcase-top"], "source": None,
    },
    {
        "id": "bookcase-back", "stage": "bookcase",
        "title": "Fit the back L06",
        "adds": ["L06"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, 1, 0],
        "camera": {"azimuth": 210, "elevation": 25, "target": "L06"},
        "text": ["Check the case is square, then fit L06 to the wall side."],
        "warnings": [],
        "hold": "back", "requires": ["bookcase-right-side"], "source": None,
    },
    {
        "id": "bookcase-drawer-box", "stage": "bookcase",
        "title": "Build the drawer box L11 to L15",
        "adds": ["L11", "L12", "L13", "L14", "L15"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 30, "elevation": 35, "target": "L15"},
        "text": ["Join the drawer sides L11 and L12 to the back L13 and inner front L14, "
                 "and support the bottom L15."],
        "warnings": [],
        "hold": "drawer-box", "requires": ["bookcase-right-side"], "source": None,
    },
    {
        "id": "bookcase-slides", "stage": "bookcase",
        "title": "Fit the slides, the drawer box and the drawer face L16",
        "adds": ["L16"], "joints": [], "fasteners": {"screw-8x1-washer": 4}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 20, "elevation": 20, "target": "L16"},
        "text": [
            "Fit the slides to the sides and the drawer box.",
            "Fix the face L16 from inside the box with four #8 x 1 in washer-head screws.",
        ],
        "warnings": [],
        "hold": "slide", "requires": ["bookcase-right-side", "bookcase-drawer-box"], "source": None,
    },
    {
        "id": "bookcase-drawer-pull", "stage": "bookcase",
        "title": "Fit the drawer pull",
        "adds": [], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 15, "elevation": 15, "target": "L16"},
        "text": ["Drill the pull holes through L16 and fix the pull."],
        "warnings": [],
        "hold": "pulls", "requires": ["bookcase-right-side", "bookcase-slides"], "source": None,
    },
    {
        "id": "bookcase-shelves", "stage": "bookcase",
        "title": "Drill the shelf-pin holes and set the shelves L08 to L10",
        "adds": ["L08", "L09", "L10"], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 25, "elevation": 20, "target": "L09"},
        "text": ["Drill the shelf-pin rows in both sides, then set the three adjustable shelves."],
        "warnings": ["Keep shelf-pin holes out of the joint bands."],
        "hold": "shelf-pins", "requires": ["bookcase-right-side"], "source": None,
    },
    {
        "id": "bookcase-place", "stage": "bookcase",
        "title": "Place the bookcase beside the bed and restrain it to the wall",
        "adds": [], "joints": [], "fasteners": {}, "consumables": [],
        "drill": [], "pose": {},
        "move": [0, -1, 0],
        "camera": {"azimuth": 30, "elevation": 20, "target": "L03", "stages": ["bed-cabinet", "bookcase"]},
        "text": ["Stand the bookcase with L01 against the bed's left side M02 and fix it to the wall."],
        "warnings": ["A tall bookcase must be restrained before use."],
        "hold": "restraint", "requires": ["bookcase-right-side", "bed-wall-brackets"], "source": None,
    },
]

for _step in BOOKCASE_STEPS:
    _step.setdefault("fix", [])

STEPS = BED_STEPS + BOOKCASE_STEPS
