import unittest

from tests import _paths  # noqa: F401
import assembly_parts as ap


class PartCatalogueTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = ap.load_parts()

    def test_all_27_parts_loaded(self):
        self.assertEqual(len(self.parts), 27)
        self.assertEqual(set(self.parts), {f"M{i:02d}" for i in range(1, 12)} | {f"L{i:02d}" for i in range(1, 17)})

    def test_name_mapping(self):
        self.assertEqual(ap.part_id_for("SC Left side"), "L01")
        self.assertEqual(ap.part_id_for("1R Right side | 3/4 x 16 x 64"), "M01")
        self.assertEqual(ap.part_id_for("3 Upper headboard — REQUIRED"), "M05")

    def test_boxes_match_geometry(self):
        l04 = self.parts["L04"]
        for got, want in zip(l04.min + l04.max, (87.5, 0, 2.5, 116, 16, 3.25)):
            self.assertAlmostEqual(got, want, delta=1e-6)

    def test_drilling_thickness(self):
        self.assertAlmostEqual(ap.drilling_thickness(self.parts["L04"]), 0.703)
        self.assertAlmostEqual(ap.drilling_thickness(self.parts["L11"]), 0.46875)
        self.assertAlmostEqual(ap.drilling_thickness(self.parts["L06"]), 0.21875)

    def test_drilling_thickness_follows_measured_stock(self):
        import unittest.mock as mock
        import generate_cut_layouts as gcl
        with mock.patch.object(gcl, "MEASURED_34", (0.69, 0.70)):
            self.assertAlmostEqual(ap.drilling_thickness(self.parts["L04"]), 0.69)

    def test_l01_is_next_to_bed(self):
        self.assertAlmostEqual(self.parts["L01"].min[0], self.parts["M02"].max[0])

    def test_finish(self):
        for pid in ("L11", "L12", "L13", "L14", "L15"):
            self.assertEqual(self.parts[pid].finish, "natural")
        self.assertEqual(self.parts["L04"].finish, "navy")
        self.assertEqual(self.parts["M01"].finish, "navy")

    def test_assembly(self):
        for pid, part in self.parts.items():
            self.assertEqual(part.assembly, "bed" if pid.startswith("M") else "bookcase")
            self.assertEqual(part.stage, ap.part_stage(pid))

    def test_stop_stock(self):
        self.assertEqual(self.parts["M07"].stock, 0.625)
        self.assertEqual(self.parts["L04"].label, "Left bookcase bottom")


if __name__ == "__main__":
    unittest.main()
