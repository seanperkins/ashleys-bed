import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
import assembly_glb as glb
import assembly_guide as ag
import assembly_parts as ap
import assembly_steps as st
import generate_assembly_guide as gen

BED = ["bed-drill-sides", "bed-inserts", "bed-top-headboard", "bed-bottom-headboard", "bed-right-side",
       "bed-left-side", "bed-stand-up", "bed-lag-bolts", "bed-wall-brackets"]
BOOKCASE = ["bookcase-drill", "bookcase-drill-shelf", "bookcase-bottom", "bookcase-plinth", "bookcase-shelf",
            "bookcase-top", "bookcase-right-side", "bookcase-back", "bookcase-drawer-box", "bookcase-slides",
            "bookcase-drawer-pull", "bookcase-shelves", "bookcase-place"]
ANCHOR_WARNINGS = ("wooden studs", "drywall anchors", "masonry", "metal studs", "impact driver", "overtighten",
                   "three studs")


class BedStepTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = ap.load_parts()
        cls.fasteners = ap.load_fasteners()
        cls.resolved = ag.resolve(st.STEPS, cls.parts, cls.fasteners)
        cls.by_id = {rs.step["id"]: rs for rs in cls.resolved}
        cls.records = {r["id"]: r for r in gen.step_records(cls.resolved, cls.parts)}

    def words(self, sid):
        step = self.by_id[sid].step
        return " ".join(step["text"] + step["warnings"]).lower()

    def test_bed_step_order(self):
        self.assertEqual([s["id"] for s in st.STEPS], BED + BOOKCASE)
        self.assertEqual(st.ACTIVE_STAGES, {"bookcase", "bed-cabinet"})
        self.assertTrue(all(s["stage"] == "bed-cabinet" for s in st.STEPS[:9]))

    def test_bed_completeness(self):
        added = [p for s in st.STEPS if s["stage"] == "bed-cabinet" for p in s["adds"]]
        self.assertEqual(sorted(added), sorted(["M01", "M02", "M03", "M04", "M05", "M06", "I-R", "I-L",
                                                "HH-1", "HH-2", "HH-3"]))
        self.assertFalse({"M07", "M08", "M09", "M10", "M11"} & {p for s in st.STEPS for p in s["adds"]})
        self.assertEqual(ag.validate(self.resolved, self.parts, self.fasteners), [])

    def test_stage_totals(self):
        totals = ag.fastener_totals(self.resolved, self.parts)
        cabinet = {code: per.get("bed-cabinet", 0) for code, per in totals.items()}
        self.assertEqual({c: n for c, n in cabinet.items() if n},
                         {"dowel": 22, "screw-8x2": 32, "T": 16, "U": 16, "KK": 12, "II": 3, "JJ": 6})

    def test_bed_drilling(self):
        drill = self.by_id["bed-drill-sides"]
        self.assertEqual({h.part for h in drill.drilled}, {"M01", "M02"})
        self.assertEqual(len(drill.drilled), 8 * 5)
        inserts = self.by_id["bed-inserts"]
        self.assertEqual(len(inserts.drilled), 16)
        for sid, part in (("bed-right-side", "M01"), ("bed-left-side", "M02")):
            joined = self.by_id[sid].joined
            self.assertTrue(joined and all(h.part in {"M03", "M04", "M05", "M06"} for h in joined), sid)
        self.assertEqual({h.part for h in self.by_id["bed-top-headboard"].drilled}, {"M03"})
        self.assertEqual({h.part for h in self.by_id["bed-top-headboard"].joined}, {"M05"})
        self.assertEqual(len(self.by_id["bed-wall-brackets"].drilled), 18)

    def test_host_poses(self):
        for sid, want in (("bed-inserts", "bench-1"), ("bed-right-side", "installed")):
            rs = self.by_id[sid]
            hosted = [n for n, host in rs.hosts.items() if host == "M01"]
            self.assertIn("I-R", hosted)
            self.assertEqual(len([n for n in hosted if n.startswith("inserts-M01-")]), 16)
            for node in hosted:
                self.assertEqual(rs.poses[node], want, (sid, node))
                self.assertEqual(self.records[sid]["poses"][node], self.records[sid]["poses"]["M01"], (sid, node))
        for sid in BED[:5]:
            self.assertEqual(self.by_id[sid].poses["M02"], "bench-2", sid)
            self.assertEqual(self.by_id[sid].poses["I-L"] if "I-L" in self.by_id[sid].poses else "bench-2",
                             "bench-2", sid)
        for sid in BED[5:]:
            self.assertEqual(self.by_id[sid].poses["M02"], "installed", sid)
            self.assertEqual(self.by_id[sid].poses["inserts-M02-U-8"], "installed", sid)
        self.assertEqual(self.by_id["bed-right-side"].hosts["M03-M01-dowel-1"], "M01")
        self.assertEqual(self.by_id["bed-wall-brackets"].hosts["HH-2"], "M03")

    def test_bench_inside_face_up(self):
        for pid, pose in (("M01", "bench-1"), ("M02", "bench-2")):
            m = st.pose_matrix(self.parts[pid], pose)
            hole = ap.pattern_holes(f"inserts-{pid}", self.parts)[0]
            axis = [sum(m[r][c] * hole.axis[c] for c in range(3)) for r in range(3)]
            self.assertEqual([round(v) for v in axis], [0, 0, -1], pid)
        a = st.pose_box(self.parts["M01"], "bench-1")
        b = st.pose_box(self.parts["M02"], "bench-2")
        self.assertFalse(all(a[0][i] < b[1][i] and b[0][i] < a[1][i] for i in range(3)))
        plate = st.pose_box(self.parts["I-R"], "bench-1", self.parts["M01"])
        self.assertAlmostEqual(plate[0][2], a[1][2])  # the plate lies on top of the side on the bench

    def test_bed_holds(self):
        held = [sid for sid in BED if self.by_id[sid].held_by]
        self.assertEqual(held, ["bed-wall-brackets"])
        self.assertEqual(sorted(self.by_id["bed-wall-brackets"].held_by), ["pilot-depth", "screw-tips"])
        self.assertEqual(sum(1 for rs in self.resolved if rs.held_by), 11)

    def test_place_requires_anchoring(self):
        place = next(s for s in st.STEPS if s["id"] == "bookcase-place")
        self.assertIn("bed-wall-brackets", place["requires"])
        decisions = copy.deepcopy(ap.OPEN_DECISIONS)
        del decisions["restraint"]
        del decisions["slide"]
        resolved = {rs.step["id"]: rs for rs in
                    ag.resolve(st.STEPS, self.parts, self.fasteners, decisions=decisions)}
        self.assertIn("pilot-depth", resolved["bookcase-place"].held_by)

    def test_bed_sources(self):
        for sid in BED:
            self.assertTrue(self.by_id[sid].step["source"], sid)
            self.assertTrue(self.by_id[sid].step["source"].startswith("Rockler p"), sid)

    def test_safety_warnings(self):
        self.assertIn("wood screws", self.words("bed-inserts"))
        stand = self.words("bed-stand-up")
        for text in ("two adults", "plumb", "shims"):
            self.assertIn(text, stand)
        for sid in ("bed-lag-bolts", "bed-wall-brackets"):
            for text in ANCHOR_WARNINGS:
                self.assertIn(text, self.words(sid), (sid, text))
        brackets = self.words("bed-wall-brackets")
        for text in ("flush", "all six fasteners", "a5", "a6", "through the bracket"):
            self.assertIn(text, brackets)

    def test_aligned_note(self):
        text = self.words("bed-inserts")
        self.assertIn("lay the plate on the marks", text)
        self.assertIn("every hole lines up", text)

    def test_cut_list_check(self):
        self.assertIn("cut list", self.words("bed-drill-sides"))

    def test_hardware_poses_in_json(self):
        poses = self.records["bed-inserts"]["poses"]
        self.assertEqual(poses["inserts-M01-T-1"], poses["M01"])
        self.assertNotEqual(poses["inserts-M01-T-1"], poses["inserts-M02-T-1"])

    def test_hardware_axes(self):
        items = {h["code"]: h for h in self.records["bed-inserts"]["hardware"]}
        self.assertIsNone(items["T"]["axis"])  # M01's inserts and M02's face opposite ways
        self.assertEqual(len(items["T"]["axes"]), 16)
        self.assertEqual(items["T"]["axes"][0], list(glb._normal_to_scene((-1, 0, 0))))
        lags = {h["code"]: h for h in self.records["bed-lag-bolts"]["hardware"]}
        self.assertEqual(lags["KK"]["axis"], list(glb._normal_to_scene((0, -1, 0))))

    def test_records_carry_stage(self):
        # the viewer frames only the current step's stage, so bookcase steps don't zoom out to the bed
        for sid, record in self.records.items():
            self.assertEqual(record["stage"], self.by_id[sid].step["stage"], sid)

    def test_place_frames_both_cabinets(self):
        # the bookcase is placed beside the bed, so that step frames both; the others frame their own stage
        self.assertEqual(sorted(self.records["bookcase-place"]["camera"]["stages"]), ["bed-cabinet", "bookcase"])
        self.assertNotIn("stages", self.records["bookcase-top"]["camera"])

    def test_countersink_face(self):
        for sid, part in (("bed-top-headboard", "m03"), ("bed-bottom-headboard", "m04")):
            text = self.words(sid)
            self.assertIn(f"turn {part} over", text, sid)
            self.assertIn("countersink the screw holes on its outside face", text, sid)

    def test_generates(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "guide"
            summary = gen.generate(out)
            self.assertEqual((summary["steps"], summary["holds"]), (22, 11))
            records = json.loads((out / "assembly-steps.json").read_text())
            nodes = {n["name"] for n in glb.read_glb((out / "assembly.glb").read_bytes())["json"]["nodes"]}
            for name in ("inserts-M01-T-1", "brackets-M03-KK-6", "lag-M06-KK-3", "M05-M03-screw-4", "HH-3"):
                self.assertIn(name, nodes)
            self.assertEqual(len(records), 22)


if __name__ == "__main__":
    unittest.main()
