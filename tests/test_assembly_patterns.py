import dataclasses
import unittest

from tests import _paths  # noqa: F401
import assembly_parts as ap

INSERTS = [(9 + 7 / 16, 11 + 7 / 16), (9 + 7 / 16, 17 + 11 / 16), (9 + 7 / 16, 25.25), (9 + 7 / 16, 27.75),
           (9 + 7 / 16, 30.25), (3.125, 11 + 7 / 16), (3.125, 13 + 7 / 8), (6 + 15 / 16, 17 + 11 / 16)]
ALIGNED = {(9 + 7 / 16, 17 + 11 / 16), (9 + 7 / 16, 25.25), (9 + 7 / 16, 27.75), (9 + 7 / 16, 30.25),
           (3.125, 11 + 7 / 16)}


class PatternTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = ap.load_parts()

    def holes(self, pid):
        return ap.pattern_holes(pid, self.parts)

    def test_insert_pattern(self):
        right, left = self.holes("inserts-M01"), self.holes("inserts-M02")
        self.assertEqual([(h.u, h.v) for h in right], INSERTS)
        self.assertEqual([(h.u, h.v) for h in left], INSERTS)
        for side, holes, x, axis in (("M01", right, 0.75, (-1, 0, 0)), ("M02", left, 86.0, (1, 0, 0))):
            for h in holes:
                self.assertEqual((h.part, h.surface, h.axis), (side, "face", axis))
                self.assertEqual((h.diameter, h.depth, h.through), (27 / 64, 9 / 16, False))
                self.assertAlmostEqual(ap.drilling_thickness(self.parts[side]) - h.depth, 0.1405)
                self.assertEqual(h.verified, "Rockler p. 8")
                self.assertEqual(h.located, "rockler")
                self.assertEqual((h.ref_edge, h.ref_end), ("front edge", "bottom end"))
                self.assertAlmostEqual(h.world[0], x)
                self.assertAlmostEqual(h.world[1], 16 - h.u)
                self.assertAlmostEqual(h.world[2], h.v)
            self.assertEqual({(h.u, h.v) for h in holes if h.aligned}, ALIGNED)

    def test_insert_checks(self):
        holes = self.holes("inserts-M01") + self.holes("inserts-M02")
        self.assertEqual(ap.check_holes(holes, self.parts, set()), [])
        low = dataclasses.replace(holes[0], v=0.2, world=(holes[0].world[0], holes[0].world[1], 0.2))
        errors = ap.check_holes([low] + holes[1:], self.parts, set())
        self.assertTrue(any("not on its face" in e for e in errors), errors)

    def test_lag_pattern(self):
        for pid, part, z, ref in (("lag-M05", "M05", 60.25, "top edge"), ("lag-M06", "M06", 3.75, "bottom edge")):
            holes = self.holes(pid)
            self.assertEqual(len(holes), 3, pid)
            for h, stud in zip(holes, ap.EXAMPLE_STUDS):
                self.assertEqual((h.part, h.through, h.diameter, h.located), (part, True, 0.1875, "stud"))
                self.assertIsNone(h.u)
                self.assertIsNone(h.world)
                self.assertEqual((h.v, h.ref_end), (3.0, ref))
                self.assertEqual(h.example, (stud, 0.75, z))
                self.assertEqual(h.axis, (0, -1, 0))
                self.assertEqual(h.verified, "Rockler p. 11")
        self.assertEqual(ap.PATTERNS["lag-M05"].hardware, [ap.Fixing("KK", "lag", "all")])

    def test_bracket_pattern(self):
        pattern = ap.PATTERNS["brackets-M03"]
        self.assertEqual(pattern.hold, "pilot-depth")
        holes = self.holes("brackets-M03")
        self.assertEqual(len(holes), 18)
        first = {h.name: h for h in holes[:6]}
        self.assertEqual(sorted(first), ["A1", "A2", "A3", "A4", "A5", "A6"])
        for name, v in (("A1", 4.625), ("A2", 4.0), ("A3", 2.75), ("A4", 1.5)):
            h = first[name]
            self.assertEqual((h.part, h.v, h.located, h.axis), ("M03", v, "stud", (0, 0, -1)))
            self.assertEqual(h.example, (ap.EXAMPLE_STUDS[0], v, 64.0))
        for name, diameter in (("A1", 13 / 64), ("A3", 0.125), ("A4", 0.125)):
            h = first[name]
            self.assertEqual((h.diameter, h.depth, h.through), (diameter, 0.5, False))
            self.assertAlmostEqual(ap.drilling_thickness(self.parts["M03"]) - h.depth, 0.203)
        self.assertEqual((first["A2"].diameter, first["A2"].through), (0.3125, True))
        wall = [h for h in holes if h.name in ("A5", "A6")]
        self.assertEqual(len(wall), 6)
        for h in wall:
            self.assertEqual((h.part, h.located, h.diameter), ("wall", "transfer", 0.1875))
            self.assertIsNone(h.world)
        self.assertEqual(first["A5"].example, (ap.EXAMPLE_STUDS[0], 0.0, 65.0))
        self.assertEqual(first["A6"].example, (ap.EXAMPLE_STUDS[0], 0.0, 66.5))
        self.assertEqual(len({h.example for h in wall}), 6)
        self.assertIn(ap.Fixing("II", "bolt", ("A2",)), pattern.hardware)
        self.assertIn(ap.Fixing("JJ", "screw", ("A3", "A4")), pattern.hardware)
        self.assertIn(ap.Fixing("KK", "lag", ("A5", "A6")), pattern.hardware)
        self.assertEqual(ap.check_holes(holes, self.parts, set()), [])

    def test_stud_holes_skip_spacing_and_position(self):
        holes = self.holes("brackets-M03")
        a1 = next(h for h in holes if h.name == "A1")
        a2 = next(h for h in holes if h.name == "A2")
        self.assertEqual(ap.check_holes([a1, a2, dataclasses.replace(a1, verified=None)], self.parts, set()), [])
        deep = dataclasses.replace(a1, depth=0.625)
        errors = ap.check_holes([deep], self.parts, set())
        self.assertTrue(any("less than 1/8 in" in e for e in errors), errors)

    def test_steel_shapes(self):
        for sid, side, face in (("I-R", "M01", 0.75), ("I-L", "M02", 86.0)):
            plate, wood = self.parts[sid], self.parts[side]
            self.assertEqual((plate.host, plate.finish, plate.stage), (side, "steel", "bed-cabinet"))
            self.assertTrue(plate.representative)
            self.assertEqual(len(plate.boxes), 3)
            for lo, hi in plate.boxes:
                self.assertAlmostEqual(min(abs(lo[0] - face), abs(hi[0] - face)), 0)
                self.assertAlmostEqual(hi[0] - lo[0], 0.1875)
                for k in (1, 2):
                    self.assertTrue(wood.min[k] <= lo[k] < hi[k] <= wood.max[k], (sid, k))
            self.assertFalse(wood.min[0] < (plate.min[0] + plate.max[0]) / 2 < wood.max[0])
        for n, stud in enumerate(ap.EXAMPLE_STUDS, 1):
            bracket = self.parts[f"HH-{n}"]
            self.assertEqual((bracket.host, bracket.finish), ("M03", "steel"))
            self.assertTrue(bracket.representative)
            self.assertAlmostEqual(bracket.min[2], 64.0)
            self.assertAlmostEqual(bracket.min[1], 0.0)
            self.assertAlmostEqual((bracket.min[0] + bracket.max[0]) / 2, stud)
        for pid, part in self.parts.items():
            if part.finish != "steel":
                self.assertEqual((part.host, part.boxes), (None, ((part.min, part.max),)), pid)

    def test_plate_covers_every_insert(self):
        for sid, pid in (("I-R", "inserts-M01"), ("I-L", "inserts-M02")):
            plate = self.parts[sid]
            for h in ap.pattern_holes(pid, self.parts):
                r = h.diameter / 2
                inside = [all(lo[k] <= h.world[k] - r and h.world[k] + r <= hi[k] for k in (1, 2))
                          for lo, hi in plate.boxes]
                self.assertTrue(any(inside), (sid, h.u, h.v))

    def test_steel_overlaps_no_wood(self):
        wood = [p for p in self.parts.values() if p.finish != "steel"]
        for steel in (p for p in self.parts.values() if p.finish == "steel"):
            for lo, hi in steel.boxes:
                for part in wood:
                    inside = all(lo[k] < part.max[k] - 1e-6 and part.min[k] + 1e-6 < hi[k] for k in range(3))
                    self.assertFalse(inside, (steel.id, part.id))


if __name__ == "__main__":
    unittest.main()
