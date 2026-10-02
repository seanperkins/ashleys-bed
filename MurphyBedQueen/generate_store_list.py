#!/usr/bin/env python3
"""Write a one-page printable store shopping list from bill-of-materials.csv.

Quantities come from the BOM; this file only groups them by store section and
shortens the wording. Every BOM item must be listed below, so a BOM change that
is not reflected here fails loudly. Requires Pillow (text measurement only) and
the macOS Helvetica font; the PDF itself uses the standard Helvetica fonts.
"""
import csv
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
# Text measurement only. Helvetica on macOS; Liberation Sans (metric-compatible
# with Helvetica) elsewhere, so the one-page check gives the same answer.
FONTS = {
    'R': [('/System/Library/Fonts/Helvetica.ttc', 0), ('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 0)],
    'B': [('/System/Library/Fonts/Helvetica.ttc', 1), ('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 0)],
}
PAGE_W, PAGE_H, MARGIN = 612, 792, 34

# BOM item -> (store section, short line). {qty} and {unit} come from the BOM.
# None means the item is deliberately left off the store list.
ITEMS = {
    '3/4-inch cabinet-grade plywood': ('Lumber', '{qty} sheets 3/4 in plywood, 4 x 8 ft', 'Cabinet-grade, veneer core. No MDF, particleboard or melamine.'),
    '1/2-inch drawer-box plywood': ('Lumber', '{qty} project panel 1/2 in plywood, 2 x 4 ft', 'For the drawer box. Cabinet-grade.'),
    '1/4-inch plywood': ('Lumber', '{qty} sheet 1/4 in plywood, 4 x 8 ft', 'Bookcase back and drawer bottom.'),
    'Drawer slides': ('Hardware', '{qty} pair 14 in drawer slides', 'Full-extension, side-mount, ball-bearing; needs 1/2 in per side.'),
    'Shelf pins': ('Hardware', '{qty} shelf pins, 5 mm', 'Steel, flat or spoon style. 12 needed + spares.'),
    'Matching pulls': ('Hardware', '{qty} black bar pulls, about 6 in centers', 'Two for the bed doors, one for the drawer. Check screws are included.'),
    'Bookcase anti-tip restraints': ('Hardware', '{qty} furniture anti-tip kit', 'For the bookcase, rated for wood studs. Extra to the bed anchors.'),
    'Cabinet connector fasteners': ('Hardware', 'Optional: {qty} connector bolt sets', 'Joins bed and bookcase sides (about 1-1/2 in total). Not a wall anchor.'),
    '#8 x 2-inch wood/cabinet screws': ('Fasteners', '{qty} #8 x 2 in wood screws', 'Wood or cabinet screws, not drywall screws.'),
    '#8 x 1-1/4-inch wood screws': ('Fasteners', '{qty} #8 x 1-1/4 in wood screws', 'Permanent stop.'),
    '#8 x 1-inch washer-head wood screws': ('Fasteners', '{qty} #8 x 1 in washer-head wood screws', 'Drawer face.'),
    '#6 x 1-1/4-inch wood screws': ('Fasteners', '{qty} #6 x 1-1/4 in wood screws', 'Drawer box corners.'),
    '#6 x 3/4-inch panel-attachment screws': ('Fasteners', '{qty} #6 x 3/4 in pan or washer-head screws', 'Bookcase back into its rabbet; drawer bottom.'),
    '3/8 x 1-1/2-inch dowels': ('Fasteners', '{qty} fluted dowels, 3/8 x 1-1/2 in', 'Hardwood. 22 for the bed, 28 for the bookcase, rest spare.'),
    'Wood glue': ('Fasteners', '{qty} bottle wood glue, 16 oz', 'Interior PVA.'),
    'Removable threadlocker': ('Fasteners', '{qty} small bottle removable threadlocker', 'Blue / removable strength.'),
    'Noncompressible shims': ('Fasteners', '{qty} pack hard cabinet shims', 'Plastic or composite, not soft wood.'),
    'Slide mounting screws': None,  # supplied with the slides
    'Paintable wood filler': ('Paint', '{qty} quart paintable wood filler', 'Sandable; for plywood edges and screw holes.'),
    'Compatible wood primer': ('Paint', '{qty} gallon primer', 'Suited to plywood and the enamel you choose.'),
    'Dark navy cabinet enamel': ('Paint', '{qty} gallons navy cabinet enamel', 'Match #182B49; check a dried sample first.'),
    'Clear drawer-box finish': ('Paint', 'Optional: {qty} quart clear water-based finish', 'Drawer box only.'),
    'Sandpaper or sanding discs': ('Paint', '{qty} packs sandpaper: 120, 180, 220 grit', 'Match your sander.'),
    'Painting consumables': ('Paint', 'Painting supplies', 'Brushes/rollers, tray liners, masking tape, drop cloth, rags.'),
    'Rockler I-Semble horizontal queen steel-frame Murphy bed kit': ('Elsewhere', 'Rockler I-Semble HORIZONTAL QUEEN bed kit', 'Rockler only. Not a vertical kit.'),
    'Queen mattress': ('Elsewhere', 'Queen mattress (you supply)', '60 x 80 in, 10 in thick max, 132 lb max, not foam or very light.'),
    'Sheet-cutting, routing and safety equipment': None,  # covered by TOOLS below
    'Permanent-stop material': None,  # cut from the 3/4 in sheets
    'Drilling and doweling equipment': None,  # covered by TOOLS below
    'Assembly and installation tools': None,
}
SECTIONS = [
    ('Lumber', 'LUMBER  -  buy full sheets; the sheet layout assumes full 4 x 8 ft sheets'),
    ('Hardware', 'HARDWARE'),
    ('Fasteners', 'FASTENERS, GLUE & SHIMS'),
    ('Paint', 'PAINT & FINISHING'),
    ('Tools', 'TOOLS  -  only if you do not already have them or cannot borrow them'),
    ('Elsewhere', 'NOT FROM THIS STORE'),
]
TOOLS = [
    ('8 mm Allen key', 'Drives the threaded inserts. The kit does not include this size.'),
    ('3/8 in doweling jig + dowel centers', 'Self-centering jig for edge holes; a set of dowel centers to mark the mating faces.'),
    ('Drill bits', '3/8 brad-point with depth collar; 5/64, 1/8, 5/32, 3/16, 13/64, 5/16, 27/64 in; #8 countersink.'),
    ('Plywood blade, straightedge, rabbeting bit', '40-tooth+ circular saw blade; 8 ft straightedge or track; bearing-guided 3/8 in rabbeting bit.'),
    ('4 bar or pipe clamps, 36 in+', 'Bookcase glue-up. Plus square, level, stud finder. Do not use an impact driver.'),
]
CHECKS = [
    'Sheets lie flat, faces have no dents or splits, and edges show no large voids.',
    'Measure one sheet of each thickness with calipers and write it down; it sets final joinery and fit.',
    'Pulls and slides: check the screws are in the package before leaving.',
]
NOTE = ('Planning quantities from the project bill of materials. Confirm the slide model, '
        'pull centers and shelf pins against the build guide before buying hardware.')


class Pdf:
    def __init__(self):
        self.ops = []
        self.measure = {w: self._font(w) for w in 'RB'}

    @staticmethod
    def _font(weight):
        for path, index in FONTS[weight]:
            if Path(path).exists():
                return ImageFont.truetype(path, 1000, index=index)
        raise FileNotFoundError(f'No measuring font found for weight {weight}: {FONTS[weight]}')

    def width(self, text, size, weight='R'):
        return self.measure[weight].getlength(text) * size / 1000

    def text(self, x, y, value, size, weight='R', grey=0):
        safe = value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        self.ops.append(f'BT {grey} g /F{weight} {size} Tf {x:.2f} {PAGE_H - y:.2f} Td ({safe}) Tj ET')

    def box(self, x, y, size):
        self.ops.append(f'0.8 w 0 G {x:.2f} {PAGE_H - y - size:.2f} {size} {size} re S')

    def rule(self, y, grey=0):
        self.ops.append(f'{grey} G 0.6 w {MARGIN} {PAGE_H - y:.2f} m {PAGE_W - MARGIN} {PAGE_H - y:.2f} l S')

    def wrap(self, value, size, width, weight='R'):
        lines, line = [], ''
        for word in value.split():
            trial = (line + ' ' + word).strip()
            if line and self.width(trial, size, weight) > width:
                lines.append(line)
                line = word
            else:
                line = trial
        return lines + [line] if line else lines

    def save(self, path):
        stream = '\n'.join(self.ops).encode('latin-1')
        objects = [
            b'<< /Type /Catalog /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] '
            f'/Resources << /Font << /FR 5 0 R /FB 6 0 R >> >> /Contents 4 0 R >>'.encode(),
            b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>',
        ]
        body, offsets = bytearray(b'%PDF-1.4\n'), []
        for number, obj in enumerate(objects, 1):
            offsets.append(len(body))
            body += b'%d 0 obj\n' % number + obj + b'\nendobj\n'
        xref = len(body)
        body += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1)
        body += b''.join(b'%010d 00000 n \n' % o for o in offsets)
        body += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objects) + 1, xref)
        path.write_bytes(bytes(body))


def load_rows():
    with (OUT / 'bill-of-materials.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    names = [r['Item'] for r in rows]
    missing, stale = set(names) - set(ITEMS), set(ITEMS) - set(names)
    if missing or stale:
        raise ValueError(f'Update generate_store_list.py ITEMS. New BOM items: {sorted(missing)}; '
                         f'removed: {sorted(stale)}')
    grouped = {key: [] for key, _ in SECTIONS}
    for row in rows:
        entry = ITEMS[row['Item']]
        if entry is None:
            continue
        section, line, detail = entry
        if '{qty}' in line and not row['Buy_quantity'].isdigit():
            raise ValueError(f'Non-numeric BOM quantity for {row["Item"]}')
        grouped[section].append((line.format(qty=row['Buy_quantity'], unit=row['Unit']), detail))
    grouped['Tools'] = TOOLS
    return grouped


def main():
    grouped = load_rows()
    pdf = Pdf()
    y = MARGIN + 4
    pdf.text(MARGIN, y + 14, "Ashley's Murphy bed  -  store shopping list", 17, 'B')
    y += 24
    pdf.text(MARGIN, y + 9, 'Queen horizontal bed (86-3/4 in) + left bookcase (30 in). Check each box as it goes in the cart.', 9.5, grey=0.3)
    y += 14
    for line in pdf.wrap(NOTE, 8.5, PAGE_W - 2 * MARGIN):
        pdf.text(MARGIN, y + 8, line, 8.5, grey=0.3)
        y += 11
    y += 4
    column = 235
    for key, title in SECTIONS:
        y += 4
        pdf.text(MARGIN, y + 9, title, 9.5, 'B')
        y += 13
        pdf.rule(y, 0.6)
        y += 5
        for line, detail in grouped[key]:
            pdf.box(MARGIN, y, 8.5)
            name_lines = pdf.wrap(line, 9.5, column - 18, 'B')
            detail_lines = pdf.wrap(detail, 8.5, PAGE_W - 2 * MARGIN - column)
            for i, part in enumerate(name_lines):
                pdf.text(MARGIN + 15, y + 8 + i * 12, part, 9.5, 'B')
            for i, part in enumerate(detail_lines):
                pdf.text(MARGIN + column, y + 8 + i * 11, part, 8.5, grey=0.25)
            y += max(12 * len(name_lines), 11 * len(detail_lines)) + 2
    y += 6
    pdf.text(MARGIN, y + 9, 'BEFORE CHECKOUT', 9.5, 'B')
    y += 13
    pdf.rule(y, 0.6)
    y += 5
    for check in CHECKS:
        pdf.box(MARGIN, y, 8.5)
        for i, part in enumerate(pdf.wrap(check, 9, PAGE_W - 2 * MARGIN - 15)):
            pdf.text(MARGIN + 15, y + 8 + i * 11, part, 9)
            y += 11
        y += 4
    pdf.text(MARGIN, PAGE_H - MARGIN + 6, 'Full details: seanperkins.github.io/ashleys-bed/purchase.html', 8, grey=0.4)
    if y > PAGE_H - MARGIN - 12:
        raise ValueError(f'Store list overflows one page ({y:.0f} of {PAGE_H - MARGIN - 12} pt)')
    target = OUT / 'store-shopping-list.pdf'
    pdf.save(target)
    print(f'Wrote {target.relative_to(ROOT)}: {sum(len(v) for v in grouped.values())} items, '
          f'{y:.0f} of {PAGE_H - MARGIN - 12} pt used')


if __name__ == '__main__':
    main()
