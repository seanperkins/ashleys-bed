#!/usr/bin/env python3
"""Create design-review drawings from verified native Fusion body bounds.

Requires Pillow and output/drawing-geometry.json captured from the saved closed
Fusion archive. These are design drawings, not a machining release.
"""
import json
from html import escape
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
MEDIA = OUT / 'media'
WIDTH, HEIGHT = 2200, 1500
INK = '#182B49'
FONT = '/System/Library/Fonts/Helvetica.ttc'


def main():
    report = json.loads((OUT / 'build-result.json').read_text())
    geometry = json.loads((OUT / 'drawing-geometry.json').read_text())
    if set(report['sideCabinets']) != {'left'} or geometry['pose'] != 'closed':
        raise ValueError('Drawings require the verified left-only closed design')
    width, height, depth = report['combinedCarcassInchesWHD']
    drawing = Image.new('RGB', (WIDTH, HEIGHT), 'white')
    pen = ImageDraw.Draw(drawing)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}">',
           '<rect width="100%" height="100%" fill="white"/>']

    def line(x1, y1, x2, y2, color=INK, weight=3):
        pen.line((x1, y1, x2, y2), fill=color, width=weight)
        svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{weight}"/>')

    def text(x, y, value, size=28, centered=False):
        font = ImageFont.truetype(FONT, size)
        pen.text((x, y), value, font=font, fill=INK, anchor='mt' if centered else 'lt')
        anchor = 'middle' if centered else 'start'
        svg.append(f'<text x="{x}" y="{y + size * .8}" text-anchor="{anchor}" font-family="Helvetica,Arial,sans-serif" font-size="{size}" fill="{INK}">{escape(value)}</text>')

    def rectangle(x1, y1, x2, y2, fill):
        pen.rectangle((x1, y1, x2, y2), fill=fill, outline=INK, width=2)
        svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="{fill}" stroke="{INK}" stroke-width="2"/>')

    def horizontal_dimension(x1, x2, edge_y, dim_y, label):
        for x in (x1, x2):
            line(x, edge_y, x, dim_y + 14, '#64748B', 2)
            line(x - 7, dim_y + 7, x + 7, dim_y - 7)
        line(x1, dim_y, x2, dim_y)
        text((x1 + x2) / 2, dim_y - 42, label, 28, True)

    text(70, 48, "ASHLEY'S BED | BED + LEFT BOOKCASE", 48)
    text(70, 112, 'Dimensioned design review | Right cabinet removed | Inches', 29)
    scale, x0, floor_y = 12, 200, 1010
    top_y = floor_y - height * scale
    front_bodies = []
    for body in geometry['wood']:
        name, owner = body['name'], body['owner']
        if owner.startswith('01 Cabinet') and name.startswith(('1R ', '1L ', '2T ', '2B ')):
            front_bodies.append(body)
        elif name.startswith('5.') or 'Left bookcase' in owner or name == 'SC Drawer face':
            front_bodies.append(body)
    # Back panels first; shelves, rails and the false drawer face overlay them.
    front_bodies.sort(key=lambda body: body['max'][1])
    for body in front_bodies:
        lo, hi = body['min'], body['max']
        x1, x2 = x0 + (width-hi[0])*scale, x0 + (width-lo[0])*scale
        y1, y2 = floor_y-hi[2]*scale, floor_y-lo[2]*scale
        fill = '#E7EDF4' if body['name'] == 'SC Plywood back' else '#B8C8DA'
        rectangle(x1, y1, x2, y2, fill)
    line(x0-25, floor_y, x0+width*scale+25, floor_y)
    horizontal_dimension(x0, x0+width*scale, top_y, 196, '116 3/4 overall')
    horizontal_dimension(x0, x0+30*scale, floor_y, 1110, '30 left bookcase')
    horizontal_dimension(x0+30*scale, x0+width*scale, floor_y, 1110, '86 3/4 bed cabinet')
    for y in (top_y, floor_y):
        line(140, y, x0-8, y, '#64748B', 2)
        line(133, y+7, 147, y-7)
    line(140, top_y, 140, floor_y)
    text(80, (top_y+floor_y)/2, '64', 28)
    text(x0, 1158, 'FRONT — viewed from the room; bookcase remains on the left', 28)
    side_x = 1830
    rectangle(side_x, top_y, side_x+depth*scale, floor_y, '#B8C8DA')
    horizontal_dimension(side_x, side_x+depth*scale, floor_y, 1110, '16 carcass')
    text(side_x+depth*scale/2, 1158, 'SIDE', 28, True)
    text(70, 1230, 'Left bookcase: four open bays above one drawer; three adjustable shelves.', 29)
    text(70, 1280, 'Carcass dimensions exclude projecting pulls. Steel hardware and folding motion remain representative.', 27)
    text(70, 1330, 'NOT A MACHINING RELEASE: finalize stock thickness, joinery, shelf fit, slide model, cutters and workholding.', 27)
    text(70, 1380, 'Native Fusion wood-body bounds; follow Rockler anchoring instructions. Hidden wall brackets remain required.', 25)
    svg.append('</svg>')
    MEDIA.mkdir(exist_ok=True)
    (OUT / 'design-elevations.svg').write_text('\n'.join(svg)+'\n')
    drawing.save(MEDIA / 'ashleys-bed-front.png')
    pages = [drawing]
    labels = [('closed', 'CLOSED — native Fusion view'), ('open', 'OPEN — native Fusion view'),
              ('frame', 'FRAME — native Fusion view; mattress hidden')]
    for pose, label in labels:
        page = Image.new('RGB', (WIDTH, HEIGHT), 'white')
        d = ImageDraw.Draw(page)
        d.text((70, 50), label, font=ImageFont.truetype(FONT, 42), fill=INK)
        with Image.open(MEDIA/f'ashleys-bed-{pose}.png') as original:
            image = ImageOps.contain(original.convert('RGB'), (2060, 1210))
        page.paste(image, ((WIDTH-image.width)//2, 145))
        d.text((70, 1410), 'Design review only — not a mechanism-clearance certification or machining release.',
               font=ImageFont.truetype(FONT, 27), fill=INK)
        pages.append(page)
    pages[0].save(OUT/'design-drawings.pdf', 'PDF', save_all=True, append_images=pages[1:], resolution=150)
    overview = Image.new('RGB', (1600, 1100), 'white')
    for index, page in enumerate(pages):
        image = ImageOps.contain(page, (800, 550))
        overview.paste(image, ((index % 2)*800, (index//2)*550))
    overview.save(MEDIA/'ashleys-bed-overview.png')
    print('Created dimensioned front/side SVG, 4-page design PDF, front PNG and overview from native Fusion geometry.')


if __name__ == '__main__':
    main()
