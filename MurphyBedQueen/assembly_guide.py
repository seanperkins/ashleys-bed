"""Resolve and validate the step-by-step assembly guide data."""

from dataclasses import dataclass, field

import assembly_parts as ap
import assembly_steps as st

STEP_KEYS = {"id", "stage", "title", "adds", "joints", "fasteners", "consumables", "drill", "pose",
             "move", "camera", "text", "warnings", "hold", "requires", "source"}


@dataclass
class ResolvedStep:
    step: dict
    held_by: list
    drilled: list
    joined: list
    hardware: list
    poses: dict  # part id -> pose name, for every part added so far
    errors: list = field(default_factory=list)


def _add_unique(items, value):
    if value not in items:
        items.append(value)


def _joint(jid, errors, step_id):
    joint = ap.JOINTS.get(jid)
    if joint is None:
        errors.append(f"{step_id}: unknown joint {jid}")
    return joint


def resolve(steps, parts, fasteners, decisions=None, joints=None):
    """Turn step dicts into ResolvedStep records, propagating HOLDs.

    A step is held by its own `hold`, by any held joint it drills or makes, by any held part it
    adds, by kit discrepancies on hardware it uses, and by anything an earlier step it
    `requires` is held by. Decisions missing from `decisions` count as resolved.
    """
    decisions = ap.OPEN_DECISIONS if decisions is None else decisions
    kit_holds = ap.discrepancy_holds()
    resolved, seen, poses = [], {}, {}
    for step in steps:
        sid = step.get("id", "?")
        errors = [f"{sid}: unknown key {k}" for k in sorted(set(step) - STEP_KEYS)]
        errors += [f"{sid}: missing key {k}" for k in sorted(STEP_KEYS - set(step))]
        held = []

        def hold(decision):
            if decision in decisions:
                _add_unique(held, decision)

        if step.get("hold"):
            hold(step["hold"])
        for pid in step.get("adds", []):
            if pid not in parts:
                errors.append(f"{sid}: unknown part {pid}")
                continue
            poses.setdefault(pid, "installed")
            if pid in ap.PART_HOLDS:
                hold(ap.PART_HOLDS[pid])
        for pid, pose in step.get("pose", {}).items():
            if pose not in st.POSES:
                errors.append(f"{sid}: unknown pose {pose} for {pid}")
            elif pid not in poses:
                errors.append(f"{sid}: pose for {pid}, which has not been added yet")
            else:
                poses[pid] = pose
        drilled, joined, hardware = [], [], {}
        for entry in step.get("drill", []):
            joint = _joint(entry["joint"], errors, sid)
            if joint is None:
                continue
            if entry["part"] != joint.side:
                errors.append(f"{sid}: drill entry {joint.id} must name the side {joint.side}")
                continue
            if joint.hold:
                hold(joint.hold)
            drilled += [h for h in ap.joint_holes(joint, parts) if h.part == joint.side]
        for jid in step.get("joints", []):
            joint = _joint(jid, errors, sid)
            if joint is None:
                continue
            if joint.hold:
                hold(joint.hold)
            joined += [h for h in ap.joint_holes(joint, parts) if h.part == joint.panel]
            for code, kind, count, phase in (("dowel", "dowel", len(joint.dowels), "dowel"),
                                             ("screw-8x2", "screw", len(joint.screws), "screw")):
                entry = hardware.setdefault(code, {"code": code, "count": 0, "nodes": [], "phase": phase})
                entry["count"] += count
                entry["nodes"] += [f"{jid}-{kind}-{n}" for n in range(1, count + 1)]
        for code, count in step.get("fasteners", {}).items():
            if code not in fasteners:
                errors.append(f"{sid}: unknown fastener code {code}")
            entry = hardware.setdefault(code, {"code": code, "count": 0, "nodes": [], "phase": "screw"})
            entry["count"] += count
        if any(code in kit_holds for code in hardware):
            hold("kit")
        for required in step.get("requires", []):
            if required not in seen:
                errors.append(f"{sid}: requires {required}, which is not an earlier step")
                continue
            for decision in seen[required].held_by:
                _add_unique(held, decision)
        rs = ResolvedStep(step, held, drilled, joined, list(hardware.values()), dict(poses), errors)
        resolved.append(rs)
        seen[sid] = rs
    return resolved


def fastener_totals(resolved, parts):
    totals = {}
    for rs in resolved:
        for item in rs.hardware:
            per = totals.setdefault(item["code"], {})
            per[rs.step["stage"]] = per.get(rs.step["stage"], 0) + item["count"]
    return totals


def validate(resolved, parts, fasteners, decisions=None):
    decisions = ap.OPEN_DECISIONS if decisions is None else decisions
    errors, added, ids = [], {}, set()
    for rs in resolved:
        step, sid = rs.step, rs.step.get("id", "?")
        errors += rs.errors
        if sid in ids:
            errors.append(f"{sid}: duplicate step id")
        ids.add(sid)
        if "stage" in step and step["stage"] not in ap.STAGES:
            errors.append(f"{sid}: unknown stage {step['stage']}")
        if step.get("hold") and step["hold"] not in ap.DECISION_IDS:
            errors.append(f"{sid}: hold names unknown decision {step['hold']}")
        for c in step.get("consumables", []):
            if c not in ap.CONSUMABLES:
                errors.append(f"{sid}: unknown consumable {c}")
        for pid in step.get("adds", []):
            if pid in added:
                errors.append(f"{sid}: {pid} added more than once (first in {added[pid]})")
            added.setdefault(pid, sid)
    for pid, part in parts.items():
        if part.stage in st.ACTIVE_STAGES and pid not in added:
            errors.append(f"{pid} is never added")
    for decision in sorted(set(decisions) - ap.DECISION_IDS):
        errors.append(f"OPEN_DECISIONS has {decision}, which is missing from DECISION_IDS in assembly_parts.py")
    for joint in ap.JOINTS.values():
        if joint.hold and joint.hold not in ap.DECISION_IDS:
            errors.append(f"joint {joint.id}: hold names unknown decision {joint.hold}")
    for pid, decision in ap.PART_HOLDS.items():
        if decision not in ap.DECISION_IDS:
            errors.append(f"part {pid}: hold names unknown decision {decision}")
    held_joints = {j.id for j in ap.JOINTS.values() if j.hold in decisions}
    holes = [h for rs in resolved for h in rs.drilled + rs.joined]
    errors += ap.check_holes(holes, parts, held_joints)
    totals = {code: {a: n for a, n in per.items() if a in st.ACTIVE_STAGES}
              for code, per in fastener_totals(resolved, parts).items()}
    errors += ap.check_fasteners(totals, fasteners, st.ACTIVE_STAGES)
    return errors
