"""Generated SVG drawings for the step-by-step guide: an exploded view per step and a
dimensioned hole close-up on every step that drills."""

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
FASTENER_NAMES = {code: name for code, name, _s, _u in ap.BOM_FASTENERS.values()} | ap.BUNDLED
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


def _pose_box(part, pose):
    return (part.min, part.max) if pose == "installed" else st.pose_box(part, pose)


def drawn_box(part, rs, pid):
    """Box drawn for `pid` in this step: its pose, pulled back along `move` if it is new or moving."""
    lo, hi = _pose_box(part, rs.poses[pid])
    if pid in _moving(rs):
        back = [-EXPLODE * m for m in rs.step["move"]]
        lo = tuple(lo[k] + back[k] for k in range(3))
        hi = tuple(hi[k] + back[k] for k in range(3))
    return lo, hi


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
    visible = [pid for pid in rs.poses if parts[pid].stage == step["stage"]
               and (rs.poses[pid] == "installed" or pid in _moving(rs) or pid in drilled)]
    boxes = {pid: drawn_box(parts[pid], rs, pid) for pid in visible}
    moving = _moving(rs)
    order = sorted(visible, key=lambda pid: -sum((boxes[pid][0][k] + boxes[pid][1][k]) / 2 * EYE[k]
                                                  for k in range(3)))
    corners = [project(c) for lo, hi in boxes.values() for face in _faces(lo, hi) for c in face]
    view_h = 300
    to_px = _fit(corners, y, view_h)
    labels = []
    for pid in order:
        lo, hi = boxes[pid]
        new = pid in moving
        focus = new or pid in drilled
        cls = "part new" if new else ("part drilled" if focus else "part done")
        fill, stroke, width = ("#fff", INK, 2.2) if focus else ("#eef1f4", GREY, 1)
        polys = "".join(
            f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in (to_px(project(c)) for c in face))}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round"/>'
            for face in _faces(lo, hi))
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


def _hardware_panel(rs, y):
    items = [(FASTENER_NAMES.get(h["code"], h["code"]), h["count"], h["code"]) for h in rs.hardware]
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
        elif count is not None:
            glyph, w = _screw_glyph(24, cy, scale)
        else:
            glyph, w = (f'<circle cx="34" cy="{cy}" r="9" fill="#fde68a" stroke="{INK}"/>', 20)
        label = f"×{count}  {name}" if count is not None else name
        body += [glyph, _text(24 + max(w, 80) + 14, cy + 5, label, 14, "bold" if count else "normal")]
    return body, 30 + 34 * len(items)


def _hole_label(hole):
    size = f"Ø{inches(hole.diameter)}"
    if hole.through:
        return f"{size} through, countersink on the outside face"
    return f"{size} × {inches(hole.depth)} deep"


def holes_svg(rs, parts):
    """Close-up of every hole this step drills: `drill` holes and the panel-edge holes it joins."""
    holes = rs.drilled + rs.joined
    if not holes:
        return None
    groups = {}
    for hole in holes:
        groups.setdefault((hole.part, hole.joint), []).append(hole)
    body = [_text(16, 28, f"Holes — {rs.step['title']}", 15, "bold")]
    y, scale, left = 50, 30, 50
    for (pid, jid), group in groups.items():
        joint = ap.JOINTS[jid]
        on_side = pid == joint.side
        other = joint.panel if on_side else joint.side
        surface = "inside face" if on_side else f"end at {joint.side}"
        heading = f"{pid} {surface} — joint with {other} ({parts[other].label.lower()})"
        body.append(_text(16, y, heading, 14, "bold"))
        y += 40
        length = parts[pid].size[1]
        strip_h = 1.5 * scale if on_side else ap.drilling_thickness(parts[pid]) * scale
        body.append(f'<rect x="{left}" y="{y}" width="{length * scale:.1f}" height="{strip_h:.1f}" '
                    f'fill="#f1f5f9" stroke="{INK}"/>')
        if on_side:
            band_h = (joint.band[1] - joint.band[0]) * scale
            body.append(f'<rect x="{left}" y="{y + (strip_h - band_h) / 2:.1f}" width="{length * scale:.1f}" '
                        f'height="{band_h:.1f}" fill="#dbeafe" stroke="#93c5fd" stroke-dasharray="4 3"/>')
        body.append(_text(left - 4, y + strip_h + 16, "front edge", 11, fill=GREY))
        cy = y + strip_h / 2
        for n, hole in enumerate(sorted(group, key=lambda h: h.u)):
            cx = left + hole.u * scale
            r = max(hole.diameter / 2 * scale, 3)
            fill = "#fff" if hole.through else INK
            body.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{INK}" '
                        f'stroke-width="1.5"/>')
            if hole.countersink:
                body.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r + 3:.1f}" fill="none" stroke="{INK}"/>')
            tick_y = y - 8 - 14 * (n % 2)
            body += [f'<line x1="{cx:.1f}" y1="{y:.1f}" x2="{cx:.1f}" y2="{tick_y:.1f}" stroke="{GREY}"/>',
                     _text(cx, tick_y - 3, f'{inches(hole.u)}"', 12, anchor="middle")]
        y += strip_h + 34
        if on_side:
            body.append(_text(left, y, f'All holes {inches(group[0].v)}" up from the bottom end '
                                       f'(centre of the {inches(joint.band[0])}–{inches(joint.band[1])}" '
                                       f'joint band).', 12))
            y += 18
            body.append(_text(left, y, "Inside the band: keep shelf-pin rows and slide screws out of it.",
                              12, fill="#1d4ed8"))
        else:
            body.append(_text(left, y, "Centred in the thickness; drill square to the end.", 12))
        y += 20
        kinds = {}
        for hole in group:
            kinds.setdefault((hole.kind, _hole_label(hole)), 0)
            kinds[(hole.kind, _hole_label(hole))] += 1
        for (kind, label), count in kinds.items():
            name = {"dowel": "dowel", "clearance": "screw", "pilot": "screw pilot"}.get(kind, kind)
            body.append(_text(left, y, f"{label}  ×{count} ({name})", 13, "bold"))
            y += 18
        y += 22
    return _svg(y, body, f"Holes: {rs.step['title']}")
