import math
import unittest
import xml.etree.ElementTree as ET

from tests import _paths  # noqa: F401
import assembly_drawings as dr
import assembly_guide as ag
import assembly_parts as ap
import assembly_steps as st

NS = "{http://www.w3.org/2000/svg}"


class DrawingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = ap.load_parts()
        cls.resolved = ag.resolve(st.STEPS, cls.parts, ap.load_fasteners())
        cls.index = {rs.step["id"]: i for i, rs in enumerate(cls.resolved)}
        cls.svgs = {rs.step["id"]: dr.step_svg(i, cls.resolved, cls.parts) for i, rs in enumerate(cls.resolved)}
        cls.holes = {rs.step["id"]: dr.holes_svg(rs, cls.parts) for rs in cls.resolved}

    def groups(self, sid):
        root = ET.fromstring(self.svgs[sid])
        return [g for g in root.iter(NS + "g") if g.get("data-part")]

    def test_svg_parses(self):
        for sid, text in self.svgs.items():
            self.assertEqual(ET.fromstring(text).tag, NS + "svg", sid)
        for sid, text in self.holes.items():
            if text is not None:
                self.assertEqual(ET.fromstring(text).tag, NS + "svg", sid)

    def test_contains_new_part_ids(self):
        for rs in self.resolved:
            for pid in rs.step["adds"]:
                self.assertIn(f">{pid}<", self.svgs[rs.step["id"]], (rs.step["id"], pid))

    def test_classes(self):
        classes = {g.get("data-part"): g.get("class").split() for g in self.groups("bookcase-top")}
        self.assertIn("done", classes["L04"])
        self.assertIn("new", classes["L03"])
        self.assertNotIn("L06", classes)  # later parts are not drawn
        self.assertNotIn("M01", classes)  # the bed is not drawn in bookcase steps

    def test_hardware_panel(self):
        svg = self.svgs["bookcase-bottom"]
        self.assertIn("×2", svg)
        self.assertIn("×3", svg)
        self.assertIn("3/8 x 1-1/2 in dowel", svg)
        self.assertIn("#8 x 2 in screw", svg)
        self.assertIn("Wood glue", svg)

    def test_hole_closeup(self):
        svg = self.holes["bookcase-drill"]
        for text in ('4"', '12"', "Ø3/8 × 1/2 deep", "Ø3/16 through, countersink",
                     "keep shelf-pin rows and slide screws out", "L01", "L02", '2 7/8"'):
            self.assertIn(text, svg)

    def test_joint_step_closeup(self):
        svg = self.holes["bookcase-top"]
        self.assertIn("Ø3/8 × 1 1/16 deep", svg)
        self.assertIn("Ø1/8 × 1 1/4 deep", svg)
        self.assertIn("L03", svg)

    def test_no_holes_svg(self):
        self.assertIsNone(self.holes["bookcase-shelves"])
        drilling = sorted(sid for sid, text in self.holes.items() if text is not None)
        self.assertEqual(drilling, sorted(["bookcase-drill", "bookcase-drill-shelf", "bookcase-bottom",
                                           "bookcase-shelf", "bookcase-top", "bookcase-right-side",
                                           "bed-drill-sides", "bed-inserts", "bed-top-headboard",
                                           "bed-bottom-headboard", "bed-right-side", "bed-left-side",
                                           "bed-lag-bolts", "bed-wall-brackets"]))

    def test_hold_banner(self):
        svg = self.svgs["bookcase-back"]
        self.assertIn("HOLD", svg)
        self.assertIn("Back L06 attachment not decided", svg)
        self.assertNotIn("HOLD", self.svgs["bookcase-bottom"])

    def test_depth_order(self):
        d = (-1 / math.sqrt(3),) * 3
        order = [g.get("data-part") for g in self.groups("bookcase-right-side")]
        rs = self.resolved[self.index["bookcase-right-side"]]
        depth = []
        for pid in order:
            lo, hi = dr.drawn_box(self.parts[pid], rs, pid)
            depth.append(sum((lo[k] + hi[k]) / 2 * d[k] for k in range(3)))
        self.assertEqual(depth, sorted(depth, reverse=True))
        self.assertEqual(len(order), 6)


if __name__ == "__main__":
    unittest.main()
