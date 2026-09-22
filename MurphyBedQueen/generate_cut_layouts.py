#!/usr/bin/env python3
"""Generate the approved one-bookcase purchasing layout and nominal cut drawings.

Run with Python 3; only the standard library is required. These drawings are
planning geometry, not CNC toolpaths. Dimensions come from cabinet-cut-list.csv;
the fixed placement contract deliberately fails if that geometry changes.
"""

import argparse
import csv
import io
import json
import math
from collections import Counter
from fractions import Fraction
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARGIN = 0.75
GAP = 0.5
WARNING = "NOMINAL PLANNING OUTLINES - NOT CNC-READY"
STOP_NOTE = "M07 on S02: mill the 3/4 in stock blank to 5/8 in finished thickness."
PENDING_NOTE = (
    "Finalize joinery, shelf clearance, slides and measured stock thickness before cutting."
)
BASIS = (
    "Shared-sheet placement of all 27 current bed-plus-LEFT-cabinet wood parts; "
    "NOT CNC toolpaths or fabrication-ready joinery. Grain follows every part "
    "Length_in and stock length (+Y). Nominal rectangular outlines only; no "
    "cutter compensation, holes, pockets or G-code. No spare sheet is included. "
    + PENDING_NOTE
)

# Stable drawing IDs, source-name keys, short labels, width, length, finished thickness.
PART_SPECS = [
    ("M01", "1R Right side", "Bed right side", 16, 64, 0.75),
    ("M02", "1L Left side", "Bed left side", 16, 64, 0.75),
    ("M03", "2T Top", "Bed top", 16, 85.25, 0.75),
    ("M04", "2B Bottom", "Bed bottom", 16, 85.25, 0.75),
    ("M05", "3 Upper headboard", "Upper headboard", 16, 85.25, 0.75),
    ("M06", "4 Lower headboard", "Lower headboard", 16, 85.25, 0.75),
    ("M07", "6 Permanent stop", "Permanent stop", 3, 56, 0.625),
    ("M08", "5.1 Door panel", "Door panel 5.1", 21.125, 61.8125, 0.75),
    ("M09", "5.2 Door panel", "Door panel 5.2", 21.125, 61.8125, 0.75),
    ("M10", "5.3 Door panel", "Door panel 5.3", 21.125, 61.8125, 0.75),
    ("M11", "5.4 Door panel", "Door panel 5.4", 21.125, 61.8125, 0.75),
    ("L01", "Left cabinet: Left side", "Left bookcase left side", 16, 64, 0.75),
    ("L02", "Left cabinet: Right side", "Left bookcase right side", 16, 64, 0.75),
    ("L03", "Left cabinet: Top", "Left bookcase top", 16, 28.5, 0.75),
    ("L04", "Left cabinet: Bottom", "Left bookcase bottom", 16, 28.5, 0.75),
    ("L05", "Left cabinet: Recessed plinth", "Recessed plinth", 2.5, 28.5, 0.75),
    ("L06", "Left cabinet: Plywood back", "Bookcase back", 28.5, 60, 0.25),
    ("L07", "Left cabinet: Shelf above drawer", "Shelf above drawer", 15.75, 28.5, 0.75),
    ("L08", "Left cabinet: Shelf 1", "Adjustable shelf 1", 15.75, 28.5, 0.75),
    ("L09", "Left cabinet: Shelf 2", "Adjustable shelf 2", 15.75, 28.5, 0.75),
    ("L10", "Left cabinet: Shelf 3", "Adjustable shelf 3", 15.75, 28.5, 0.75),
    ("L11", "Left cabinet: Drawer Left side", "Drawer left side", 8, 14, 0.5),
    ("L12", "Left cabinet: Drawer Right side", "Drawer right side", 8, 14, 0.5),
    ("L13", "Left cabinet: Drawer back", "Drawer back", 8, 26.5, 0.5),
    ("L14", "Left cabinet: Drawer inner front", "Drawer inner front", 8, 26.5, 0.5),
    ("L15", "Left cabinet: Drawer bottom", "Drawer bottom", 14, 27.5, 0.25),
    ("L16", "Left cabinet: Drawer face", "Drawer face", 10.5, 28.25, 0.75),
]

# Stock thickness, width, length, then (part ID, lower-left X, lower-left Y).
# Every part length stays parallel to stock length; nothing is rotated to fit.
SHEET_PLAN = [
    (0.75, 48, 96, [("M03", 0.75, 0.75), ("M04", 17.25, 0.75),
                    ("L16", 33.75, 0.75), ("L05", 44.75, 0.75)]),
    (0.75, 48, 96, [("M05", 0.75, 0.75), ("M06", 17.25, 0.75),
                    ("M07", 33.75, 0.75)]),
    (0.75, 48, 96, [("M01", 0.75, 0.75), ("M02", 17.25, 0.75),
                    ("L03", 0.75, 65.25), ("L04", 17.25, 65.25)]),
    (0.75, 48, 96, [("L01", 0.75, 0.75), ("L02", 17.25, 0.75),
                    ("L07", 0.75, 65.25), ("L08", 17.25, 65.25)]),
    (0.75, 48, 96, [("M08", 0.75, 0.75), ("M09", 22.375, 0.75),
                    ("L09", 0.75, 63.0625)]),
    (0.75, 48, 96, [("M10", 0.75, 0.75), ("M11", 22.375, 0.75),
                    ("L10", 0.75, 63.0625)]),
    (0.5, 24, 48, [("L13", 0.75, 0.75), ("L14", 9.25, 0.75),
                   ("L11", 0.75, 27.75), ("L12", 9.25, 27.75)]),
    (0.25, 48, 96, [("L06", 0.75, 0.75), ("L15", 29.75, 0.75)]),
]


def require(condition, message):
    """Keep geometry assertions active even under python -O."""
    if not condition:
        raise ValueError(message)


def number(value):
    return format(value, ".8g")


def inches(value):
    whole, numerator = divmod(Fraction(value).limit_denominator(64).numerator,
                              Fraction(value).limit_denominator(64).denominator)
    denominator = Fraction(value).limit_denominator(64).denominator
    if not numerator:
        return str(whole)
    return (str(whole) + " " if whole else "") + f"{numerator}/{denominator}"


def part_key(name):
    return name.split(" |", 1)[0].split(" —", 1)[0]


def load_parts(path):
    expected = {key: (pid, label, w, length, thickness)
                for pid, key, label, w, length, thickness in PART_SPECS}
    parts = {}
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            name = row["Part"]
            key = part_key(name)
            require(key in expected, f"Unplanned source part: {name}")
            pid, label, expected_w, expected_l, expected_t = expected[key]
            require(pid not in parts, f"Duplicate source part: {name}")
            require(int(row["Quantity"]) == 1, f"Expected quantity 1 for {name}")
            width, length, thickness = (
                float(row[field]) for field in ("Width_in", "Length_in", "Thickness_in")
            )
            require(all(math.isfinite(v) and v > 0 for v in (width, length, thickness)),
                    f"Non-positive or non-finite dimensions: {name}")
            require((width, length, thickness) == (expected_w, expected_l, expected_t),
                    f"Source dimensions changed for {name}: "
                    f"{width} x {length} x {thickness}; revise the approved layout first")
            parts[pid] = {
                "partId": pid, "part": name, "label": label,
                "assembly": "Left shelf" if name.startswith("Left cabinet:") else "Main cabinet",
                "widthInches": width, "lengthInches": length,
                "finishedThicknessInches": thickness,
                "grainAxis": "+Y", "rotationDegrees": 0,
            }
    require(set(parts) == {spec[0] for spec in PART_SPECS},
            "Cut list is missing one or more of the 27 approved parts")
    require(Counter(p["finishedThicknessInches"] for p in parts.values())
            == {0.75: 20, 0.625: 1, 0.5: 4, 0.25: 2}, "Unexpected material counts")
    return parts


def build_layout(parts):
    sheets = []
    seen = []
    for index, (thickness, width, length, placements) in enumerate(SHEET_PLAN, 1):
        sheet = {
            "sheetId": f"S{index:02d}", "stockThicknessInches": thickness,
            "widthInches": width, "lengthInches": length, "grainAxis": "+Y",
            "stockType": "project panel" if index == 7 else "full sheet",
            "purchaseId": {0.75: "P01", 0.5: "P02", 0.25: "P03"}[thickness],
            "parts": [],
        }
        for pid, x, y in placements:
            part = dict(parts[pid], xInches=x, yInches=y)
            w, height = part["widthInches"], part["lengthInches"]
            require(x >= MARGIN and y >= MARGIN and
                    x + w <= width - MARGIN and y + height <= length - MARGIN,
                    f"Edge-margin violation on {sheet['sheetId']}: {pid}")
            stock_t = 0.75 if part["finishedThicknessInches"] == 0.625 else part["finishedThicknessInches"]
            require(stock_t == thickness, f"Wrong stock thickness for {pid}")
            for other in sheet["parts"]:
                separated = (
                    x + w + GAP <= other["xInches"] or
                    other["xInches"] + other["widthInches"] + GAP <= x or
                    y + height + GAP <= other["yInches"] or
                    other["yInches"] + other["lengthInches"] + GAP <= y
                )
                require(separated, f"Collision/gap violation: {pid} / {other['partId']}")
            sheet["parts"].append(part)
            seen.append(pid)
        sheet["assemblies"] = sorted({p["assembly"] for p in sheet["parts"]})
        sheet["shared"] = len(sheet["assemblies"]) > 1
        sheets.append(sheet)
    require(Counter(seen) == Counter(parts.keys()), "Each of 27 parts must appear exactly once")
    require(Counter((s["stockThicknessInches"], s["widthInches"], s["lengthInches"])
                    for s in sheets)
            == {(0.75, 48, 96): 6, (0.5, 24, 48): 1, (0.25, 48, 96): 1},
            "Expected six full 3/4 sheets, one 24x48 half-inch panel, one full quarter sheet")
    return {
        "schemaVersion": 2, "basis": BASIS,
        "units": "inches", "coordinateSystem": "Stock lower-left origin; +X across width; +Y along length/grain",
        "edgeMarginInches": MARGIN, "partGapInches": GAP,
        "stopBlank": STOP_NOTE, "partCount": len(seen), "sheetCount": len(sheets),
        "machineReady": False,
        "machiningStatus": "Nominal rectangles only; joinery and machine setup unresolved",
        "dxfLayers": {
            "PART_OUTLINES": "Closed nominal part boundaries, uncompensated",
            "STOCK_REFERENCE": "Stock boundary; do not cut",
            "MARGIN_REFERENCE": "3/4-inch edge clearance; do not cut",
            "GRAIN_REFERENCE": "Grain-direction arrow; do not cut",
            "LABELS": "Part IDs, dimensions and planning warnings; do not cut",
        },
        "sheets": sheets,
    }


def project_csv(layout):
    fields = [
        "Assembly", "Stock_thickness_in", "Part", "Quantity", "Finished_thickness_in",
        "Width_in", "Length_in", "Source_sheet_ID", "Sheet_shared_with",
        "Layout_sheet_width_in", "Layout_sheet_length_in", "X_in", "Y_in", "Purchase_ID",
        "Notes", "Part_ID",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    entries = [(sheet, part) for sheet in layout["sheets"] for part in sheet["parts"]]
    entries.sort(key=lambda entry: (entry[1]["assembly"] != "Main cabinet",
                                    entry[0]["sheetId"], entry[1]["partId"]))
    for sheet, part in entries:
        note = "Nominal planning layout, NOT CNC-ready. Grain along Length_in and stock length."
        if part["partId"] == "M07":
            note += " " + STOP_NOTE
        if sheet["sheetId"] == "S07":
            note += " One 24 x 48 project panel for the LEFT drawer; confirm grain along 48-inch length."
        writer.writerow({
            "Assembly": part["assembly"], "Stock_thickness_in": sheet["stockThicknessInches"],
            "Part": part["part"], "Quantity": 1,
            "Finished_thickness_in": part["finishedThicknessInches"],
            "Width_in": part["widthInches"], "Length_in": part["lengthInches"],
            "Source_sheet_ID": sheet["sheetId"],
            "Sheet_shared_with": "; ".join(a for a in sheet["assemblies"] if a != part["assembly"]),
            "Layout_sheet_width_in": sheet["widthInches"], "Layout_sheet_length_in": sheet["lengthInches"],
            "X_in": part["xInches"], "Y_in": part["yInches"], "Purchase_ID": sheet["purchaseId"],
            "Notes": note, "Part_ID": part["partId"],
        })
    return stream.getvalue()


def part_dimensions(part):
    return f"{inches(part['widthInches'])} x {inches(part['lengthInches'])} in"


def stock_title(sheet):
    return (f"{sheet['sheetId']} | {inches(sheet['stockThicknessInches'])} in stock | "
            f"{sheet['widthInches']} x {sheet['lengthInches']} in | {len(sheet['parts'])} parts")


def svg_document(sheet):
    w, length = sheet["widthInches"], sheet["lengthInches"]
    canvas_w, canvas_h = w + 28, length + 14
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}in" height="{canvas_h}in" '
        f'viewBox="-2 -8 {canvas_w} {canvas_h}">',
        f'<title>{escape(stock_title(sheet))} - {WARNING}</title>',
        '<desc>Full-scale inches: one SVG unit equals one inch. Stock lower-left '
        'origin, +Y along grain. Only PART_OUTLINES contains nominal part boundaries.</desc>',
        '<rect x="-2" y="-8" width="100%" height="100%" fill="white"/>',
        '<g font-family="Arial, sans-serif" fill="#152b42">',
        f'<text x="0" y="-5.6" font-size="1.5" font-weight="bold">{escape(stock_title(sheet))}</text>',
        f'<text x="0" y="-3.5" font-size="0.95" fill="#943518">{WARNING}</text>',
        '<text x="0" y="-1.6" font-size="0.8">Full scale: 1 unit = 1 inch. Sheet border and notes are reference only.</text>',
        f'<g id="STOCK_REFERENCE"><rect x="0" y="0" width="{w}" height="{length}" '
        'fill="none" stroke="#152b42" stroke-width="0.12"/></g>',
        f'<g id="MARGIN_REFERENCE"><rect x="{MARGIN}" y="{MARGIN}" '
        f'width="{w - 2 * MARGIN}" height="{length - 2 * MARGIN}" '
        'fill="none" stroke="#888" stroke-width="0.06" stroke-dasharray="0.5 0.35"/></g>',
        '<g id="PART_OUTLINES" stroke="#152b42" stroke-width="0.08">',
    ]
    for part in sheet["parts"]:
        fill = "#e0ebf3" if part["assembly"] == "Main cabinet" else "#e6efdf"
        lines.append(f'<rect id="{part["partId"]}" x="{part["xInches"]}" '
                     f'y="{number(length - part["yInches"] - part["lengthInches"])}" '
                     f'width="{part["widthInches"]}" height="{part["lengthInches"]}" fill="{fill}"/>')
    lines.append('</g><g id="LABELS" text-anchor="middle">')
    for part in sheet["parts"]:
        x = part["xInches"] + part["widthInches"] / 2
        y = length - part["yInches"] - part["lengthInches"] / 2
        rotation = f' transform="rotate(-90 {number(x)} {number(y)})"' if part["widthInches"] < 5 else ""
        lines.append(f'<g{rotation}><text x="{number(x)}" y="{number(y - 0.3)}" '
                     f'font-size="1.2" font-weight="bold">{part["partId"]}</text>'
                     f'<text x="{number(x)}" y="{number(y + 1.1)}" font-size="0.72">'
                     f'{part_dimensions(part)}</text></g>')
    legend_x = w + 4
    lines += [
        '</g><g id="GRAIN_REFERENCE" stroke="#152b42" stroke-width="0.12" fill="none">',
        f'<path d="M {w + 1.5} 14 V 4 M {w + 0.9} 5 L {w + 1.5} 4 L {w + 2.1} 5"/>',
        '</g>',
        f'<text x="{legend_x}" y="4" font-size="0.95" font-weight="bold">GRAIN +Y / STOCK LENGTH</text>',
        f'<text x="{legend_x}" y="6" font-size="0.85">3/4 in edge margin; 1/2 in part gap</text>',
        f'<text x="{legend_x}" y="8" font-size="0.8">Dimensions: width x length</text>',
        f'<text x="{legend_x}" y="10" font-size="0.8">X/Y measured from stock lower-left</text>',
    ]
    for index, part in enumerate(sheet["parts"]):
        y = 14 + index * 6
        lines.extend([
            f'<text x="{legend_x}" y="{y}" font-size="0.95" font-weight="bold">{part["partId"]}  {escape(part["label"])}</text>',
            f'<text x="{legend_x}" y="{y + 1.6}" font-size="0.85">{part_dimensions(part)}; finish {inches(part["finishedThicknessInches"])} in</text>',
            f'<text x="{legend_x}" y="{y + 3}" font-size="0.78">X {number(part["xInches"])} / Y {number(part["yInches"])} in</text>',
        ])
    lines.extend([
        f'<text x="0" y="{length + 1.7}" font-size="0.8">{escape(STOP_NOTE)}</text>',
        f'<text x="0" y="{length + 3.3}" font-size="0.75">{escape(PENDING_NOTE)}</text>',
        f'<text x="0" y="{length + 4.9}" font-size="0.75">No cutter compensation, holes, pockets or G-code. Confirm cutter, workholding and machine/post setup.</text>',
        '</g></svg>',
    ])
    return "\n".join(lines) + "\n"


def dxf_document(sheet):
    pairs = []

    def emit(*values):
        pairs.extend(str(value) for value in values)

    def rectangle(layer, x, y, w, height):
        emit(0, "LWPOLYLINE", 100, "AcDbEntity", 8, layer, 100, "AcDbPolyline",
             90, 4, 70, 1, 38, 0)
        for px, py in ((x, y), (x + w, y), (x + w, y + height), (x, y + height)):
            emit(10, number(px), 20, number(py))

    def text(x, y, value, height=0.8, angle=0):
        emit(0, "TEXT", 100, "AcDbEntity", 8, "LABELS", 100, "AcDbText",
             10, number(x), 20, number(y), 30, 0, 40, height, 1, value,
             50, angle, 7, "STANDARD", 100, "AcDbText")

    def line(x1, y1, x2, y2):
        emit(0, "LINE", 100, "AcDbEntity", 8, "GRAIN_REFERENCE", 100, "AcDbLine",
             10, x1, 20, y1, 30, 0, 11, x2, 21, y2, 31, 0)

    w, length = sheet["widthInches"], sheet["lengthInches"]
    emit(0, "SECTION", 2, "HEADER", 9, "$ACADVER", 1, "AC1015",
         9, "$INSUNITS", 70, 1, 9, "$MEASUREMENT", 70, 0,
         9, "$LUNITS", 70, 2, 9, "$LUPREC", 70, 4,
         9, "$INSBASE", 10, 0, 20, 0, 30, 0, 0, "ENDSEC")
    emit(0, "SECTION", 2, "TABLES", 0, "TABLE", 2, "LTYPE", 70, 1,
         0, "LTYPE", 2, "CONTINUOUS", 70, 0, 3, "Solid line", 72, 65, 73, 0, 40, 0,
         0, "ENDTAB", 0, "TABLE", 2, "LAYER", 70, 5)
    for layer, color in (("PART_OUTLINES", 7), ("STOCK_REFERENCE", 8),
                         ("MARGIN_REFERENCE", 8), ("LABELS", 3), ("GRAIN_REFERENCE", 5)):
        emit(0, "LAYER", 2, layer, 70, 0, 62, color, 6, "CONTINUOUS")
    emit(0, "ENDTAB", 0, "TABLE", 2, "STYLE", 70, 1,
         0, "STYLE", 2, "STANDARD", 70, 0, 40, 0, 41, 1, 50, 0, 71, 0,
         42, 0.8, 3, "txt", 4, "", 0, "ENDTAB", 0, "ENDSEC",
         0, "SECTION", 2, "ENTITIES")
    rectangle("STOCK_REFERENCE", 0, 0, w, length)
    rectangle("MARGIN_REFERENCE", MARGIN, MARGIN, w - 2 * MARGIN, length - 2 * MARGIN)
    for part in sheet["parts"]:
        x, y = part["xInches"], part["yInches"]
        pw, pl = part["widthInches"], part["lengthInches"]
        rectangle("PART_OUTLINES", x, y, pw, pl)
        if pw < 5:
            text(x + pw / 2, y + 1, f"{part['partId']} | {part_dimensions(part)}", 0.7, 90)
        else:
            text(x + 0.5, y + pl / 2, part["partId"], 1)
            text(x + 0.5, y + pl / 2 - 1.2, part_dimensions(part), 0.7)
    text(0, length + 5, stock_title(sheet), 1.2)
    text(0, length + 3, WARNING, 1)
    text(0, length + 1.4, "INCHES / 1:1. Only PART_OUTLINES are nominal part boundaries.")
    line(w + 2, length - 14, w + 2, length - 4)
    line(w + 1.4, length - 5, w + 2, length - 4)
    line(w + 2.6, length - 5, w + 2, length - 4)
    text(w + 4, length - 4, "GRAIN +Y / STOCK LENGTH")
    text(w + 4, length - 6, "3/4 in edge margin; 1/2 in gap")
    for index, part in enumerate(sheet["parts"]):
        y = length - 10 - index * 5
        text(w + 4, y, f"{part['partId']}  {part['label']}", 0.9)
        text(w + 4, y - 1.5, f"{part_dimensions(part)}; finish {inches(part['finishedThicknessInches'])} in")
        text(w + 4, y - 3, f"X {number(part['xInches'])} / Y {number(part['yInches'])} in", 0.7)
    text(0, -2, STOP_NOTE)
    text(0, -3.5, PENDING_NOTE)
    text(0, -5, "No cutter compensation, holes, pockets or G-code. Reference layers are NOT cut paths.")
    emit(0, "ENDSEC", 0, "EOF")
    return "\n".join(pairs) + "\n"


class PdfPage:
    """Small vector page writer: coordinates are PDF points, not stock inches."""

    def __init__(self):
        self.commands = []

    def text(self, x, y, value, size=10, bold=False, angle=0):
        value = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        matrix = "0 1 -1 0" if angle == 90 else "1 0 0 1"
        self.commands.append(f"BT /{'F2' if bold else 'F1'} {size} Tf "
                             f"{matrix} {number(x)} {number(y)} Tm ({value}) Tj ET")

    def line(self, x1, y1, x2, y2):
        self.commands.append(f"{number(x1)} {number(y1)} m {number(x2)} {number(y2)} l S")

    def rectangle(self, x, y, width, height, fill=None, dashed=False):
        self.commands.append("q")
        self.commands.append("[3 2] 0 d" if dashed else "[] 0 d")
        if fill:
            self.commands.append(f"{fill} rg")
        self.commands.append(f"{number(x)} {number(y)} {number(width)} {number(height)} re "
                             + ("B" if fill else "S"))
        self.commands.append("Q")

    def bytes(self):
        return ("\n".join(self.commands) + "\n").encode("cp1252")


def booklet_page(sheet, page_number):
    page = PdfPage()
    page.commands.extend(["0.08 0.16 0.24 RG", "0.08 0.16 0.24 rg", "0.7 w"])
    page.text(36, 755, "ASHLEY'S MURPHY BED + LEFT BOOKCASE", 17, True)
    page.text(36, 730, stock_title(sheet), 13, True)
    page.text(36, 710, WARNING, 11, True)
    page.text(36, 692, "3/4 in edge margin | 1/2 in minimum part gap | Grain parallel to every part length", 9)
    scale = 480 / sheet["lengthInches"]
    ox, oy = 36, 190
    sw, sl = sheet["widthInches"], sheet["lengthInches"]
    page.rectangle(ox, oy, sw * scale, sl * scale)
    page.rectangle(ox + MARGIN * scale, oy + MARGIN * scale,
                   (sw - 2 * MARGIN) * scale, (sl - 2 * MARGIN) * scale, dashed=True)
    for part in sheet["parts"]:
        x = ox + part["xInches"] * scale
        y = oy + part["yInches"] * scale
        w, height = part["widthInches"] * scale, part["lengthInches"] * scale
        fill = "0.88 0.93 0.96" if part["assembly"] == "Main cabinet" else "0.90 0.94 0.87"
        page.rectangle(x, y, w, height, fill)
        if w < 28:
            page.text(x + w / 2 + 3, y + height / 2 - 10, part["partId"], 9, True, 90)
        else:
            page.text(x + w / 2 - 10, y + height / 2, part["partId"], 9, True)
    page.text(ox, oy - 17, f"Stock width {sw} in  /  length {sl} in", 9)
    page.text(ox, oy - 32, "Origin (0,0): lower-left stock corner", 8)
    page.line(291, 575, 291, 648)
    page.line(287, 640, 291, 648)
    page.line(295, 640, 291, 648)
    page.text(296, 586, "GRAIN +Y", 8, True, 90)
    page.text(315, 657, "PARTS ON THIS SHEET", 11, True)
    page.text(315, 642, "Dimensions in inches: width x length", 9)
    page.text(315, 627, "X / Y = lower-left nominal outline", 8)
    for index, part in enumerate(sheet["parts"]):
        y = 602 - index * 67
        page.text(315, y, f"{part['partId']}  {part['label']}", 9, True)
        page.text(315, y - 15, part_dimensions(part), 10)
        page.text(315, y - 29, f"Finished thickness: {inches(part['finishedThicknessInches'])} in", 8)
        page.text(315, y - 42, f"X {number(part['xInches'])} / Y {number(part['yInches'])}", 8)
    page.text(315, 290, "SHARED STOCK" if sheet["shared"] else "DEDICATED STOCK", 9, True)
    for index, assembly in enumerate(sheet["assemblies"]):
        page.text(315, 274 - index * 14, assembly, 9)
    page.text(315, 225, f"Drawing scale: 1:{number(72 / scale)}", 9, True)
    page.text(315, 211, "US Letter; print Actual Size / 100%.", 8)
    page.text(315, 197, "Use written dimensions, not a paper template.", 8)
    page.line(36, 142, 576, 142)
    page.text(36, 128, STOP_NOTE, 9, True)
    page.text(36, 110, PENDING_NOTE, 9)
    page.text(36, 94, "No cutter compensation, holes, pockets or G-code. Confirm cutter, workholding and post.", 9)
    page.text(36, 78, "DXF: inches, closed PART_OUTLINES. Stock/margin/grain/labels are reference only.", 9)
    page.text(36, 62, "SVG: full scale in inches, including a separate note area. PDF: reduced-scale planning booklet.", 8)
    page.text(36, 40, "27 parts | 6 full 3/4 sheets + 1 half-inch 24x48 panel + 1 full quarter-inch sheet | No spare", 8)
    page.text(533, 24, f"{page_number} / 8", 8)
    return page.bytes()


def pdf_document(layout):
    # Standard Helvetica fonts avoid third-party PDF/rendering dependencies.
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    page_ids = []
    for page_number, sheet in enumerate(layout["sheets"], 1):
        content = booklet_page(sheet, page_number)
        content_id = len(objects) + 1
        objects.append(b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
                       + content + b"endstream")
        page_id = len(objects) + 1
        objects.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                        f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                        f"/Contents {content_id} 0 R >>").encode("ascii"))
        page_ids.append(page_id)
    objects[1] = (f"<< /Type /Pages /Count {len(page_ids)} /Kids ["
                  + " ".join(f"{pid} 0 R" for pid in page_ids) + "] >>").encode("ascii")
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend((f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                   f"startxref\n{xref}\n%%EOF\n").encode("ascii"))
    return bytes(output)


def cut_guide(layout):
    lines = [
        "ASHLEY'S BED + LEFT BOOKCASE - CUT LAYOUT GUIDE", WARNING, "",
        "PURCHASE STOCK", "Six 48 x 96 x 3/4 in sheets: S01-S06.",
        "One 24 x 48 x 1/2 in project panel: S07.", "One 48 x 96 x 1/4 in sheet: S08.",
        "27 wood pieces total; no spare stock included. Keep shared sheets shared.", "",
        "COORDINATES AND SCALE", "All coordinates and dimensions are inches.",
        "Origin is stock lower-left; X across width, Y along length. Do not rotate parts.",
        "Confirm face grain runs along stock length, especially the 24 x 48 project panel.",
        "3/4 in minimum edge margin; 1/2 in minimum gap between nominal outlines.",
        "DXF and SVG: full-scale nominal geometry. SVG canvas also includes notes outside stock.",
        "PDF: 8 reduced-scale US Letter pages. Print Actual Size; use written dimensions.", "",
        "LAYER RULES", "PART_OUTLINES: closed nominal rectangular part boundaries only.",
        "STOCK_REFERENCE, MARGIN_REFERENCE, GRAIN_REFERENCE and LABELS: never cut.",
        "DXF declares inches ($INSUNITS=1); verify a known dimension after import.", "",
        "MILLING / MACHINING HOLD", STOP_NOTE, PENDING_NOTE,
        "No machining values are implied by the 1/2 in gap. It is layout clearance, not a tool size.",
        "No cutter compensation, joinery pockets, drilling, tabs or G-code are supplied.",
        "Measure stock; finalize dados/rabbets, shelf fit and drawer hardware before CAM.",
        "Confirm machine, approved post/profile, exact cutter, workholding and work zero with shop.",
        "Do not run these drawings as machine programs or treat nominal rectangles as final blanks.", "",
        "SHEET MAP (width x length; finished thickness; lower-left X/Y)",
    ]
    for sheet in layout["sheets"]:
        lines += ["", stock_title(sheet), "Assemblies: " + "; ".join(sheet["assemblies"])]
        for part in sheet["parts"]:
            lines.append(f"  {part['partId']} {part['part']} | {part_dimensions(part)} | "
                         f"finish {inches(part['finishedThicknessInches'])} in | "
                         f"X {number(part['xInches'])}, Y {number(part['yInches'])}")
    lines += ["", "REGENERATE", "python3 MurphyBedQueen/generate_cut_layouts.py",
              "Reads output/cabinet-cut-list.csv; excludes only names beginning 'Right cabinet:'.",
              "Asserts approved dimensions, material counts, margin/gap and one placement per part.",
              "Writes only layout JSON, project allocation CSV and output/cut-lines deliverables."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cut-list", type=Path, default=ROOT / "output/cabinet-cut-list.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    layout = build_layout(load_parts(args.cut_list))
    # Construct every file before writing, so a drawing-generation error cannot
    # publish a partially regenerated set. Geometry assertions run before this.
    artifacts = {
        "plywood-purchasing-layout.json": (json.dumps(layout, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        "plywood-by-project.csv": project_csv(layout).encode("utf-8"),
        "cut-lines/cut-layout-booklet.pdf": pdf_document(layout),
        "cut-lines/cut-guide.txt": cut_guide(layout).encode("utf-8"),
    }
    for sheet in layout["sheets"]:
        stem = f"cut-lines/{sheet['sheetId']}"
        artifacts[stem + ".dxf"] = dxf_document(sheet).encode("ascii")
        artifacts[stem + ".svg"] = svg_document(sheet).encode("utf-8")
    for relative, content in artifacts.items():
        target = args.output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    print(f"Generated {layout['sheetCount']} sheets / {layout['partCount']} parts: "
          "6 full 3/4 sheets, 1 half-inch 24x48 panel, 1 full quarter-inch sheet.")
    print("Dimension, thickness, completeness, grain orientation, margin and gap assertions passed.")
    print(f"Wrote {len(artifacts)} files under {args.output_dir.resolve()}")
    print(WARNING)


if __name__ == "__main__":
    main()
