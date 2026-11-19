#!/usr/bin/env python3
"""Generate the table-saw cut plan (PDF) for every sheet from the approved sheet layout.

Run with Python 3; only the standard library is required. The plan reuses the
sheet map (S01-S08) and part sizes from generate_cut_layouts.py, so cut sizes
never drift from the cut list. The joints use dowels and screws, so parts are sawn to FINISHED
length (no dado tongues, no routing). Rips are on the table saw; crosscuts too long for a
sled use a circular saw and straightedge. It describes
rip/crosscut sequences, fence settings and the tape label for each part. Shop
technique, safety and machine limits stay with the person at the saw.
"""

import argparse
import re
from pathlib import Path

from generate_cut_layouts import (
    MEASURED_34, PART_SPECS, ROOT, PdfPage, build_layout, inches, load_parts,
    number, pdf_from_pages, require, stock_title, wrapped,
)

KERF = 0.125      # full-kerf blade; a thin-kerf blade only leaves the pieces a hair larger
ROUGH = 0.25      # extra width on rough rips, trimmed off by the finish rip
TRIM = 0.25       # squaring cut off the factory end of each strip
NARROW = 4.0      # rough strips narrower than this are peeled with a wider neighbour
SHEET_ORDER = ["S02", "S05", "S06", "S01", "S03", "S04", "S07", "S08"]
TITLE = "TABLE SAW PLAN - ALL SHEETS (3/4, 1/2 AND 1/4 IN)"
SHOP_NOTE = ("Geometry and sequence only. Blade height, feed, push sticks, featherboards and "
             "support are the operator's responsibility.")

BODY = 10         # step text in points: readable at arm's length at the saw
HEAD = 11
LINE = 12.5       # line pitch for BODY text
COL_X = 290       # instruction column to the right of the sketch on each sheet page
COL_CHARS = 50    # wrap width in characters for BODY text in that 286 pt column
PAGE_NUM_Y = 42   # 0.58 in up, clear of the unprintable bottom margin on home printers
BLUE = "0.88 0.93 0.96"     # bed (M) parts
GREEN = "0.90 0.94 0.87"    # bookcase (L) parts

# Rockler kit number for the bed parts ("1R Right side" -> 1R); bookcase parts have none.
KIT = {}
for _pid, _key, *_rest in PART_SPECS:
    _match = re.match(r"(\d+(?:\.\d+)?[A-Z]?)\s", _key)
    if _match:
        KIT[_pid] = _match.group(1)

# Third line of tape only where it prevents a mistake (see the LABELS section of page 1).
TAPE_EXTRA = {
    "L01": "FRONT edge tick",
    "L02": "FRONT edge tick",
    "L07": "FRONT edge tick",
    "M07": "THIN TO 5/8",
}

CROSSCUT_NOTE = ("85 1/4 in crosscut off a 96 in strip: circular saw + clamped straightedge, "
                 "good face DOWN (a sled cannot support the strip).")
NARROW_NOTE = "narrow finish rip: push stick, featherboard, riving knife."
DOOR_NOTE = ("Door panels are visible painted faces: keep the best face on the outside. "
             "Tape goes on the inside face.")
SHEET_NOTES = {
    "S01": ["L05 plinth (2 1/2 in wide): " + NARROW_NOTE, "M03/M04: " + CROSSCUT_NOTE],
    "S02": ["M05/M06: " + CROSSCUT_NOTE,
            "M07 (3 in wide): " + NARROW_NOTE + " Cut the blank only; thin it to 5/8 in later "
            "(planer/sander or 5/8 in stock)."],
    "S03": ["M01/M02 (bed sides) are the same size as L01/L02 (bookcase sides, S04): tape each "
            "one as it comes off the saw."],
    "S04": ["L01/L02 (bookcase sides) are the same size as M01/M02 (bed sides, S03): tape each "
            "one as it comes off the saw."],
    "S05": [DOOR_NOTE],
    "S06": [DOOR_NOTE],
    "S07": ["1/2 in stock is not bought yet: sizes are nominal. Caliper the panel and re-check "
            "every size before cutting.",
            "Drawer-box sizes depend on the drawer-slide clearance, which is not confirmed. Confirm "
            "the slides first.",
            "L11/L12 (8 x 14) and L13/L14 (8 x 26 1/2) pair up by size: tape each one as it comes "
            "off the saw."],
    "S08": ["1/4 in stock is not bought yet: sizes are nominal. Caliper the sheet before cutting.",
            "Thin stock can slip under the fence or drop into the throat: zero-clearance insert, "
            "sheet fully supported.",
            "L06: rough rip R1 needs 28 11/16 in of rip capacity; without it, and for the 59 15/16 in "
            "crosscut, use a circular saw + clamped straightedge, good face DOWN.",
            "L06 back: tape on the wall side (the inside shows through the shelves)."],
}


def fmt(value):
    return f"{inches(value)} in ({value:.3f})"


def tape_text(part):
    """Exact words for the painter's-tape label on one part."""
    pid = part["partId"]
    kit = f" (kit {KIT[pid]})" if pid in KIT else ""
    bits = [f"{pid}{kit}", part["label"].upper(), "arrow to TOP"]
    if pid in TAPE_EXTRA:
        bits.append(TAPE_EXTRA[pid])
    return " / ".join(bits)


def tick(page, x, y):
    page.rectangle(x, y - 1, 7, 7)


def heading(page, x, y, text):
    page.text(x, y, text, HEAD, True)
    return y - 14


def item(page, x, y, text, size=BODY, width=COL_CHARS, step=LINE, box=False, bullet=None):
    """Wrapped text with a hanging indent, optionally led by a tick box or a bullet."""
    indent = 0
    if box:
        tick(page, x, y)
        indent = 12
    elif bullet:
        page.text(x, y, bullet, size)
        indent = 9
    return wrapped(page, x + indent, y, text, size, width=width - (indent and 3), step=step)


def plan_sheet(sheet):
    """Guillotine plan: rip strips along the grain, finish-rip, then crosscut."""
    groups = {}
    for part in sheet["parts"]:
        groups.setdefault(part["xInches"], []).append(part)
    columns = []
    for x in sorted(groups):
        parts = sorted(groups[x], key=lambda p: -p["lengthInches"])   # longest first
        width = max(p["widthInches"] for p in parts)
        columns.append({"name": chr(ord("A") + len(columns)), "parts": parts,
                        "width": width, "rough": width + ROUGH})
    require(columns[0]["rough"] >= NARROW, f"{sheet['sheetId']}: first strip is too narrow to rip safely")

    rips = []
    index = 0
    while index < len(columns):
        col = columns[index]
        nxt = columns[index + 1] if index + 1 < len(columns) else None
        if nxt and nxt["rough"] < NARROW:
            block = col["rough"] + KERF + nxt["rough"]
            rips.append({"fence": block, "text": f"strips {col['name']}+{nxt['name']} as one block "
                         f"({nxt['name']} is narrow)"})
            rips.append({"fence": col["rough"], "text": f"split the block: {col['name']} between blade and "
                         f"fence, narrow {nxt['name']} falls to the left"})
            index += 2
        else:
            rips.append({"fence": col["rough"], "text": f"strip {col['name']}"})
            index += 1

    used = sum(c["rough"] for c in columns) + KERF * len(columns)
    require(used <= sheet["widthInches"] - 0.25,
            f"{sheet['sheetId']}: strips need {used} in of a {sheet['widthInches']} in sheet")
    for col in columns:
        needed = TRIM + KERF + sum(p["lengthInches"] + KERF for p in col["parts"])
        col["needed"] = needed
        require(needed <= sheet["lengthInches"] - 0.25,
                f"{sheet['sheetId']} strip {col['name']}: needs {needed} in of a {sheet['lengthInches']} in strip")
        col["rerip"] = [p for p in col["parts"] if p["widthInches"] < col["width"]]
    return {"columns": columns, "rips": rips, "used": used}


def part_label(page, part, px, py, w, h):
    """Part ID and size inside a sketched part; rotated when the part is too narrow for the text."""
    size_text = f"{inches(part['widthInches'])} x {inches(part['lengthInches'])}"
    cx, cy = px + w / 2, py + h / 2
    if w >= 0.52 * 8 * len(size_text) + 6:
        page.text(cx - 0.52 * 9 * len(part["partId"]) / 2, cy + 3, part["partId"], 9, True)
        page.text(cx - 0.52 * 8 * len(size_text) / 2, cy - 8, size_text, 8)
    else:
        text = f"{part['partId']}  {size_text}"
        page.text(cx + 3, cy - 0.52 * 8 * len(text) / 2, text, 8, False, 90)


def sketch(page, sheet, plan, ox, oy, scale):
    page.rectangle(ox, oy, sheet["widthInches"] * scale, sheet["lengthInches"] * scale)
    x = 0.0
    for col in plan["columns"]:
        page.rectangle(ox + x * scale, oy, col["rough"] * scale, sheet["lengthInches"] * scale,
                       dashed=True)
        page.text(ox + (x + col["rough"] / 2) * scale - 3, oy + sheet["lengthInches"] * scale + 6,
                  col["name"], 11, True)
        y = 0.0
        page.rectangle(ox + x * scale, oy, col["width"] * scale, TRIM * scale, "0.8 0.8 0.8")
        y += TRIM + KERF
        for part in col["parts"]:
            fill = BLUE if part["assembly"] == "Main cabinet" else GREEN
            w, height = part["widthInches"] * scale, part["lengthInches"] * scale
            page.rectangle(ox + x * scale, oy + y * scale, w, height, fill)
            part_label(page, part, ox + x * scale, oy + y * scale, w, height)
            y += part["lengthInches"] + KERF
        x += col["rough"] + KERF


def sheet_page(sheet, plan, number_, total):
    page = PdfPage()
    page.commands.extend(["0.08 0.16 0.24 RG", "0.08 0.16 0.24 rg", "0.7 w"])
    page.text(36, 756, "ASHLEY'S MURPHY BED + LEFT BOOKCASE - TABLE SAW CUT SHEET", 13, True)
    page.text(36, 736, stock_title(sheet), 12, True)
    page.text(36, 720, "Good face UP on the table saw. Dashed = rough strips; grey = squaring trim; "
              "drawn from the factory end.", BODY)
    scale = 4.4
    ox, oy = 36, 259
    sketch(page, sheet, plan, ox, oy, scale)
    wrapped(page, ox, oy - 13, "Not for measuring. Strips run along the grain (up the page). "
            "Kerf drawn as 1/8 in.", 8, width=48, step=10)
    page.rectangle(ox, oy - 41, 12, 8, BLUE)
    page.text(ox + 16, oy - 39, "Bed parts (M)", 8)
    page.rectangle(ox + 100, oy - 41, 12, 8, GREEN)
    page.text(ox + 116, oy - 39, "Bookcase parts (L)", 8)

    col, y = COL_X, 700
    y = heading(page, col, y, "STEP 1  ROUGH RIPS")
    support = "Helper + outfeed. " if sheet["lengthInches"] > 48 else ""
    y = item(page, col, y, support + "Factory edge on the fence first, then each new sawn "
             "edge. Fence settings, in order:")
    for number_rip, rip in enumerate(plan["rips"], 1):
        y = item(page, col, y, f"R{number_rip}  fence {fmt(rip['fence'])} - {rip['text']}", box=True)
    y -= 6
    y = heading(page, col, y, "STEP 2  FINISH RIPS")
    y = item(page, col, y, "Full-length strips. Sawn edge on the fence; the blade trims the extra "
             "1/4 in. Fence = finished width:")
    for c in plan["columns"]:
        names = ", ".join(p["partId"] for p in c["parts"])
        y = item(page, col, y, f"{c['name']}  fence {fmt(c['width'])} ({names})", box=True)
    y -= 6
    y = heading(page, col, y, "STEP 3  CROSSCUTS")
    y = item(page, col, y, "Cut in this order. Measure each length from the end the last cut left. "
             "Over about 36 in: mark it from the trimmed end.")
    y = item(page, col, y, f"Trim {inches(TRIM)} in off the factory end of every strip", box=True)
    for c in plan["columns"]:
        for p in c["parts"]:
            y = item(page, col, y, f"{c['name']}  {p['partId']} at {inches(p['lengthInches'])}",
                     box=True)
    reripped = [(p, c) for c in plan["columns"] for p in c["rerip"]]
    if reripped:
        y -= 6
        y = heading(page, col, y, "STEP 4  RE-RIP NARROWER PARTS")
        for p, c in reripped:
            y = item(page, col, y, f"{p['partId']}: rip from {inches(c['width'])} to "
                     f"{inches(p['widthInches'])} in", box=True)
    y -= 6
    y = heading(page, col, y, "LABEL EACH PART")
    y = item(page, col, y, "Right after its cut: measure width, length and diagonals, then tape "
             "it (text under PARTS OUT).")
    y -= 6
    y = heading(page, col, y, "SHEET NOTE")
    for note in SHEET_NOTES[sheet["sheetId"]]:
        y = item(page, col, y, note, bullet="-")
    require(y >= 218, f"{sheet['sheetId']}: instruction column runs into the parts block (y={y})")

    page.line(36, 211, 576, 211)
    page.text(36, 197, "PARTS OUT: tick when taped (finished width x cut length, inches)", 10.5, True)
    row = 181
    for c in plan["columns"]:
        for p in c["parts"]:
            tick(page, 36, row)
            page.text(50, row, f"{p['partId']}  {p['label']}: {inches(p['widthInches'])} x "
                      f"{inches(p['lengthInches'])}", BODY, True)
            page.text(50, row - 11, "tape: " + tape_text(p), 9)
            row -= 24
    require(row >= 80, f"{sheet['sheetId']}: parts block runs into the footer (row={row})")
    page.text(36, 66, f"Blade kerf assumed {inches(KERF)} in. Strips use {number(plan['used'])} of "
              f"{sheet['widthInches']} in of sheet width. Re-measure the real sheet and scale to it.", 8)
    page.text(36, 55, SHOP_NOTE, 8)
    page.text(533, PAGE_NUM_Y, f"{number_} / {total}", 8)
    return page.bytes()


def overview_page(total, widest):
    page = PdfPage()
    page.commands.extend(["0.08 0.16 0.24 RG", "0.08 0.16 0.24 rg", "0.7 w"])
    page.text(36, 756, "ASHLEY'S MURPHY BED + LEFT BOOKCASE", 15, True)
    page.text(36, 736, TITLE, 13, True)
    y = 712
    sections = [
        ("METHOD", [
            "Same sheets and part IDs as the cut list (S01-S08); nothing is re-bought. Strip positions differ "
            "from the CNC layout coordinates, so mark from these pages, not the CSV.",
            "Per sheet: rough rips (+1/4 in), then finish rips to exact width, then crosscuts to exact length.",
            "Page order is the cutting order: " + ", ".join(SHEET_ORDER) + ". Parts are sawn to finished length.",
            "Tick the boxes as you go. Tape-label each part right after its cut (LABELS, below).",
        ]),
        ("SETUP", [
            f"3/4 in stock measured {MEASURED_34[0]}-{MEASURED_34[1]} in; caliper each sheet before cutting.",
            "1/2 in (S07) and 1/4 in (S08) stock is not bought or measured yet: caliper it when bought.",
            "Blade: 60-80 tooth ATB plywood blade, riving knife on, zero-clearance insert.",
            "Good face UP on the table saw (teeth exit the bottom). Good face DOWN with a circular saw.",
            "Full sheets: outfeed support and a helper. Longest rip fence setting is "
            f"{inches(widest[0])} in ({widest[1]}); 3/4 in sheets top out at 21 3/8 in (door panels).",
            "Crosscuts: M03-M06 (85 1/4 in) and L06 (28 7/16 x 59 15/16) come off 96 in strips, so use a "
            "circular saw with a clamped straightedge. Other strips (up to 21 1/8 in wide) need a sled of "
            "22 in or more, or the same saw and straightedge.",
            "Test-cut an offcut and measure it before the first real cut; re-check the fence after each move.",
        ]),
        ("AFTER SAWING", [
            "Bookcase top, bottom and fixed shelf join the sides like the bed: 2 dowels + 3 #8 x 2 in screws per "
            "joint, no dados or routing. Dowel holes 1/2 in into the side face, 1 1/16 in into the panel edge. "
            "How the 1/4 in back attaches is still open.",
            "Shelf-pin holes (5 mm), dowel holes and the Rockler bed holes (27/64 in inserts, screws) are drilled by hand.",
            "M07 stop: thin from about 0.71 to 5/8 in with a planer or sander, or use 5/8 in stock.",
        ]),
    ]
    for head, lines in sections:
        y = heading(page, 36, y, head)
        for text in lines:
            y = item(page, 44, y, text, width=100, bullet="-")
        y -= 8
    order_y = y
    y = heading(page, 36, y, "SHEET ORDER AND CONTENTS")
    for text in ("S02  M05, M06 headboards; M07 stop blank",
                 "S05  M08, M09 door panels; L09 adjustable shelf 2",
                 "S06  M10, M11 door panels; L10 adjustable shelf 3",
                 "S01  M03 top, M04 bottom; L16 drawer face; L05 plinth",
                 "S03  M01, M02 bed sides; L03 top, L04 bottom",
                 "S04  L01, L02 bookcase sides; L07 fixed shelf; L08 adjustable shelf 1",
                 "S07  1/2 in: L11, L12 drawer sides; L13 drawer back; L14 drawer inner front",
                 "S08  1/4 in: L06 bookcase back; L15 drawer bottom"):
        page.text(44, y, text, BODY)
        y -= LINE
    y -= 8
    y = heading(page, 36, y, "LABELS")
    for text in (
        "Label each part the moment it leaves the saw, before the next cut. These sizes repeat, so "
        "unlabeled parts get mixed up: M03-M06 (16 x 85 1/4); M01, M02, L01, L02 (16 x 64: bed sides "
        "vs bookcase sides); M08-M11 (doors); L08-L10 (shelves); L03/L04; L11/L12 and L13/L14 (drawer).",
        "Use low-tack painter's tape on the HIDDEN face and pencil on the tape (marker bleeds through "
        "paint; peel the tape before finishing). Hidden face = the non-good face; shelves: the "
        "underside; doors: the inside. The show face stays blank, so no separate good-face mark.",
        "Tape text, three lines: ID with the Rockler kit number, the part name, and an arrow to the TOP "
        "end as assembled. Also pencil the ID on one short end edge so stacks can be read.",
        "Add a fourth line only where it prevents a mistake: FRONT edge tick on L01, L02, L07 (hole "
        "layout starts from the front); M07 THIN TO 5/8.",
        "Each sheet page prints the exact tape text for its parts under PARTS OUT.",
    ):
        y = item(page, 44, y, text, width=100, bullet="-")
    require(y >= 70, f"overview runs into the footer (y={y})")
    bx, by = 396, order_y - 42        # sample tape label, beside the sheet-order list
    page.rectangle(bx, by, 180, 50)
    page.text(bx + 8, by + 34, "M05 (kit 3)", 12, True)
    page.text(bx + 8, by + 20, "UPPER HEADBOARD", BODY)
    page.text(bx + 8, by + 6, "arrow to TOP", BODY)
    ax = bx + 156
    page.line(ax, by + 8, ax, by + 40)
    page.line(ax, by + 40, ax - 5, by + 32)
    page.line(ax, by + 40, ax + 5, by + 32)
    page.text(bx, by - 11, "Sample tape label. L01 adds a fourth", 8.5)
    page.text(bx, by - 21, "line: FRONT edge tick", 8.5)
    page.text(36, 55, SHOP_NOTE, 8)
    page.text(533, PAGE_NUM_Y, f"1 / {total}", 8)
    return page.bytes()


def table_saw_pdf(layout):
    by_id = {s["sheetId"]: s for s in layout["sheets"]}
    require(set(by_id) == set(SHEET_ORDER), f"Table-saw plan must cover exactly {sorted(by_id)}")
    plans = {sid: plan_sheet(by_id[sid]) for sid in SHEET_ORDER}
    widest = max((r["fence"], sid) for sid, plan in plans.items() for r in plan["rips"])
    total = len(SHEET_ORDER) + 1
    pages = [overview_page(total, widest)]
    for number_, sheet_id in enumerate(SHEET_ORDER, 2):
        pages.append(sheet_page(by_id[sheet_id], plans[sheet_id], number_, total))
    return pdf_from_pages(pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cut-list", type=Path, default=ROOT / "output/cabinet-cut-list.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "output/cut-lines/table-saw-plan-3-4.pdf")
    args = parser.parse_args()
    layout = build_layout(load_parts(args.cut_list))
    for sheet_id in SHEET_ORDER:
        sheet = next(s for s in layout["sheets"] if s["sheetId"] == sheet_id)
        plan = plan_sheet(sheet)
        print(f"{sheet_id}: rips " + ", ".join(fmt(r["fence"]) for r in plan["rips"])
              + f" | strips use {number(plan['used'])} of {sheet['widthInches']} in")
    args.output.write_bytes(table_saw_pdf(layout))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
