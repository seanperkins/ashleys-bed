#!/usr/bin/env python3
"""Build the public guide from current project outputs; publish an explicit allowlist."""
import csv
import html
import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
DEST = SITE / '_site'
OUT = ROOT / 'output'
PAGES = [
    ('index', 'Overview', 'Ashley’s Murphy bed', 'A project guide for the horizontal queen bed and left bookcase.'),
    ('planning', 'Plan the build', 'Plan before you purchase', 'Dimensions, room checks and decisions that control the build.'),
    ('purchase', 'Purchase', 'The purchasing guide', 'What to buy, what is included, and what to confirm first.'),
    ('cnc', 'CNC preparation', 'From plywood to cut parts', 'The machining plan, setup worksheet and release requirements.'),
    ('assembly', 'Build & finish', 'Assembly, finishing & installation', 'A staged project guide, alongside Rockler’s required instructions.'),
    ('downloads', 'Drawings & files', 'The current project files', 'One revision. Clearly labeled drawings, parts and cut outlines.'),
]
DOWNLOADS = [
    ('design-drawings.pdf', 'Design drawings', '4-page PDF · elevations and native Fusion views'),
    ('parts-list.txt', 'Readable parts checklist', 'Text · quantities, package allowances and required confirmations'),
    ('bill-of-materials.csv', 'Bill of materials', 'CSV · materials, hardware, fasteners and finishing supplies'),
    ('cabinet-cut-list.csv', 'Wood cut list', 'CSV · 27 nominal parts and their dimensions'),
    ('plywood-by-project.csv', 'Plywood by project', 'CSV · main / left cabinet pieces, sheet IDs and coordinates'),
    ('rockler-kit-inventory.csv', 'Kit inventory', 'CSV · supplied parts and manual discrepancies to confirm'),
    ('cut-lines/cut-layout-booklet.pdf', 'Sheet layout booklet', '8-page PDF · planning placements, NOT a machining release'),
    ('cut-lines/cut-guide.txt', 'Cut file conventions', 'Text · grain, layers, origins and limitations'),
    ('plywood-purchasing-layout.json', 'Placement data', 'JSON · dimensions and coordinates; machineReady is false'),
    ('queen-horizontal-closed.f3d', 'Closed Fusion model', 'Editable native assembly · hardware remains representative'),
    ('queen-horizontal-open.f3d', 'Open Fusion model', 'Editable native assembly · not certified mechanism clearance'),
    ('queen-horizontal-closed.step', 'Closed STEP model', 'CAD interchange · visible components only'),
    ('queen-horizontal-open.step', 'Open STEP model', 'CAD interchange · visible components only'),
    ('design-elevations.svg', 'Dimensioned elevations', 'SVG · front and side design-review drawing'),
    ('ashleys-bed-design-review.zip', 'Complete design-review package', 'ZIP · current models, drawings and nominal cut files; NO G-code'),
]


def e(value):
    return html.escape(str(value), quote=True)


def bom_table():
    with (OUT/'bill-of-materials.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    groups = []
    for row in rows:
        if row['Group'] not in groups:
            groups.append(row['Group'])
    tables = []
    for group in groups:
        body = []
        for row in (r for r in rows if r['Group'] == group):
            body.append(f'''<tr data-bom-row><th scope="row">{e(row['Item'])}</th>
<td class="quantity">{e(row['Buy_quantity'])} {e(row['Unit'])}</td>
<td><p>{e(row['Specification'])}</p><details><summary>Use, quantity basis & notes</summary>
<p><strong>Used for:</strong> {e(row['Where_used'])}</p><p><strong>Basis:</strong> {e(row['Quantity_basis'])}</p><p>{e(row['Notes'])}</p></details></td></tr>''')
        tables.append(f'<div class="table-wrap" data-bom-group><table><caption>{e(group)}</caption><thead><tr><th scope="col">Item</th><th scope="col">Planning quantity</th><th scope="col">Specification & notes</th></tr></thead><tbody>{"".join(body)}</tbody></table></div>')
    return '<div id="bom-results">' + ''.join(tables) + '</div><p id="bom-empty" hidden>No items match that search.</p>'


def downloads_page():
    cards = []
    for path, title, description in DOWNLOADS:
        size = (OUT/path).stat().st_size
        size_label = f'{size/1024/1024:.1f} MB' if size > 1024*1024 else f'{size/1024:.0f} KB'
        cards.append(f'<a class="download-card" href="downloads/{e(path)}" download><span class="download-type">{e(Path(path).suffix[1:].upper())}</span><span><strong>{e(title)}</strong><small>{e(description)}</small></span><span class="file-size">{size_label}</span></a>')
    sheets = []
    layout = json.loads((OUT/'plywood-purchasing-layout.json').read_text())
    for sheet in layout['sheets']:
        sid = sheet['sheetId']
        thickness = {0.75:'¾',0.5:'½',0.25:'¼'}[sheet['stockThicknessInches']]
        sheets.append(f'<tr><th scope="row">{sid}</th><td>{thickness}″ · {sheet["widthInches"]} × {sheet["lengthInches"]}″</td><td>{len(sheet["parts"])} parts</td><td><a href="downloads/cut-lines/{sid}.svg">View {sid}</a> · <a href="downloads/cut-lines/{sid}.dxf" download>DXF {sid}</a></td></tr>')
    return f'''<div class="warning"><strong>These files are not machine-ready.</strong><p>DXFs contain uncompensated nominal rectangles. They do not contain approved joints, machining operations or runnable G-code. Use the <a href="cnc.html">CNC release checklist</a> before cutting.</p></div>
<section><h2 id="project-downloads">Models, drawings & purchasing documents</h2><div class="download-list">{''.join(cards)}</div></section>
<section><h2 id="sheet-files">Individual sheet outlines</h2><p>All DXFs declare inches. Only the closed <code>PART_OUTLINES</code> layer describes nominal parts; stock, margin, grain and label layers are references, not cut paths.</p><div class="table-wrap"><table><caption>Current eight-sheet/panel layout</caption><thead><tr><th scope="col">Sheet</th><th scope="col">Stock</th><th scope="col">Contents</th><th scope="col">Files</th></tr></thead><tbody>{''.join(sheets)}</tbody></table></div></section>
<section><h2 id="verification">What has actually been checked</h2><ul><li>Both saved Fusion archives reopened with one left cabinet, correct bed endpoints, hidden wall-bracket references and no timeline warnings.</li><li>All 27 remaining wood pieces match their previous model dimensions; the right cabinet’s 16 parts were removed.</li><li>All eight DXFs match the placement data, with ¾″ edge margins, ½″ gaps, correct stock groups and no missing or duplicate pieces.</li></ul><p>These checks verify the design files, not final joinery, structural adequacy, cutter clearance or machine setup. Earlier two-cabinet media and budgets are archived locally and excluded here.</p></section>'''


def render(slug, title, description, body):
    navigation = ''.join(f'<a href="{name}.html"'+(' aria-current="page"' if name==slug else '')+f'><span>{index:02}</span>{e(label)}</a>' for index,(name,label,_,_) in enumerate(PAGES,1))
    next_index = next(i for i,p in enumerate(PAGES) if p[0]==slug)+1
    next_page = PAGES[next_index] if next_index<len(PAGES) else PAGES[0]
    headings = re.findall(r'<h2\b[^>]*id="([^"]+)"[^>]*>(.*?)</h2>', body, re.S)
    contents = ''
    if slug != 'index' and headings:
        links = ''.join(f'<li><a href="#{e(anchor)}">{e(re.sub("<[^>]+>", "", label))}</a></li>'
                        for anchor, label in headings)
        contents = f'<details class="page-contents"><summary>On this page</summary><ol>{links}</ol></details>'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} · Ashley’s bed</title><meta name="description" content="{e(description)}">
<meta name="theme-color" content="#182B49"><link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="assets/style.css"><script src="assets/guide.js" defer></script></head>
<body><a class="skip-link" href="#main">Skip to content</a><div class="site-shell">
<aside class="sidebar"><a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span><span>Ashley’s bed<small>PROJECT FIELD GUIDE</small></span></a>
<nav aria-label="Build guide">{navigation}</nav><div class="sidebar-note"><span class="status-dot"></span>Design-review revision<small>Bed + left bookcase<br>Updated September 22, 2026</small></div></aside>
<div class="page"><header class="utility"><span>HORIZONTAL QUEEN / ROCKLER I-SEMBLE</span><div><button type="button" id="print-page">Print this page</button><button type="button" id="export-notes">Export my notes</button></div></header>
<main id="main"><div class="page-heading"><p class="eyebrow">{e(next(p[1] for p in PAGES if p[0]==slug))}</p><h1>{e(title)}</h1><p class="lead">{e(description)}</p></div>
<div class="release-bar"><span class="badge pending">Planning only</span><p>Plywood and cutters not purchased. Final fabrication and CNC release remain pending.</p></div>
<div class="personal-progress" id="personal-progress" hidden><span id="progress-label"></span><progress id="check-progress" value="0" max="1"></progress><small id="save-status">Your checks and notes save only in this browser. Checking a box does not approve machining.</small></div>
<noscript><p class="note">All instructions and downloads work without JavaScript. Saved checklists, note export, filtering and the print button require JavaScript; use your browser’s Print command instead.</p></noscript>
{contents}
{body}
<div class="next-page"><span>Continue the guide</span><a href="{next_page[0]}.html">{e(next_page[1])} <span aria-hidden="true">→</span></a></div></main>
<footer><p>Use this guide alongside the <a href="https://go.rockler.com/tech/horizontal-murphy-bed-inst-25.pdf">Rockler horizontal-bed instructions</a> and <a href="https://wiki.hackrva.org/index.php/Avid_PRO6096">HackRVA’s CNC requirements</a>. Manufacturer instructions and the qualified installer/operator control the work.</p><p>No analytics, account or cloud-saved checklist. <a href="https://github.com/seanperkins/ashleys-bed">Project source</a></p></footer></div></div></body></html>'''


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                raise ValueError('Duplicate HTML id: '+attrs['id'])
            self.ids.add(attrs['id'])
        if tag=='a' and 'href' in attrs: self.links.append(attrs['href'])
        if tag in ('img','script') and 'src' in attrs: self.links.append(attrs['src'])
        if tag=='link' and 'href' in attrs: self.links.append(attrs['href'])


def validate_site():
    documents={}
    for page in DEST.glob('*.html'):
        parser=Links()
        parser.feed(page.read_text())
        documents[page]=parser
    for page, parser in documents.items():
        for link in parser.links:
            url=urlsplit(link)
            if url.scheme or url.netloc: continue
            target=(page.parent/unquote(url.path)).resolve() if url.path else page
            if not target.is_relative_to(DEST.resolve()) or not target.exists():
                raise ValueError(f'{page.name}: missing or unsafe local link {link}')
            if url.fragment and target in documents and unquote(url.fragment) not in documents[target].ids:
                raise ValueError(f'{page.name}: missing anchor {link}')
    print(f'Validated {len(documents)} pages: local navigation, anchors and download links resolve.')


def main():
    report=json.loads((OUT/'build-result.json').read_text())
    if set(report['sideCabinets'])!={'left'} or report['combinedCarcassInchesWHD'] != [116.75,64,16]:
        raise ValueError('Public guide requires the bed-plus-left-cabinet revision')
    if DEST.exists(): shutil.rmtree(DEST)
    (DEST/'downloads/cut-lines').mkdir(parents=True)
    shutil.copytree(SITE/'assets', DEST/'assets', dirs_exist_ok=True)
    for name in ('closed','open','frame','front','overview'):
        shutil.copy2(OUT/f'media/ashleys-bed-{name}.png', DEST/f'assets/ashleys-bed-{name}.png')
    for path, _, _ in DOWNLOADS:
        shutil.copy2(OUT/path, DEST/'downloads'/path)
    for sheet in range(1,9):
        for ext in ('svg','dxf'):
            name=f'cut-lines/S{sheet:02}.{ext}'
            shutil.copy2(OUT/name, DEST/'downloads'/name)
    for slug, _, title, description in PAGES:
        body=downloads_page() if slug=='downloads' else (SITE/f'content/{slug}.html').read_text()
        body=body.replace('{{BOM_TABLE}}',bom_table()) if slug=='purchase' else body
        if re.search(r'\{\{[A-Z_]+\}\}',body): raise ValueError('Unresolved content token in '+slug)
        (DEST/f'{slug}.html').write_text(render(slug,title,description,body))
    (DEST/'.nojekyll').touch()
    validate_site()
    print('Built GitHub Pages site in site/_site. Archived budgets/revisions are not published.')


if __name__=='__main__':
    main()
