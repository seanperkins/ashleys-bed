import copy
import dataclasses
import unittest

from tests import _paths  # noqa: F401
import assembly_parts as ap


class FastenerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fasteners = ap.load_fasteners()

    def bookcase_totals(self, **changes):
        totals = {"dowel": {"bookcase": 12}, "screw-8x2": {"bookcase": 18},
                  "screw-8x1-washer": {"bookcase": 4}}
        for code, count in changes.items():
            totals[code.replace("_", "-")] = {"bookcase": count}
        return totals

    def test_kit_codes_loaded(self):
        for code in ("T", "U", "V", "W", "Z", "AA", "BB", "DD", "EE", "FF", "II", "JJ", "KK", "OO"):
            self.assertEqual(self.fasteners[code].source, "kit", code)
        self.assertEqual(self.fasteners["KK"].supplied, 12)
        self.assertEqual(self.fasteners["OO"].supplied, 0)
        self.assertEqual(self.fasteners["OO"].used, {"bed-mechanism": 4})
        self.assertEqual(self.fasteners["W"].used, {"bed-mechanism": 88})
        self.assertNotIn("A1", self.fasteners)

    def test_bought_codes(self):
        expected = {"dowel": 50, "screw-8x2": 100, "screw-8x1.25": 25, "screw-8x1-washer": 25}
        for code, bought in expected.items():
            self.assertEqual(self.fasteners[code].bought, bought, code)
            self.assertEqual(self.fasteners[code].source, "bought")

    def test_used_bookcase(self):
        self.assertEqual(self.fasteners["dowel"].used, {"bed-cabinet": 22, "bookcase": 12})
        self.assertEqual(self.fasteners["screw-8x2"].used, {"bed-cabinet": 32, "bookcase": 18})
        self.assertEqual(self.fasteners["screw-6x1.25"].used, {})

    def test_check_passes_bookcase(self):
        self.assertEqual(ap.check_fasteners(self.bookcase_totals(), self.fasteners, {"bookcase"}), [])

    def test_check_fails_mismatch(self):
        errors = ap.check_fasteners(self.bookcase_totals(dowel=10), self.fasteners, {"bookcase"})
        self.assertTrue(any("dowel" in e for e in errors), errors)

    def test_unknown_code(self):
        totals = self.bookcase_totals()
        totals["screw-9x9"] = {"bookcase": 1}
        errors = ap.check_fasteners(totals, self.fasteners, {"bookcase"})
        self.assertTrue(any("screw-9x9" in e for e in errors), errors)

    def test_used_exceeds_supply(self):
        fasteners = dict(self.fasteners)
        fasteners["screw-pull"] = dataclasses.replace(fasteners["screw-pull"], used={"bookcase": 8}, supplied=0)
        totals = self.bookcase_totals()
        totals["screw-pull"] = {"bookcase": 8}
        errors = ap.check_fasteners(totals, fasteners, {"bookcase"})
        self.assertTrue(any("screw-pull" in e and "exceeds" in e for e in errors), errors)

    def test_unknown_supply_with_use(self):
        fasteners = dict(self.fasteners)
        fasteners["screw-slide"] = dataclasses.replace(fasteners["screw-slide"], used={"bookcase": 12})
        totals = self.bookcase_totals()
        totals["screw-slide"] = {"bookcase": 12}
        errors = ap.check_fasteners(totals, fasteners, {"bookcase"})
        self.assertTrue(any("screw-slide" in e and "unknown" in e for e in errors), errors)

    def test_w_banner_conditional(self):
        banner = ap.discrepancy_holds()["W"]
        for text in ("88", "56", "possible shortage of 32", "confirm with Rockler"):
            self.assertIn(text, banner)
        self.assertNotIn("buy 32", banner)

    def test_w_banner_after_confirm(self):
        table = copy.deepcopy(ap.DISCREPANCIES)
        table["W"]["recorded"].append("confirmed-supply-56")
        self.assertIn("buy 32", ap.discrepancy_holds(table)["W"])
        table["W"]["recorded"].append("on-hand-88")
        self.assertNotIn("W", ap.discrepancy_holds(table))

    def test_bb_needs_length(self):
        table = copy.deepcopy(ap.DISCREPANCIES)
        table["BB"]["recorded"].append("on-hand-34")
        self.assertIn("BB", ap.discrepancy_holds(table))
        table["BB"]["recorded"].append("length-confirmed")
        self.assertNotIn("BB", ap.discrepancy_holds(table))

    def test_bundled_hold_entries(self):
        for code in ("screw-slide", "screw-pull", "restraint-fasteners"):
            entry = self.fasteners[code]
            self.assertEqual((entry.source, entry.used, entry.bought), ("bundled", {}, 0), code)
        self.assertIsNone(self.fasteners["screw-slide"].supplied)

    def test_consumables(self):
        self.assertEqual(set(ap.CONSUMABLES), {"glue", "threadlocker"})
        self.assertNotIn("glue", self.fasteners)

    def test_current_bom_loads(self):
        self.assertIn("screw-6x0.75", self.fasteners)

    def test_unmapped_bom_row_rejected(self):
        import tempfile
        from pathlib import Path
        bom = ap.BOM.read_text(encoding="utf-8-sig")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bom.csv"
            path.write_text(bom + "Fasteners and adhesives,Mystery bolts,5,bolts,,,,,\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Mystery bolts"):
                ap.load_fasteners(bom=path)


if __name__ == "__main__":
    unittest.main()
