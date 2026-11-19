import copy
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401
import assembly_guide as ag
import assembly_parts as ap
import assembly_steps as st

ORDER = ["bookcase-drill", "bookcase-drill-shelf", "bookcase-bottom", "bookcase-plinth", "bookcase-shelf",
         "bookcase-top", "bookcase-right-side", "bookcase-back", "bookcase-drawer-box", "bookcase-slides",
         "bookcase-drawer-pull", "bookcase-shelves", "bookcase-place"]
AFTER_RIGHT_SIDE = ["bookcase-back", "bookcase-drawer-box", "bookcase-slides", "bookcase-drawer-pull",
                    "bookcase-shelves", "bookcase-place"]


class StepTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts = ap.load_parts()
        cls.fasteners = ap.load_fasteners()
        cls.resolved = ag.resolve(st.STEPS, cls.parts, cls.fasteners)
        cls.by_id = {rs.step["id"]: rs for rs in cls.resolved}

    def errors_for(self, steps):
        return ag.validate(ag.resolve(steps, self.parts, self.fasteners), self.parts, self.fasteners)

    def test_bookcase_step_order(self):
        self.assertEqual([s["id"] for s in st.STEPS], ORDER)
        self.assertEqual(st.ACTIVE_STAGES, {"bookcase"})

    def test_completeness_active_only(self):
        added = [p for s in st.STEPS for p in s["adds"]]
        self.assertEqual(sorted(added), [f"L{i:02d}" for i in range(1, 17)])
        self.assertEqual(ag.validate(self.resolved, self.parts, self.fasteners), [])

    def test_step_joints(self):
        drills = lambda sid: sorted((d["joint"], d["part"]) for d in self.by_id[sid].step["drill"])
        self.assertEqual(drills("bookcase-drill"), [("L03-L01", "L01"), ("L03-L02", "L02"),
                                                    ("L04-L01", "L01"), ("L04-L02", "L02")])
        self.assertEqual(drills("bookcase-drill-shelf"), [("L07-L01", "L01"), ("L07-L02", "L02")])
        joins = lambda sid: self.by_id[sid].step["joints"]
        self.assertEqual(joins("bookcase-bottom"), ["L04-L01"])
        self.assertEqual(joins("bookcase-shelf"), ["L07-L01"])
        self.assertEqual(joins("bookcase-top"), ["L03-L01"])
        self.assertEqual(joins("bookcase-right-side"), ["L04-L02", "L07-L02", "L03-L02"])
        drill = self.by_id["bookcase-drill"]
        self.assertEqual(len(drill.drilled), 20)
        self.assertTrue(all(h.surface == "face" for h in drill.drilled))
        bottom = self.by_id["bookcase-bottom"]
        self.assertEqual(sorted({h.part for h in bottom.joined}), ["L04"])
        self.assertEqual(len(bottom.joined), 5)

    def test_bench_poses(self):
        pose = lambda sid, pid: self.by_id[sid].poses[pid]
        for sid in ("bookcase-drill", "bookcase-drill-shelf"):
            self.assertEqual(pose(sid, "L01"), "bench-1")
        for sid in ORDER[2:]:
            self.assertEqual(pose(sid, "L01"), "installed")
        for sid in ORDER[:6]:
            self.assertEqual(pose(sid, "L02"), "bench-2")
        for sid in ORDER[6:]:
            self.assertEqual(pose(sid, "L02"), "installed")
        a = st.pose_box(self.parts["L01"], "bench-1")
        b = st.pose_box(self.parts["L02"], "bench-2")
        overlap = all(a[0][i] < b[1][i] and b[0][i] < a[1][i] for i in range(3))
        self.assertFalse(overlap)
        self.assertAlmostEqual(a[0][2], 0)
        self.assertAlmostEqual(a[1][2] - a[0][2], 0.75)
        self.assertGreater(a[0][0], 116.75)

    def test_bench_inside_face_up(self):
        for pid, pose in (("L01", "bench-1"), ("L02", "bench-2")):
            m = st.pose_matrix(self.parts[pid], pose)
            hole = next(h for h in ap.joint_holes(ap.JOINTS[f"L04-{pid}"], self.parts) if h.part == pid)
            axis = [sum(m[r][c] * hole.axis[c] for c in range(3)) for r in range(3)]
            self.assertEqual([round(v) for v in axis], [0, 0, -1], pid)  # drilled straight down

    def test_holds(self):
        ready = [rs.step["id"] for rs in self.resolved if not rs.held_by]
        self.assertEqual(ready, ["bookcase-drill", "bookcase-bottom", "bookcase-top"])
        for sid in ("bookcase-drill-shelf", "bookcase-shelf", "bookcase-right-side", "bookcase-slides"):
            self.assertIn("slide", self.by_id[sid].held_by, sid)
        for sid, decision in (("bookcase-plinth", "plinth"), ("bookcase-back", "back"),
                              ("bookcase-drawer-box", "drawer-box"), ("bookcase-drawer-pull", "pulls"),
                              ("bookcase-shelves", "shelf-pins"), ("bookcase-place", "restraint")):
            self.assertIn(decision, self.by_id[sid].held_by, sid)
        self.assertEqual(sum(1 for rs in self.resolved if rs.held_by), 10)

    def test_open_decisions(self):
        self.assertEqual(set(ap.OPEN_DECISIONS), {"back", "slide", "shelf-pins", "restraint", "plinth",
                                                  "drawer-box", "pulls", "pilot-depth", "screw-tips", "kit"})

    def test_requires_chain(self):
        decisions = copy.deepcopy(ap.OPEN_DECISIONS)
        for d in ("back", "drawer-box", "pulls", "shelf-pins", "restraint"):
            del decisions[d]
        resolved = {rs.step["id"]: rs for rs in
                    ag.resolve(st.STEPS, self.parts, self.fasteners, decisions=decisions)}
        for sid in AFTER_RIGHT_SIDE:
            self.assertIn("bookcase-right-side", self.by_id[sid].step["requires"], sid)
            self.assertEqual(resolved[sid].held_by, ["slide"], sid)
        del decisions["slide"]
        resolved = ag.resolve(st.STEPS, self.parts, self.fasteners, decisions=decisions)
        self.assertEqual([rs.step["id"] for rs in resolved if rs.held_by], ["bookcase-plinth"])

    def test_drawer_order(self):
        self.assertIn("bookcase-drawer-box", self.by_id["bookcase-slides"].step["requires"])
        self.assertIn("bookcase-slides", self.by_id["bookcase-drawer-pull"].step["requires"])
        decisions = copy.deepcopy(ap.OPEN_DECISIONS)
        del decisions["slide"]
        resolved = {rs.step["id"]: rs for rs in
                    ag.resolve(st.STEPS, self.parts, self.fasteners, decisions=decisions)}
        self.assertEqual(resolved["bookcase-slides"].held_by, ["drawer-box"])

    def test_resolving_a_decision_validates(self):
        decisions = copy.deepcopy(ap.OPEN_DECISIONS)
        del decisions["back"]  # the README's way to resolve a decision
        resolved = ag.resolve(st.STEPS, self.parts, self.fasteners, decisions=decisions)
        self.assertEqual(ag.validate(resolved, self.parts, self.fasteners, decisions=decisions), [])
        back = next(rs for rs in resolved if rs.step["id"] == "bookcase-back")
        self.assertEqual(back.held_by, ["slide"])

    def test_decision_ids_survive_source_removal(self):
        # Resolve "back" the README way, by deleting its line from the source, and re-run the module.
        source = Path(ap.__file__).read_text(encoding="utf-8")
        start = source.index('    "back": ')
        edited = source[:start] + source[source.index("\n", start) + 1:]
        namespace = {"__name__": "assembly_parts_edited", "__file__": ap.__file__}
        exec(compile(edited, ap.__file__, "exec"), namespace)
        self.assertNotIn("back", namespace["OPEN_DECISIONS"])
        self.assertIn("back", namespace["DECISION_IDS"])

    def test_new_decision_must_be_listed(self):
        decisions = dict(ap.OPEN_DECISIONS, hinges="Choose hinge hardware")
        errors = ag.validate(ag.resolve(st.STEPS, self.parts, self.fasteners, decisions=decisions),
                             self.parts, self.fasteners, decisions=decisions)
        self.assertTrue(any("hinges" in e and "DECISION_IDS" in e for e in errors), errors)

    def test_unknown_decision_in_joint_or_part_hold(self):
        import dataclasses
        import unittest.mock as mock
        joints = dict(ap.JOINTS)
        joints["L07-L01"] = dataclasses.replace(joints["L07-L01"], hold="slyde")
        with mock.patch.object(ap, "JOINTS", joints), mock.patch.dict(ap.PART_HOLDS, {"L05": "plinthh"}):
            errors = ag.validate(ag.resolve(st.STEPS, self.parts, self.fasteners), self.parts, self.fasteners)
        self.assertTrue(any("slyde" in e for e in errors), errors)
        self.assertTrue(any("plinthh" in e for e in errors), errors)

    def test_rejects(self):
        def changed(index, **fields):
            steps = copy.deepcopy(st.STEPS)
            steps[index].update(fields)
            return steps
        self.assertTrue(any("Q99" in e for e in self.errors_for(changed(0, adds=["L01", "L02", "Q99"]))))
        self.assertTrue(any("L09-L01" in e for e in self.errors_for(changed(2, joints=["L09-L01"]))))
        twice = self.errors_for(changed(2, adds=["L04", "L01"]))
        self.assertTrue(any("L01" in e and "more than once" in e for e in twice), twice)
        self.assertTrue(any("bookcase-nope" in e for e in self.errors_for(changed(7, requires=["bookcase-nope"]))))
        self.assertTrue(any("bench-9" in e for e in self.errors_for(changed(0, pose={"L01": "bench-9"}))))
        self.assertTrue(any("not-a-decision" in e for e in self.errors_for(changed(3, hold="not-a-decision"))))

    def test_fastener_totals(self):
        totals = ag.fastener_totals(self.resolved, self.parts)
        self.assertEqual(totals["dowel"], {"bookcase": 12})
        self.assertEqual(totals["screw-8x2"], {"bookcase": 18})
        right = {h["code"]: h for h in self.by_id["bookcase-right-side"].hardware}
        self.assertEqual((right["dowel"]["count"], right["dowel"]["phase"]), (6, "dowel"))
        self.assertEqual(right["screw-8x2"]["nodes"][:2], ["L04-L02-screw-1", "L04-L02-screw-2"])
        self.assertEqual(ag.validate(self.resolved, self.parts, self.fasteners), [])

    def test_consumables(self):
        for sid in ("bookcase-bottom", "bookcase-shelf", "bookcase-top", "bookcase-right-side"):
            self.assertEqual(self.by_id[sid].step["consumables"], ["glue"], sid)
        steps = copy.deepcopy(st.STEPS)
        steps[2]["consumables"] = ["epoxy"]
        self.assertTrue(any("epoxy" in e for e in self.errors_for(steps)))

    def test_drill_entry_must_be_side(self):
        steps = copy.deepcopy(st.STEPS)
        steps[0]["drill"] = [{"joint": "L04-L01", "part": "L04"}]
        self.assertTrue(any("L04-L01" in e and "side" in e for e in self.errors_for(steps)))


if __name__ == "__main__":
    unittest.main()
