"""Resolve and validate the step-by-step assembly guide data."""

from dataclasses import dataclass, field

import assembly_parts as ap
import assembly_steps as st

STEP_KEYS = {"id", "stage", "title", "adds", "joints", "fasteners", "consumables", "drill", "fix", "pose",
             "move", "camera", "text", "warnings", "hold", "requires", "source"}


@dataclass
class ResolvedStep:
    step: dict
    held_by: list
    drilled: list
    joined: list
    hardware: list
    poses: dict  # node -> pose name, for every part, steel shape and hardware node so far
    errors: list = field(default_factory=list)
    hosts: dict = field(default_factory=dict)  # node -> the part whose pose it takes


def _add_unique(items, value):
    if value not in items:
        items.append(value)


def _joint(jid, errors, step_id):
    joint = ap.JOINTS.get(jid)
    if joint is None:
        errors.append(f"{step_id}: unknown joint {jid}")
    return joint


def _hardware(hardware, code, phase):
    return hardware.setdefault(code, {"code": code, "count": 0, "nodes": [], "phase": phase, "axes": []})


def resolve(steps, parts, fasteners, decisions=None, joints=None):
    """Turn step dicts into ResolvedStep records, propagating HOLDs.

    A step is held by its own `hold`, by any held joint or pattern it drills, makes or fixes, by any
    held part it adds, by kit discrepancies on hardware it uses, and by anything an earlier step it
    `requires` is held by. Decisions missing from `decisions` count as resolved.

    Steel shapes and hardware take their host part's pose: a joint's dowels and screws ride on the
    joint's side, a pattern's fixings on the pattern's part, a steel shape on its `host`.
    """
    decisions = ap.OPEN_DECISIONS if decisions is None else decisions
    kit_holds = ap.discrepancy_holds()
    resolved, seen, own, hosts = [], {}, {}, {}
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
            host = parts[pid].host or pid
            if host != pid and host not in own:
                errors.append(f"{sid}: {pid} rides on {host}, which has not been added yet")
                continue
            hosts.setdefault(pid, host)
            if host == pid:
                own.setdefault(pid, "installed")
            if pid in ap.PART_HOLDS:
                hold(ap.PART_HOLDS[pid])
        for pid, pose in step.get("pose", {}).items():
            if pose not in st.POSES:
                errors.append(f"{sid}: unknown pose {pose} for {pid}")
            elif pid not in own:
                errors.append(f"{sid}: pose for {pid}, which has not been added yet or rides on another part")
            else:
                own[pid] = pose
        drilled, joined, hardware = [], [], {}
        for entry in step.get("drill", []):
            if "pattern" in entry:
                pattern = ap.PATTERNS.get(entry["pattern"])
                if pattern is None:
                    errors.append(f"{sid}: unknown pattern {entry['pattern']}")
                    continue
                if pattern.hold:
                    hold(pattern.hold)
                drilled += ap.pattern_holes(pattern.id, parts)
                continue
            joint = _joint(entry["joint"], errors, sid)
            if joint is None:
                continue
            if entry["part"] != joint.side:
                errors.append(f"{sid}: drill entry {joint.id} must name the side {joint.side}")
                continue
            if joint.side not in own:
                errors.append(f"{sid}: drills {joint.side} before it is added")
                continue
            if joint.hold:
                hold(joint.hold)
            drilled += [h for h in ap.joint_holes(joint, parts) if h.part == joint.side]
        for jid in step.get("joints", []):
            joint = _joint(jid, errors, sid)
            if joint is None:
                continue
            missing = [pid for pid in (joint.side, joint.panel) if pid not in own]
            if missing:
                errors.append(f"{sid}: joins {jid} before {', '.join(missing)} is added")
                continue
            if joint.hold:
                hold(joint.hold)
            holes = ap.joint_holes(joint, parts)
            joined += [h for h in holes if h.part == joint.panel]
            # Dowels travel into the side's face holes; screws travel on into the panel's pilots.
            dowel_axis = next(h.axis for h in holes if h.part == joint.side and h.kind == "dowel")
            screw_axis = next(h.axis for h in holes if h.part == joint.panel and h.kind == "pilot")
            for code, kind, count, phase, axis in (
                    ("dowel", "dowel", len(joint.dowels), "dowel", dowel_axis),
                    ("screw-8x2", "screw", len(joint.screws), "screw", screw_axis)):
                entry = _hardware(hardware, code, phase)
                entry["count"] += count
                nodes = [f"{jid}-{kind}-{n}" for n in range(1, count + 1)]
                entry["nodes"] += nodes
                entry["axes"] += [axis] * count
                for node in nodes:
                    hosts[node] = joint.side
        for pid in step.get("fix", []):
            pattern = ap.PATTERNS.get(pid)
            if pattern is None:
                errors.append(f"{sid}: unknown pattern {pid}")
                continue
            if pattern.part not in own and pattern.part in parts:
                errors.append(f"{sid}: fixes {pid} before {pattern.part} is added")
                continue
            if pattern.hold:
                hold(pattern.hold)
            for fixing, node, hole in ap.pattern_fixings(pid, parts):
                if fixing.code not in fasteners:
                    errors.append(f"{sid}: unknown fastener code {fixing.code}")
                entry = _hardware(hardware, fixing.code, "dowel" if fixing.kind == "insert" else "screw")
                entry["count"] += 1
                entry["nodes"].append(node)
                entry["axes"].append(ap.fixing_direction(fixing, hole))
                hosts[node] = pattern.part
        for code, count in step.get("fasteners", {}).items():
            if code not in fasteners:
                errors.append(f"{sid}: unknown fastener code {code}")
            entry = _hardware(hardware, code, "screw")
            entry["count"] += count
        if any(code in kit_holds for code in hardware):
            hold("kit")
        for required in step.get("requires", []):
            if required not in seen:
                errors.append(f"{sid}: requires {required}, which is not an earlier step")
                continue
            for decision in seen[required].held_by:
                _add_unique(held, decision)
        poses = {node: own[host] for node, host in hosts.items()}
        rs = ResolvedStep(step, held, drilled, joined, list(hardware.values()), poses, errors, dict(hosts))
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
    for pattern in ap.PATTERNS.values():
        if pattern.hold and pattern.hold not in ap.DECISION_IDS:
            errors.append(f"pattern {pattern.id}: hold names unknown decision {pattern.hold}")
    for pid, decision in ap.PART_HOLDS.items():
        if decision not in ap.DECISION_IDS:
            errors.append(f"part {pid}: hold names unknown decision {decision}")
    held_joints = {j.id for j in ap.JOINTS.values() if j.hold in decisions}
    held_joints |= {p.id for p in ap.PATTERNS.values() if p.hold in decisions}
    holes = [h for rs in resolved for h in rs.drilled + rs.joined]
    errors += ap.check_holes(holes, parts, held_joints)
    totals = {code: {a: n for a, n in per.items() if a in st.ACTIVE_STAGES}
              for code, per in fastener_totals(resolved, parts).items()}
    errors += ap.check_fasteners(totals, fasteners, st.ACTIVE_STAGES)
    return errors
