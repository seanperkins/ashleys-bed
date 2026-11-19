import struct
import unittest

from tests import _paths  # noqa: F401
import assembly_glb as glb
import assembly_guide as ag
import assembly_parts as ap
import assembly_steps as st

IN = 0.0254


class GlbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = ap.load_parts()
        cls.resolved = ag.resolve(st.STEPS, cls.parts, ap.load_fasteners())
        cls.data = glb.build_glb(cls.parts, cls.resolved)
        cls.doc = glb.read_glb(cls.data)
        cls.gltf = cls.doc["json"]
        cls.nodes = {n["name"]: n for n in cls.gltf["nodes"]}

    def mesh_bounds(self, name):
        mesh = self.gltf["meshes"][self.nodes[name]["mesh"]]
        acc = self.gltf["accessors"][mesh["primitives"][0]["attributes"]["POSITION"]]
        return acc["min"], acc["max"]

    def material(self, name):
        mesh = self.gltf["meshes"][self.nodes[name]["mesh"]]
        return self.gltf["materials"][mesh["primitives"][0]["material"]]["name"]

    def test_magic_and_chunks(self):
        magic, version, length = struct.unpack_from("<III", self.data)
        self.assertEqual((magic, version, length), (0x46546C67, 2, len(self.data)))
        json_len, json_type = struct.unpack_from("<II", self.data, 12)
        self.assertEqual(json_type, 0x4E4F534A)
        self.assertEqual(json_len % 4, 0)
        bin_len, bin_type = struct.unpack_from("<II", self.data, 20 + json_len)
        self.assertEqual(bin_type, 0x004E4942)
        self.assertEqual(bin_len % 4, 0)
        self.assertEqual(len(self.doc["bin"]), self.gltf["buffers"][0]["byteLength"])

    def test_node_names(self):
        names = set(self.nodes)
        self.assertTrue({p for p, part in self.parts.items() if part.stage not in st.PENDING_STAGES} <= names)
        dowels = [n for n in names if "-dowel-" in n]
        screws = [n for n in names if "-screw-" in n]
        self.assertEqual((len(dowels), len(screws)), (12, 18))
        self.assertIn("L04-L01-dowel-1", names)
        self.assertEqual(len(names), 22 + 5 + 30)  # wood less the five pending parts, steel, hardware
        self.assertEqual(sorted(self.gltf["scenes"][0]["nodes"]), list(range(57)))

    def test_pending_parts_omitted(self):
        for pid in ("M07", "M08", "M09", "M10", "M11"):
            self.assertNotIn(pid, self.nodes)
        for sid in ("I-R", "I-L", "HH-1", "HH-2", "HH-3"):
            self.assertIn(sid, self.nodes)
            self.assertEqual(self.material(sid), "context")  # bed-cabinet is not active yet
        lo, hi = self.mesh_bounds("HH-1")
        self.assertAlmostEqual(lo[1], 64 * IN, places=6)

    def test_axis_map(self):
        lo, hi = self.mesh_bounds("L04")
        for got, want in zip(lo + hi, (-116, 2.5, 0, -87.5, 3.25, 16)):
            self.assertAlmostEqual(got, want * IN, places=6)

    def test_materials(self):
        self.assertEqual(self.material("L11"), "natural")
        self.assertEqual(self.material("L04"), "navy")
        self.assertEqual(self.material("M01"), "context")
        self.assertEqual(self.material("L04-L01-dowel-1"), "hardware")

    def test_accessor_bounds_present(self):
        for mesh in self.gltf["meshes"]:
            acc = self.gltf["accessors"][mesh["primitives"][0]["attributes"]["POSITION"]]
            self.assertIn("min", acc)
            self.assertIn("max", acc)

    def test_hardware_in_joint(self):
        lo, hi = self.mesh_bounds("L04-L01-dowel-1")
        # dowel 1 sits 4 in from the front (y = 12) at z = 2.875, spanning the contact plane x = 87.5
        self.assertAlmostEqual((lo[2] + hi[2]) / 2, 12 * IN, places=5)
        self.assertAlmostEqual((lo[1] + hi[1]) / 2, 2.875 * IN, places=5)
        self.assertLess(lo[0], -87.5 * IN)
        self.assertGreater(hi[0], -87.5 * IN)
        self.assertAlmostEqual(hi[0] - lo[0], 1.5 * IN, places=5)

    def test_scene_matrix(self):
        m = glb.scene_matrix(st.pose_matrix(self.parts["L01"], "bench-1"))
        self.assertEqual(len(m), 16)
        lo, hi = self.mesh_bounds("L01")
        corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        moved = [[sum(m[c * 4 + r] * p[c] for c in range(3)) + m[12 + r] for r in range(3)] for p in corners]
        want_lo, want_hi = st.pose_box(self.parts["L01"], "bench-1")
        scene = lambda p: (-p[0] * IN, p[2] * IN, p[1] * IN)
        a, b = scene(want_lo), scene(want_hi)
        for axis in range(3):
            self.assertAlmostEqual(min(p[axis] for p in moved), min(a[axis], b[axis]), places=6)
            self.assertAlmostEqual(max(p[axis] for p in moved), max(a[axis], b[axis]), places=6)



class PatternMeshTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = ap.load_parts()

    def meshes(self, pid):
        return glb.pattern_meshes(ap.PATTERNS[pid], self.parts)

    @staticmethod
    def bounds(mesh):
        positions = mesh[0]
        return ([min(p[k] for p in positions) for k in range(3)], [max(p[k] for p in positions) for k in range(3)])

    def test_insert_at_hole(self):
        hole = ap.pattern_holes("inserts-M01", self.parts)[0]
        lo, hi = self.bounds(self.meshes("inserts-M01")["inserts-M01-T-1"])
        scene = glb.to_scene(hole.world)
        # centred on the hole in the face's plane (scene y = Fusion z, scene z = Fusion y)...
        self.assertAlmostEqual((lo[1] + hi[1]) / 2, scene[1], places=6)
        self.assertAlmostEqual((lo[2] + hi[2]) / 2, scene[2], places=6)
        # ...and sunk from the inside face (Fusion x = 0.75, scene x = -0.75 in) 9/16 into M01.
        self.assertAlmostEqual(hi[0], -0.75 * IN + 0.5625 * IN, places=6)
        self.assertAlmostEqual(lo[0], -0.75 * IN, places=6)
        self.assertAlmostEqual(hi[1] - lo[1], 0.42 * IN, places=3)

    def test_pattern_node_counts(self):
        count = lambda pid, code: len([n for n in self.meshes(pid) if n.startswith(f"{pid}-{code}-")])
        self.assertEqual((count("inserts-M01", "T"), count("inserts-M01", "U")), (8, 8))
        self.assertEqual(count("lag-M05", "KK"), 3)
        self.assertEqual((count("brackets-M03", "II"), count("brackets-M03", "JJ"), count("brackets-M03", "KK")),
                         (3, 6, 6))
        self.assertEqual(len(self.meshes("brackets-M03")), 15)
        self.assertIn("inserts-M01-U-8", self.meshes("inserts-M01"))

    def test_wall_lags_distinct(self):
        meshes = self.meshes("brackets-M03")
        centres = []
        for n in range(1, 7):
            lo, hi = self.bounds(meshes[f"brackets-M03-KK-{n}"])
            self.assertLess(lo[2], 0)  # scene z = Fusion y: the lag crosses the wall plane y = 0
            self.assertGreater(hi[2], 0)
            centres.append(tuple(round((a + b) / 2, 6) for a, b in zip(lo, hi)))
        self.assertEqual(len(set(centres)), 6)
        per_stud = {}
        for c in centres:
            per_stud.setdefault(round(-c[0] / IN, 3), []).append(c)
        self.assertEqual(sorted(per_stud), list(ap.EXAMPLE_STUDS))
        self.assertTrue(all(len(v) == 2 for v in per_stud.values()))

    def test_bolt_from_below(self):
        lo, hi = self.bounds(self.meshes("brackets-M03")["brackets-M03-II-1"])
        self.assertLess(lo[1], 63.25 * IN)  # head under the top
        self.assertGreater(hi[1], 64.1875 * IN)  # through the top and the bracket foot


if __name__ == "__main__":
    unittest.main()
