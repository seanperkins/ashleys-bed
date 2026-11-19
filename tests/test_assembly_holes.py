import dataclasses
import unittest

from tests import _paths  # noqa: F401
import assembly_parts as ap

BOOKCASE = ("L04-L01", "L04-L02", "L07-L01", "L07-L02", "L03-L01", "L03-L02")

class JointHoleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = ap.load_parts()

    def holes(self, joint_id):
        return ap.joint_holes(ap.JOINTS[joint_id], self.parts)

    def test_joint_ids(self):
        self.assertTrue(set(BOOKCASE) <= set(ap.JOINTS))
        self.assertEqual({j for j in ap.JOINTS if j.startswith("L")}, set(BOOKCASE))

    def test_joint_hole_set(self):
        for jid in BOOKCASE:
            joint = ap.JOINTS[jid]
            holes = self.holes(jid)
            side = [h for h in holes if h.part == joint.side]
            panel = [h for h in holes if h.part == joint.panel]
            self.assertEqual(len(holes), 10, jid)
            self.assertEqual(sorted((h.kind, h.surface, h.through, h.countersink) for h in side),
                             [("clearance", "face", True, True)] * 3 + [("dowel", "face", False, False)] * 2)
            self.assertEqual(sorted((h.kind, h.surface, h.through) for h in panel),
                             [("dowel", "edge", False)] * 2 + [("pilot", "edge", False)] * 3)

    def test_positions_from_front(self):
        holes = self.holes("L04-L01")
        side = [h for h in holes if h.part == "L01"]
        self.assertEqual([h.world[1] for h in side if h.kind == "dowel"], [12, 4])
        self.assertEqual([h.world[1] for h in side if h.kind == "clearance"], [14, 8, 2])
        for h in holes:
            self.assertAlmostEqual(h.world[2], 2.875)
            self.assertAlmostEqual(h.world[0], 87.5)
        self.assertEqual([h.u for h in side if h.kind == "dowel"], [4, 12])
        self.assertAlmostEqual(side[0].v, 2.875)
        self.assertEqual((side[0].ref_edge, side[0].ref_end), ("front edge", "bottom end"))
        panel = [h for h in holes if h.part == "L04"]
        self.assertEqual((panel[0].ref_edge, panel[0].ref_end), ("front edge", "end at L01"))
        self.assertEqual([h.u for h in panel if h.kind == "pilot"], [2, 8, 14])

    def test_depths(self):
        holes = self.holes("L04-L01")
        by = {(h.part, h.kind): h for h in holes}
        self.assertEqual(by[("L01", "dowel")].depth, 0.5)
        self.assertEqual(by[("L04", "dowel")].depth, 1.0625)
        self.assertEqual(by[("L04", "pilot")].depth, 1.25)
        self.assertEqual(by[("L04", "pilot")].diameter, 0.125)
        clearance = by[("L01", "clearance")]
        self.assertTrue(clearance.through)
        self.assertEqual(clearance.depth, 0.75)
        self.assertEqual(clearance.diameter, 0.1875)
        self.assertEqual(by[("L01", "dowel")].diameter, 0.375)
        self.assertEqual(by[("L01", "dowel")].axis, (-1, 0, 0))
        self.assertEqual(by[("L04", "dowel")].axis, (1, 0, 0))

    def test_mirror_sides(self):
        left, right = self.holes("L04-L01"), self.holes("L04-L02")
        self.assertEqual(len(left), len(right))
        for a, b in zip(left, right):
            self.assertAlmostEqual(a.world[0] + b.world[0], 2 * 101.75)
            self.assertEqual(a.world[1:], b.world[1:])
            self.assertEqual((a.kind, a.u), (b.kind, b.u))
            self.assertEqual(a.axis[0], -b.axis[0])
        self.assertEqual([h for h in right if h.part == "L04"][0].ref_end, "end at L02")

    def test_bands(self):
        holes = [h for jid in BOOKCASE for h in self.holes(jid)]
        self.assertEqual(ap.check_holes(holes, self.parts, set()), [])
        moved = dataclasses.replace(holes[0], world=(holes[0].world[0], holes[0].world[1], 4.0))
        errors = ap.check_holes([moved] + holes[1:], self.parts, set())
        self.assertTrue(any("outside joint band" in e for e in errors), errors)

    def test_wall_rule(self):
        holes = self.holes("L04-L01")
        face = next(h for h in holes if h.part == "L01" and h.kind == "dowel")
        self.assertEqual(ap.check_holes([face], self.parts, set()), [])
        deep = dataclasses.replace(face, depth=0.625)
        errors = ap.check_holes([deep], self.parts, set())
        self.assertTrue(any("less than 1/8 in" in e for e in errors), errors)
        edge = next(h for h in holes if h.part == "L04" and h.kind == "dowel")
        self.assertEqual(ap.check_holes([edge], self.parts, set()), [])
        self.assertAlmostEqual(ap.edge_wall(edge, self.parts["L04"]), 0.164)
        clearance = next(h for h in holes if h.kind == "clearance")
        self.assertEqual(ap.check_holes([dataclasses.replace(clearance, depth=5)], self.parts, set()), [])

    def test_spacing(self):
        face = next(h for h in self.holes("L04-L01") if h.part == "L01" and h.kind == "dowel")
        near = dataclasses.replace(face, world=(face.world[0], face.world[1] - 0.75, face.world[2]))
        errors = ap.check_holes([face, near], self.parts, set())
        self.assertTrue(any("closer than 1 in" in e for e in errors), errors)
        verified = [dataclasses.replace(h, verified="Rockler p. 12") for h in (face, near)]
        self.assertEqual(ap.check_holes(verified, self.parts, set()), [])
        self.assertEqual(ap.check_holes([face, near], self.parts, {"L04-L01"}), [])

    def test_hole_on_its_part(self):
        face = next(h for h in self.holes("L04-L01") if h.part == "L01" and h.kind == "dowel")
        off = dataclasses.replace(face, world=(90.0, face.world[1], face.world[2]))
        errors = ap.check_holes([off], self.parts, set())
        self.assertTrue(any("not on" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
