#!/usr/bin/env python3
"""Generate the step-by-step assembly guide: assembly.glb, assembly-steps.json and step SVGs.

Standard library only. Writes into a sibling staging directory, validates the full set, then swaps
it into place, so a failure at any point leaves the previous outputs untouched.

    python3 MurphyBedQueen/generate_assembly_guide.py            # -> output/assembly-guide/
"""

import argparse
import json
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import assembly_drawings as dr  # noqa: E402
import assembly_glb as glb  # noqa: E402
import assembly_guide as ag  # noqa: E402
import assembly_parts as ap  # noqa: E402
import assembly_steps as st  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "output" / "assembly-guide"


def _round(values):
    return [round(v, 6) + 0.0 for v in values]


def hardware_axis(item, parts):
    """Scene direction a step's hardware travels in, from the holes it goes into (Fusion axes)."""
    axes = set(item.get("axes", []))
    if not axes:
        return None
    if len(axes) != 1:
        raise ValueError(f"{item['code']} items travel in different directions: {sorted(axes)}")
    return list(glb._normal_to_scene(axes.pop()))


def step_records(resolved, parts):
    names = {code: name for code, name in dr.FASTENER_NAMES.items()}
    records = []
    for i, rs in enumerate(resolved):
        step = rs.step
        records.append({
            "id": step["id"],
            "title": step["title"],
            "adds": step["adds"],
            "drills": sorted({h.part for h in rs.drilled + rs.joined}),
            "hardware": [{"code": h["code"], "name": names.get(h["code"], h["code"]), "count": h["count"],
                          "nodes": h["nodes"], "phase": h["phase"], "axis": hardware_axis(h, parts)}
                         for h in rs.hardware],
            "poses": {pid: _round(glb.scene_matrix(st.pose_matrix(parts[pid], pose)))
                      for pid, pose in rs.poses.items()},
            "move": [-step["move"][0], step["move"][2], step["move"][1]],
            "camera": step["camera"],
            "text": step["text"],
            "warnings": step["warnings"],
            "consumables": step["consumables"],
            "hold": dr.hold_lines(rs),
            "held_by": rs.held_by,
            "requires": step["requires"],
            "source": step["source"],
            "svg": f"step-{i + 1:02d}.svg",
            "holes_svg": f"step-{i + 1:02d}-holes.svg" if rs.drilled or rs.joined else None,
        })
    return records


def write_outputs(directory, resolved, parts):
    records = step_records(resolved, parts)
    for i, rs in enumerate(resolved):
        (directory / records[i]["svg"]).write_text(dr.step_svg(i, resolved, parts), encoding="utf-8")
        holes = dr.holes_svg(rs, parts)
        if holes is not None:
            (directory / records[i]["holes_svg"]).write_text(holes, encoding="utf-8")
    (directory / "assembly-steps.json").write_text(json.dumps(records, indent=1, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")
    (directory / "assembly.glb").write_bytes(glb.build_glb(parts, resolved))
    return records


def check_outputs(directory, steps, parts, resolved):
    records = json.loads((directory / "assembly-steps.json").read_text(encoding="utf-8"))
    if [r["id"] for r in records] != [s["id"] for s in steps]:
        raise ValueError("assembly-steps.json does not match the step list")
    for record in records:
        for key in ("svg", "holes_svg"):
            if record[key]:
                ET.parse(directory / record[key])
    gltf = glb.read_glb((directory / "assembly.glb").read_bytes())["json"]
    nodes = {n["name"] for n in gltf["nodes"]}
    expected = set(parts) | {n for rs in resolved for h in rs.hardware for n in h["nodes"]}
    missing = expected - nodes
    if missing:
        raise ValueError(f"assembly.glb is missing nodes: {sorted(missing)}")


def _recover(out_dir):
    """Restore an interrupted swap, then clear leftover staging and backup folders."""
    parent, name = out_dir.parent, out_dir.name
    backups = sorted(parent.glob(f"{name}.backup-*"), key=lambda p: p.stat().st_mtime)
    if not out_dir.exists() and backups:
        backups.pop().rename(out_dir)
    for leftover in list(parent.glob(f"{name}.staging-*")) + backups:
        shutil.rmtree(leftover, ignore_errors=True)


def generate(out_dir=DEFAULT_OUT, steps=None):
    out_dir = Path(out_dir)
    steps = st.STEPS if steps is None else steps
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    _recover(out_dir)
    staging = Path(tempfile.mkdtemp(dir=out_dir.parent, prefix=f"{out_dir.name}.staging-"))
    staging.chmod(0o755)  # mkdtemp makes 0700; the folder is published as-is
    try:
        parts = ap.load_parts()
        fasteners = ap.load_fasteners()
        resolved = ag.resolve(steps, parts, fasteners)
        errors = ag.validate(resolved, parts, fasteners)
        if errors:
            raise ValueError("Assembly guide data is invalid:\n  " + "\n  ".join(errors))
        write_outputs(staging, resolved, parts)
        check_outputs(staging, steps, parts, resolved)
        backup = None
        if out_dir.exists():
            backup = Path(tempfile.mkdtemp(dir=out_dir.parent, prefix=f"{out_dir.name}.backup-"))
            backup.rmdir()
            out_dir.rename(backup)
        try:
            staging.rename(out_dir)
        except OSError:
            if backup is not None:
                backup.rename(out_dir)
            raise
        if backup is not None:
            shutil.rmtree(backup)
        held = [rs for rs in resolved if rs.held_by]
        return {"steps": len(resolved), "holds": len(held),
                "held": {rs.step["id"]: rs.held_by for rs in held},
                "files": sorted(p.name for p in out_dir.iterdir())}
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    args = parser.parse_args(argv)
    try:
        summary = generate(args.out)
    except (ValueError, OSError) as error:
        print(f"Assembly guide not generated: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {len(summary['files'])} files to {args.out}: {summary['steps']} steps, "
          f"{summary['holds']} on HOLD")
    for sid, decisions in summary["held"].items():
        print(f"  HOLD {sid}: {', '.join(decisions)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
