import copy
import unittest

from tests import _paths  # noqa: F401
import assembly_guide as ag
import assembly_parts as ap
import assembly_steps as st


class StageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = ap.load_parts()
        cls.fasteners = ap.load_fasteners()

    def test_part_stages(self):
        for pid, part in self.parts.items():
            if pid.startswith("L"):
                want = "bookcase"
            elif pid in {"M01", "M02", "M03", "M04", "M05", "M06"}:
                want = "bed-cabinet"
            else:
                want = "bed-mechanism"
            self.assertEqual(part.stage, want, pid)
        self.assertEqual(self.parts["M01"].assembly, "bed")

    def test_used_by_stage(self):
        used = lambda code: self.fasteners[code].used
        self.assertEqual(used("dowel"), {"bed-cabinet": 22, "bookcase": 12})
        self.assertEqual(used("screw-8x2"), {"bed-cabinet": 32, "bookcase": 18})
        self.assertEqual(used("T"), {"bed-cabinet": 16})
        self.assertEqual(used("BB"), {"bed-mechanism": 34})
        self.assertEqual(used("screw-8x1.25"), {"bed-mechanism": 4})
        self.assertEqual(used("screw-8x1-washer"), {"bookcase": 4})
        for code in ("U", "KK", "II", "JJ"):
            self.assertEqual(list(used(code)), ["bed-cabinet"], code)
        for code in ("V", "W", "Z", "AA", "DD", "EE", "FF", "OO"):
            self.assertEqual(list(used(code)), ["bed-mechanism"], code)

    def test_step_stage_key(self):
        steps = copy.deepcopy(st.STEPS)
        steps[0]["assembly"] = steps[0].pop("stage")
        errors = ag.validate(ag.resolve(steps, self.parts, self.fasteners), self.parts, self.fasteners)
        self.assertTrue(any("unknown key assembly" in e for e in errors), errors)
        self.assertTrue(any("missing key stage" in e for e in errors), errors)

    def test_active_stages(self):
        self.assertTrue(st.ACTIVE_STAGES <= {"bookcase", "bed-cabinet", "bed-mechanism"})
        self.assertFalse(hasattr(st, "ACTIVE_ASSEMBLIES"))

    def test_totals_by_stage(self):
        resolved = ag.resolve(st.STEPS, self.parts, self.fasteners)
        totals = ag.fastener_totals(resolved, self.parts)
        self.assertEqual(totals["dowel"].get("bookcase"), 12)


if __name__ == "__main__":
    unittest.main()
