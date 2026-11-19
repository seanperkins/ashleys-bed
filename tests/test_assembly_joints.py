import dataclasses
import unittest

from tests import _paths  # noqa: F401
import assembly_parts as ap

BOOKCASE = ("L04-L01", "L04-L02", "L07-L01", "L07-L02", "L03-L01", "L03-L02")
BED = ("M03-M01", "M04-M01", "M05-M01", "M06-M01", "M03-M02", "M04-M02", "M05-M02", "M06-M02",
       "M05-M03", "M06-M04")


def phase1_holes(joint, parts):
    """Phase 1's bookcase rule, restated: contact along x, run along y from the front edge."""
    side, panel = parts[joint.side], parts[joint.panel]
    if abs(side.max[0] - panel.min[0]) < 1e-6:
        x, direction = side.max[0], 1
    else:
        x, direction = side.min[0], -1
    z, front = panel.centre[2], side.max[1]
    out = []
    for part, kind, distances, depth in ((side, "dowel", joint.dowels, 0.5), (side, "clearance", joint.screws, 0.75),
                                          (panel, "dowel", joint.dowels, 1.0625),
                                          (panel, "pilot", joint.screws, 1.25)):
        for d in distances:
            out.append(dict(part=part.id, kind=kind, world=(x, front - d, z), u=d, v=z - part.min[2], depth=depth,
                            axis=(-direction, 0, 0) if part is side else (direction, 0, 0),
                            ref_edge="front edge",
                            ref_end="bottom end" if part is side else f"end at {joint.side}"))
    return out


class JointGeometryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = ap.load_parts()

    def holes(self, jid):
        return ap.joint_holes(ap.JOINTS[jid], self.parts)

    def test_bookcase_unchanged(self):
        for jid in BOOKCASE:
            got = self.holes(jid)
            want = phase1_holes(ap.JOINTS[jid], self.parts)
            self.assertEqual(len(got), len(want), jid)
            for hole, ref in zip(got, want):
                for key, value in ref.items():
                    self.assertEqual(getattr(hole, key), value, f"{jid} {key}")
                self.assertEqual(hole.located, "rule")
                self.assertFalse(hole.aligned)

    def test_side_horizontal(self):
        holes = self.holes("M03-M01")
        side_dowels = [h for h in holes if h.part == "M01" and h.kind == "dowel"]
        self.assertEqual([h.world[1] for h in side_dowels], [12, 4])
        for h in side_dowels:
            self.assertAlmostEqual(h.world[2], 63.625)
            self.assertAlmostEqual(h.world[0], 0.75)
            self.assertEqual(h.axis, (-1, 0, 0))
        edge = [h for h in holes if h.part == "M03" and h.kind == "dowel"]
        self.assertTrue(edge and all(h.axis == (1, 0, 0) and h.surface == "edge" for h in edge))
        self.assertEqual(ap.joint_geometry(ap.JOINTS["M03-M01"], self.parts).datum_name, "front edge")

    def test_side_headboard(self):
        holes = self.holes("M05-M01")
        side = [h for h in holes if h.part == "M01"]
        self.assertEqual(sorted(h.world[2] for h in side if h.kind == "dowel"), [51.25, 59.25])
        self.assertEqual(sorted(h.world[2] for h in side if h.kind == "clearance"), [49.25, 55.25, 61.25])
        for h in holes:
            self.assertAlmostEqual(h.world[1], 0.375)
        self.assertEqual([h.u for h in side if h.kind == "clearance"], [2, 8, 14])
        self.assertAlmostEqual(side[0].v, 0.375)
        lower = [h for h in self.holes("M06-M01") if h.part == "M01" and h.kind == "clearance"]
        self.assertEqual(sorted(h.world[2] for h in lower), [2.75, 8.75, 14.75])
        geometry = ap.joint_geometry(ap.JOINTS["M05-M01"], self.parts)
        self.assertEqual(geometry.datum_name, "lower end")
        self.assertAlmostEqual(geometry.datum, 47.25)
        self.assertEqual((geometry.contact_axis, geometry.run_axis), (0, 2))

    def test_headboard_joint(self):
        joint = ap.JOINTS["M05-M03"]
        self.assertEqual((joint.side, joint.panel), ("M03", "M05"))
        geometry = ap.joint_geometry(joint, self.parts)
        self.assertEqual((geometry.contact_axis, geometry.run_axis), (2, 0))
        self.assertAlmostEqual(geometry.contact, 63.25)
        self.assertEqual(geometry.datum_name, "end at M01")
        holes = self.holes("M05-M03")
        run = 85.25
        face_dowels = [h for h in holes if h.part == "M03" and h.kind == "dowel"]
        for h, f in zip(face_dowels, (0.25, 0.5, 0.75)):
            self.assertAlmostEqual(h.world[0], 0.75 + run * f)
            self.assertEqual((h.axis, h.depth, h.surface), ((0, 0, 1), 0.5, "face"))
        clearances = [h for h in holes if h.part == "M03" and h.kind == "clearance"]
        for h, x in zip(clearances, (3.75, 0.75 + run / 3, 0.75 + 2 * run / 3, 83.0)):
            self.assertAlmostEqual(h.world[0], x)
            self.assertTrue(h.through and h.countersink)
        edge_dowels = [h for h in holes if h.part == "M05" and h.kind == "dowel"]
        self.assertEqual(len(edge_dowels), 3)
        for h in edge_dowels:
            self.assertEqual((h.axis, h.depth, h.surface), ((0, 0, -1), 1.0625, "edge"))
        for h in holes:
            self.assertAlmostEqual(h.world[1], 0.375)
            self.assertAlmostEqual(h.world[2], 63.25)
        self.assertEqual(len([h for h in holes if h.part == "M05" and h.kind == "pilot"]), 4)

    def test_bed_mirror(self):
        for panel in ("M03", "M04", "M05", "M06"):
            right, left = self.holes(f"{panel}-M01"), self.holes(f"{panel}-M02")
            self.assertEqual(len(right), len(left))
            for a, b in zip(right, left):
                self.assertAlmostEqual(a.world[0] + b.world[0], 2 * 43.375)
                self.assertEqual(a.world[1:], b.world[1:])
                self.assertEqual((a.kind, a.u, a.surface), (b.kind, b.u, b.surface))
                self.assertEqual(a.axis[0], -b.axis[0])

    def test_bed_checks_pass(self):
        holes = [h for jid in BED for h in self.holes(jid)]
        self.assertEqual(ap.check_holes(holes, self.parts, set()), [])

    def test_bed_counts(self):
        joints = [ap.JOINTS[j] for j in BED]
        self.assertEqual(sum(len(j.dowels) for j in joints), 22)
        self.assertEqual(sum(len(j.screws) for j in joints), 32)
        self.assertTrue(all(j.band is None for j in joints))

    def test_no_contact(self):
        apart = ap.Joint("M01-M02", "M01", "M02", [4], [2])
        with self.assertRaisesRegex(ValueError, "M01.*M02"):
            ap.joint_geometry(apart, self.parts)
        parts = dict(self.parts)
        # M03 moved so it meets M01 only along an edge (zero-width overlap in y).
        parts["M03"] = dataclasses.replace(self.parts["M03"], min=(0.75, 16.0, 63.25), max=(86.0, 32.0, 64.0))
        with self.assertRaisesRegex(ValueError, "M03.*M01|M01.*M03"):
            ap.joint_geometry(ap.JOINTS["M03-M01"], parts)
        # ...and only at a corner.
        parts["M03"] = dataclasses.replace(self.parts["M03"], min=(0.75, 16.0, 64.0), max=(86.0, 32.0, 65.0))
        with self.assertRaisesRegex(ValueError, "M03.*M01|M01.*M03"):
            ap.joint_geometry(ap.JOINTS["M03-M01"], parts)


if __name__ == "__main__":
    unittest.main()
