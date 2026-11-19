import copy
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tests import _paths  # noqa: F401
import assembly_glb as glb
import assembly_steps as st
import generate_assembly_guide as gen

DRILLING = ["bookcase-drill", "bookcase-drill-shelf", "bookcase-bottom", "bookcase-shelf", "bookcase-top",
            "bookcase-right-side"]


def bad_steps():
    steps = copy.deepcopy(st.STEPS)
    steps[0]["adds"] = ["L01", "L02", "Q99"]
    return steps


class GenerateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.out = self.root / "assembly-guide"

    def tearDown(self):
        self.tmp.cleanup()

    def siblings(self):
        return sorted(p.name for p in self.root.iterdir())

    def test_generates_all_files(self):
        summary = gen.generate(self.out)
        self.assertEqual(summary["steps"], 13)
        names = {p.name for p in self.out.iterdir()}
        self.assertEqual({n for n in names if n.endswith(".svg") and "holes" not in n},
                         {f"step-{i:02d}.svg" for i in range(1, 14)})
        steps = json.loads((self.out / "assembly-steps.json").read_text())
        self.assertEqual([s["id"] for s in steps], [s["id"] for s in st.STEPS])
        with_holes = [s["id"] for s in steps if s["holes_svg"]]
        self.assertEqual(with_holes, DRILLING)
        for s in steps:
            ET.parse(self.out / s["svg"])
            if s["holes_svg"]:
                ET.parse(self.out / s["holes_svg"])
        self.assertEqual(len([n for n in names if n.endswith("-holes.svg")]), 6)
        glb.read_glb((self.out / "assembly.glb").read_bytes())
        self.assertEqual(sorted(summary["files"]), sorted(names))

    def test_json_fields(self):
        gen.generate(self.out)
        steps = {s["id"]: s for s in json.loads((self.out / "assembly-steps.json").read_text())}
        bottom = steps["bookcase-bottom"]
        self.assertEqual(bottom["consumables"], ["glue"])
        self.assertEqual(bottom["hold"], [])
        self.assertEqual({h["code"]: (h["count"], h["phase"]) for h in bottom["hardware"]},
                         {"dowel": (2, "dowel"), "screw-8x2": (3, "screw")})
        self.assertEqual(bottom["hardware"][0]["name"], "3/8 x 1-1/2 in dowel")
        self.assertEqual(bottom["move"], [1, 0, 0])  # Fusion -x -> scene +x
        self.assertEqual(len(steps["bookcase-drill"]["poses"]["L01"]), 16)
        self.assertNotEqual(steps["bookcase-drill"]["poses"]["L02"], steps["bookcase-right-side"]["poses"]["L02"])
        self.assertEqual(steps["bookcase-right-side"]["poses"]["L02"],
                         [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
        self.assertIn("Back L06 attachment", steps["bookcase-back"]["hold"][0])
        self.assertEqual(steps["bookcase-back"]["held_by"], ["back", "slide"])
        self.assertIsNone(steps["bookcase-shelves"]["holes_svg"])

    def test_clean_checkout(self):
        self.assertFalse(self.out.exists())
        gen.generate(self.out)
        self.assertTrue((self.out / "assembly.glb").exists())
        self.assertEqual(self.siblings(), ["assembly-guide"])

    def test_stale_files_removed(self):
        self.out.mkdir()
        (self.out / "step-99.svg").write_text("<svg/>")
        gen.generate(self.out)
        self.assertFalse((self.out / "step-99.svg").exists())

    def test_failure_keeps_previous(self):
        gen.generate(self.out)
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        with self.assertRaisesRegex(ValueError, "Q99"):
            gen.generate(self.out, steps=bad_steps())
        self.assertEqual({p.name: p.read_bytes() for p in self.out.iterdir()}, before)
        self.assertEqual(self.siblings(), ["assembly-guide"])

    def test_leftover_staging_cleaned(self):
        self.out.mkdir()
        (self.root / "assembly-guide.staging-x").mkdir()
        (self.root / "assembly-guide.backup-x").mkdir()
        (self.root / "assembly-guide.backup-x" / "junk.txt").write_text("old")
        gen.generate(self.out)
        self.assertEqual(self.siblings(), ["assembly-guide"])

    def test_interrupted_swap_restored(self):
        backup = self.root / "assembly-guide.backup-x"
        backup.mkdir()
        (backup / "marker.txt").write_text("previous outputs")
        with self.assertRaises(ValueError):
            gen.generate(self.out, steps=bad_steps())
        self.assertEqual((self.out / "marker.txt").read_text(), "previous outputs")
        self.assertEqual(self.siblings(), ["assembly-guide"])
        gen.generate(self.out)
        self.assertFalse((self.out / "marker.txt").exists())

    def test_hold_count(self):
        summary = gen.generate(self.out)
        self.assertEqual(summary["holds"], 10)

    def test_cli_exit_codes(self):
        self.assertEqual(gen.main(["--out", str(self.out)]), 0)
        import unittest.mock as mock
        with mock.patch.object(gen.st, "STEPS", bad_steps()):
            self.assertEqual(gen.main(["--out", str(self.out)]), 1)


if __name__ == "__main__":
    unittest.main()
