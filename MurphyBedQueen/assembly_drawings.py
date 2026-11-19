"""Generated SVG drawings for the step-by-step guide: an exploded view per step and a
dimensioned hole close-up on every step that drills."""

import functools
import math
import textwrap
from html import escape

import assembly_parts as ap
import assembly_steps as st
from generate_cut_layouts import inches

WIDTH = 600
COS30, SIN30 = math.cos(math.radians(30)), 0.5
EYE = (-1 / math.sqrt(3),) * 3  # view direction: from the room side, outer end and above
EXPLODE = 8.0  # inches new parts are drawn back along their travel


@functools.lru_cache(maxsize=1)
def fastener_names():
    """Catalogue name per fastener code: kit names from the inventory, bought ones from the BOM."""
    return {code: f.name for code, f in ap.load_fasteners().items()}

INK, GREY, ACCENT, HOLD_RED = "#1f2933", "#9aa5b1", "#c2410c", "#b91c1c"


def _svg(height, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height:.0f}" '
            f'width="{WIDTH}" height="{height:.0f}" role="img" font-family="system-ui, sans-serif">'
            f'<title>{escape(title)}</title><rect width="100%" height="100%" fill="#fff"/>'
            + "".join(body) + "</svg>")


def _text(x, y, value, size=13, weight="normal", fill=INK, anchor="start"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}">{escape(value, quote=False)}</text>')


def _wrapped(x, y, value, width_chars, **kw):
    lines = textwrap.wrap(value, width_chars) or [""]
    return [_text(x, y + 17 * i, line, **kw) for i, line in enumerate(lines)], 17 * len(lines)


def hold_lines(rs):
    kit = ap.discrepancy_holds()
    lines = []
    for decision in rs.held_by:
        if decision == "kit":
            lines += [kit[c["code"]] for c in rs.hardware if c["code"] in kit]
        else:
            lines.append(ap.OPEN_DECISIONS[decision])
    return lines


def _hold_banner(rs, y):
    if not rs.held_by:
        return [], 0
    body, height = [], 0
    for line in hold_lines(rs):
        parts, h = _wrapped(20, y + 22 + height, line, 78, size=13, fill="#7f1d1d")
        body += parts
        height += h
    box = [f'<rect x="8" y="{y}" width="{WIDTH - 16}" height="{height + 34}" rx="6" fill="#fef2f2" '
           f'stroke="{HOLD_RED}" stroke-width="2"/>',
           _text(20, y + 20, "HOLD — not ready to build", 14, "bold", HOLD_RED)]
    return box + _shift(body, 18), height + 42


def _shift(elements, dy):
    out = []
    for e in elements:
        head, _, rest = e.partition(' y="')
        value, _, tail = rest.partition('"')
        out.append(f'{head} y="{float(value) + dy:.1f}"{tail}')
    return out


def project(p):
    x, y, z = p
    return ((y - x) * COS30, (x + y) * SIN30 - z)


def _pose_box(part, pose, host=None):
    return (part.min, part.max) if pose == "installed" else st.pose_box(part, pose, host)


def drawn_box(part, rs, pid, host=None):
    """Box drawn for `pid` in this step: its pose, pulled back along `move` if it is new or moving."""
    return drawn_boxes(part, rs, pid, host)[0] if len(part.boxes) == 1 else _bounds(drawn_boxes(part, rs, pid, host))


def _bounds(boxes):
    return (tuple(min(b[0][k] for b in boxes) for k in range(3)), tuple(max(b[1][k] for b in boxes) for k in range(3)))


def drawn_boxes(part, rs, pid, host=None):
    """Every box of `pid` (one for wood, several for a steel shape) as drawn in this step."""
    pose = rs.poses[pid]
    out = []
    for lo, hi in part.boxes or ((part.min, part.max),):
        if pose != "installed":
            box = ap.Part(pid, "", "", lo, hi, part.stock, part.finish, part.stage)
            lo, hi = st.pose_box(box, pose, host or part)
        if pid in _moving(rs) or (host is not None and host.id in _moving(rs)):
            back = [-EXPLODE * m for m in rs.step["move"]]
            lo = tuple(lo[k] + back[k] for k in range(3))
            hi = tuple(hi[k] + back[k] for k in range(3))
        out.append((lo, hi))
    return out


def _moving(rs):
    """Parts drawn pulled back with an arrow: the parts added, else the parts this step moves."""
    return set(rs.step["adds"]) or set(rs.step["pose"])


def _faces(lo, hi):
    """The three faces seen from the eye (+x, +y, +z normals) as 3D polygons."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    return [
        [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],  # top
        [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],  # room side
        [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],  # outer end
    ]


def _fit(points, top, height):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    span_x, span_y = max(xs) - min(xs) or 1, max(ys) - min(ys) or 1
    scale = min((WIDTH - 60) / span_x, height / span_y)
    ox = (WIDTH - span_x * scale) / 2 - min(xs) * scale
    oy = top + (height - span_y * scale) / 2 - min(ys) * scale
    return lambda p: (p[0] * scale + ox, p[1] * scale + oy)


def step_svg(index, resolved, parts):
    rs = resolved[index]
    step = rs.step
    body = [_text(16, 28, f"Step {index + 1} of {len(resolved)}", 13, fill=GREY)]
    title, h = _wrapped(16, 50, step["title"], 60, size=17, weight="bold")
    body += title
    y = 50 + h
    banner, h = _hold_banner(rs, y)
    body += banner
    y += h + 8
    drilled = {h.part for h in rs.drilled}
    visible = [pid for pid in rs.poses if pid in parts and parts[pid].stage == step["stage"]
               and (rs.poses[pid] == "installed" or pid in _moving(rs) or pid in drilled)]
    shapes = {pid: drawn_boxes(parts[pid], rs, pid, parts.get(parts[pid].host)) for pid in visible}
    boxes = {pid: _bounds(shape) for pid, shape in shapes.items()}
    moving = _moving(rs)
    order = sorted(visible, key=lambda pid: -sum((boxes[pid][0][k] + boxes[pid][1][k]) / 2 * EYE[k]
                                                  for k in range(3)))
    corners = [project(c) for lo, hi in boxes.values() for face in _faces(lo, hi) for c in face]
    steel = [pid for pid in visible if parts[pid].representative]
    view_h = 300
    to_px = _fit(corners, y, view_h)
    labels = []
    for pid in order:
        lo, hi = boxes[pid]
        new = pid in moving
        focus = new or pid in drilled
        cls = "part new" if new else ("part drilled" if focus else "part done")
        fill, stroke, width = ("#fff", INK, 2.2) if focus else ("#eef1f4", GREY, 1)
        if parts[pid].finish == "steel":
            fill = "#d5d9de" if focus else "#e4e7eb"
        polys = "".join(
            f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in (to_px(project(c)) for c in face))}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round"/>'
            for box in shapes[pid] for face in _faces(*box))
        label = ""
        if focus:
            cx, cy = to_px(project(tuple((lo[k] + hi[k]) / 2 for k in range(3))))
            badge = (f'<rect x="{cx - 18:.1f}" y="{cy - 11:.1f}" width="36" height="18" rx="4" fill="{ACCENT}"/>'
                     + _text(cx, cy + 3, pid, 12, "bold", "#fff", "middle"))
            if new and any(step["move"]):
                seat = to_px(project(tuple((lo[k] + hi[k]) / 2 + EXPLODE * step["move"][k] for k in range(3))))
                label += (f'<line x1="{cx:.1f}" y1="{cy + 9:.1f}" x2="{seat[0]:.1f}" y2="{seat[1]:.1f}" '
                          f'stroke="{ACCENT}" stroke-width="2" stroke-dasharray="5 4" '
                          f'marker-end="url(#arrow)"/>')
            label += badge
        body.append(f'<g class="{cls}" data-part="{pid}">{polys}</g>')
        labels.append(label)
    body.append('<g class="labels">' + "".join(labels) + "</g>")  # above every box
    y += view_h + 12
    if steel:
        body.append(_text(16, y + 4, f"{', '.join(sorted(steel))}: representative shape (steel sizes not given "
                                     f"by Rockler).", 12, fill=GREY))
        y += 22
    panel, h = _hardware_panel(rs, y)
    body += panel
    defs = (f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{ACCENT}"/></marker></defs>')
    return _svg(y + h + 10, [defs] + body, f"Step {index + 1}: {step['title']}")


def _dowel_glyph(x, y, scale):
    w, h = 1.5 * scale, 0.375 * scale
    return (f'<rect x="{x:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="2" fill="#e8d5b0" '
            f'stroke="{INK}"/>'), w


def _screw_glyph(x, y, scale):
    w, shank, head = 2.0 * scale, 0.164 * scale, 0.32 * scale
    return (f'<path d="M{x:.1f},{y - head / 2:.1f} L{x + 4:.1f},{y - shank / 2:.1f} L{x + w - 6:.1f},'
            f'{y - shank / 2:.1f} L{x + w:.1f},{y:.1f} L{x + w - 6:.1f},{y + shank / 2:.1f} L{x + 4:.1f},'
            f'{y + shank / 2:.1f} L{x:.1f},{y + head / 2:.1f} z" fill="#cbd2d9" stroke="{INK}"/>'), w


def _kit_glyph(x, y, code):
    return (f'<rect x="{x:.1f}" y="{y - 11:.1f}" width="34" height="22" rx="5" fill="#cbd2d9" stroke="{INK}"/>'
            + _text(x + 17, y + 5, code, 12, "bold", anchor="middle")), 34


def _hardware_panel(rs, y):
    names = fastener_names()
    kit = set(ap.KIT_FASTENERS)
    items = [(names.get(h["code"], h["code"]), h["count"], h["code"]) for h in rs.hardware]
    items += [(ap.CONSUMABLES[c], None, c) for c in rs.step["consumables"]]
    if not items:
        return [], 0
    body = [f'<rect x="8" y="{y}" width="{WIDTH - 16}" height="{30 + 34 * len(items)}" rx="6" fill="#f8fafc" '
            f'stroke="#d9e2ec"/>', _text(20, y + 20, "You need", 13, "bold")]
    scale = 40
    for n, (name, count, code) in enumerate(items):
        cy = y + 44 + 34 * n
        if code == "dowel":
            glyph, w = _dowel_glyph(24, cy, scale)
        elif code in kit:
            glyph, w = _kit_glyph(24, cy, code)
        elif count is not None:
            glyph, w = _screw_glyph(24, cy, scale)
        else:
            glyph, w = (f'<circle cx="34" cy="{cy}" r="9" fill="#fde68a" stroke="{INK}"/>', 20)
        label = f"{name} ×{count}" if count is not None else name
        body += [glyph, _text(24 + max(w, 80) + 14, cy + 5, label, 14, "bold" if count else "normal")]
    return body, 30 + 34 * len(items)


def _in(value):
    """A position for the tape: inches to the nearest 1/16 (exact values stay in the data)."""
    return inches(round(value * 16) / 16)


def _hole_label(hole):
    size = f"Ø{inches(hole.diameter)}"
    if hole.through:
        return f"{size} through, countersink on the outside face" if hole.countersink else f"{size} through"
    return f"{size} × {inches(hole.depth)} deep"


HOLE_NAMES = {"dowel": "dowel", "clearance": "screw", "pilot": "screw pilot", "insert": "threaded insert",
              "lag": "lag bolt", "steel-dowel": "bracket's steel dowel", "bolt": "bolt"}


def _hole_kinds(group, left, y):
    body, kinds = [], {}
    for hole in group:
        key = (hole.kind, _hole_label(hole))
        kinds[key] = kinds.get(key, 0) + 1
    for (kind, label), count in kinds.items():
        body.append(_text(left, y, f"{label}  ×{count} ({HOLE_NAMES.get(kind, kind)})", 13, "bold"))
        y += 18
    return body, y


def _joint_strip(pid, joint, group, parts, y):
    """Holes of one joint on one part, laid out along the joint's run from its datum."""
    body, left = [], 50
    g = ap.joint_geometry(joint, parts)
    part = parts[pid]
    on_side = pid == joint.side
    other = joint.panel if on_side else joint.side
    if on_side:
        surface = "inside face"
    else:  # the panel's end (its long axis meets the side) or its long edge
        surface = "end" if max(range(3), key=lambda k: part.size[k]) == g.contact_axis else "edge"
        surface = f"{surface} at {joint.side}"
    body.append(_text(16, y, f"{pid} {surface} — joint with {other} ({parts[other].label.lower()})", 14, "bold"))
    y += 40
    length = part.size[g.run_axis] if on_side and joint.band else None
    if length is None:
        lo = max(parts[joint.side].min[g.run_axis], parts[joint.panel].min[g.run_axis])
        hi = min(parts[joint.side].max[g.run_axis], parts[joint.panel].max[g.run_axis])
        length = hi - lo
    scale = min(30, (WIDTH - 2 * left) / length)
    strip_h = 1.5 * 30 if on_side else ap.drilling_thickness(part) * 30
    body.append(f'<rect x="{left}" y="{y}" width="{length * scale:.1f}" height="{strip_h:.1f}" '
                f'fill="#f1f5f9" stroke="{INK}"/>')
    if on_side and joint.band:
        band_h = (joint.band[1] - joint.band[0]) * 30
        body.append(f'<rect x="{left}" y="{y + (strip_h - band_h) / 2:.1f}" width="{length * scale:.1f}" '
                    f'height="{band_h:.1f}" fill="#dbeafe" stroke="#93c5fd" stroke-dasharray="4 3"/>')
    body.append(_text(left - 4, y + strip_h + 16, g.datum_name, 11, fill=GREY))
    cy = y + strip_h / 2
    for n, hole in enumerate(sorted(group, key=lambda h: h.u)):
        cx = left + hole.u * scale
        r = max(hole.diameter / 2 * 30, 3)
        fill = "#fff" if hole.through else INK
        body.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{INK}" '
                    f'stroke-width="1.5"/>')
        if hole.countersink:
            body.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r + 3:.1f}" fill="none" stroke="{INK}"/>')
        tick_y = y - 8 - 14 * (n % 2)
        body += [f'<line x1="{cx:.1f}" y1="{y:.1f}" x2="{cx:.1f}" y2="{tick_y:.1f}" stroke="{GREY}"/>',
                 _text(cx, tick_y - 3, f'{_in(hole.u)}"', 12, anchor="middle")]
    y += strip_h + 34
    if on_side and joint.band:
        body.append(_text(left, y, f'All holes {inches(group[0].v)}" up from the bottom end '
                                   f'(centre of the {inches(joint.band[0])}–{inches(joint.band[1])}" '
                                   f'joint band).', 12))
        y += 18
        body.append(_text(left, y, "Inside the band: keep shelf-pin rows and slide screws out of it.",
                          12, fill="#1d4ed8"))
    elif on_side:
        reference = group[0].ref_end
        body.append(_text(left, y, f'All holes {_in(group[0].v)}" from the {reference}.', 12))
        if g.datum_name == "lower end":
            y += 18
            body.append(_text(left, y, f'The lower end is {_in(g.datum - part.min[g.run_axis])}" up from '
                                       f'{pid}\'s bottom end (where {other} starts).', 12))
    else:
        body.append(_text(left, y, f"Centred in the thickness; drill square to the {surface.split()[0]}.", 12))
    y += 20
    kinds, y = _hole_kinds(group, left, y)
    return body + kinds, y + 22


def _face_view(pid, pattern, group, parts, y):
    """A side's inside face with a pattern's holes, each dimensioned from the front edge and the bottom end."""
    body, left = [], 50
    body.append(_text(16, y, f"{pid} inside face — {len(group)} holes, same layout on both sides", 14, "bold"))
    y += 22
    top_v = max(h.v for h in group) + 3
    scale = 12
    width, height = parts[pid].size[1] * scale, top_v * scale
    body.append(f'<rect x="{left}" y="{y}" width="{width:.1f}" height="{height:.1f}" fill="#f1f5f9" '
                f'stroke="{GREY}" stroke-dasharray="4 3"/>')
    body.append(f'<line x1="{left}" y1="{y}" x2="{left}" y2="{y + height:.1f}" stroke="{INK}" stroke-width="2"/>')
    body.append(f'<line x1="{left}" y1="{y + height:.1f}" x2="{left + width:.1f}" y2="{y + height:.1f}" '
                f'stroke="{INK}" stroke-width="2"/>')
    body.append(_text(left - 4, y + height + 16, "front edge", 11, fill=GREY))
    body.append(_text(left + width, y + height + 16, "bottom end", 11, fill=GREY, anchor="end"))
    table_x = left + width + 30
    body.append(_text(table_x, y + 12, "Hole: from the front edge, up from the bottom end", 12, "bold"))
    for n, hole in enumerate(group, 1):
        cx, cy = left + hole.u * scale, y + height - hole.v * scale
        body.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{max(hole.diameter / 2 * scale, 3):.1f}" '
                    f'fill="{INK}" stroke="{INK}"/>')
        body.append(_text(cx + 7, cy - 5, str(n), 11, "bold", ACCENT))
        mark = " *" if hole.aligned else ""
        body.append(_text(table_x, y + 32 + 18 * n, f'{n}:  {_in(hole.u)}",  {_in(hole.v)}"{mark}', 12))
    y += max(height, 32 + 18 * len(group)) + 30
    if any(h.aligned for h in group):
        body.append(_text(left, y, "* position by alignment — check against the plate before drilling.", 12,
                          fill="#1d4ed8"))
        y += 20
    if group[0].verified:
        body.append(_text(left, y, f"Transcribed from {group[0].verified}.", 12, fill=GREY))
        y += 20
    kinds, y = _hole_kinds(group, left, y)
    return body + kinds, y + 22


def _stud_table(pid, pattern, group, parts, y):
    """Stud-located holes: offsets along each stud line, never a position along the cabinet."""
    body, left = [], 50
    names = {"M05": "M05", "M06": "M06"}
    body.append(_text(16, y, f"{pid} — on each stud line", 14, "bold"))
    y += 24
    body.append(_text(left, y, "On each stud line:", 13, "bold"))
    y += 20
    first_stud = group[0].example[0]
    one = [h for h in group if h.example[0] == first_stud]
    wall = [h for h in one if h.part == "wall"]
    for hole in (h for h in one if h.part != "wall"):
        name = f"{hole.name}  " if hole.name else ""
        if hole.ref_end == "wall":
            where = f'{_in(hole.v)}" from the wall'
        elif hole.ref_end == "top edge":
            where = f'{_in(hole.v)}" down from the top edge of {names.get(pid, pid)}'
        else:
            where = f'{_in(hole.v)}" up from the bottom edge of {names.get(pid, pid)}'
        body.append(_text(left, y, f"{name}{where} — {_hole_label(hole)} ({HOLE_NAMES.get(hole.kind, hole.kind)})",
                          12))
        y += 18
    if wall:
        labels = ", ".join(h.name for h in wall)
        body.append(_text(left, y, f"{labels}: mark through the bracket onto the wall, "
                                   f"{inches(wall[0].diameter)} in pilots into the stud.", 12))
        y += 18
    y += 6
    body.append(_text(left, y, "Find the stud centres with a stud finder; at least three studs.", 12,
                      fill="#1d4ed8"))
    y += 20
    if group[0].verified:
        body.append(_text(left, y, f"Transcribed from {group[0].verified}.", 12, fill=GREY))
        y += 20
    return body, y + 22


def holes_svg(rs, parts):
    """Close-up of every hole this step drills: `drill` holes and the panel-edge holes it joins."""
    holes = rs.drilled + rs.joined
    if not holes:
        return None
    groups = {}
    for hole in holes:
        groups.setdefault((hole.part if hole.part != "wall" else None, hole.joint), []).append(hole)
    merged = {}
    for (pid, gid), group in groups.items():  # a pattern's wall holes go with its cabinet holes
        key = (pid or ap.PATTERNS[gid].part, gid)
        merged.setdefault(key, []).extend(group)
    body = [_text(16, 28, f"Holes — {rs.step['title']}", 15, "bold")]
    y = 50
    for (pid, gid), group in merged.items():
        if gid in ap.JOINTS:
            part, y = _joint_strip(pid, ap.JOINTS[gid], group, parts, y)
        elif all(h.world is not None for h in group):
            part, y = _face_view(pid, ap.PATTERNS[gid], group, parts, y)
        else:
            part, y = _stud_table(pid, ap.PATTERNS[gid], group, parts, y)
        body += part
    return _svg(y, body, f"Holes: {rs.step['title']}")
