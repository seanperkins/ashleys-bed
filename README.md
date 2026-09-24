# Ashley’s Murphy bed

Build guide: https://seanperkins.github.io/ashleys-bed/

Current design: Rockler I-Semble horizontal queen bed with one room-facing left bookcase and drawer. Overall carcass: **116¾ W × 64 H × 16 D inches**. The right cabinet is removed.

## Release status

The native models, drawings, parts list and nominal sheet layouts are design-review deliverables. **No machine-ready CAM or G-code is released.** Plywood and cutters have not been purchased. Final stock thickness, bookcase joinery, hardware, workholding, tools and the shop-approved post/profile must be resolved before machining.

Follow the complete [Rockler horizontal-bed instructions](https://go.rockler.com/tech/horizontal-murphy-bed-inst-25.pdf) and [HackRVA Avid PRO6096 requirements](https://wiki.hackrva.org/index.php/Avid_PRO6096). Hardware and motion in CAD remain representative. Hidden wall brackets remain required; both headboards and all specified anchors are retained.

## Build the website

The website builder uses Python 3.10+ standard library only. No Node packages, API keys or backend are needed.

```sh
python3 site/build.py
python3 -m http.server 8047 --directory site/_site
```

Open http://localhost:8047. The build checks local links, anchors, duplicate IDs, required downloads and the current model revision. Page links are relative, so the guide works under the GitHub Pages project path.

- `site/content/`: page-specific instructions.
- `site/assets/`: responsive/print styles and browser-local checklist/worksheet behavior.
- `site/assets/vendor/`: pinned, self-hosted `<model-viewer>` 4.3.1 for the overview page's 3D viewer. No third-party requests.
- `site/build.py`: page shell, live BOM table, download index and explicit public-file allowlist.
- `output/`: current verified models and generated project documents.
- `.github/workflows/pages.yml`: builds and deploys the guide on pushes to `main` or manual dispatch.

Checklist and worksheet values remain in the reader’s browser. “Export my notes” downloads them; they are not sent to GitHub or a server. Printed worksheets expand full field values and disclosure notes. Checking boxes does not release machining.

## Update the design documents

1. Run `MurphyBedQueen/MurphyBedQueen.py` inside Autodesk Fusion. It creates a new design and exports open/closed F3D and STEP files, native previews, the wood cut list, drawing-body bounds and a build report.
2. Reopen both saved Fusion archives and verify the intended cabinet count/position, bed endpoints, required hidden references and timeline health. Review native previews; do not treat a successful export as a fabrication release.
3. Generate the nominal layouts and design-review drawings:

   ```sh
   python3 MurphyBedQueen/generate_cut_layouts.py
   python3 MurphyBedQueen/generate_drawings.py
   ```

   Then build the GLB files used by the site's 3D viewer (needs `pip install cascadio trimesh`). It writes static closed/open models and an animated open/close model. It fails if any part does not match the bed and leg joints in `MurphyBedQueen.py`, if the STEP gas-spring mounts moved, or if the swing puts the leg through the mattress or below the floor:

   ```sh
   python3 MurphyBedQueen/export_web_models.py
   ```

   The cut-layout generator uses the standard library and rejects unexpected parts or dimensions. The drawing generator requires Pillow and the macOS Helvetica font; it consumes native Fusion body bounds, not guessed image dimensions. Site deployment does not regenerate CAD or require Pillow.
4. Update purchasing instructions and the BOM when the design changes. Recheck all sheet quantities, hardware requirements and finish allowances. Refresh the design-review ZIP from the matching current outputs; do not include old revisions or prior budgets.
5. Run the website build, inspect desktop/mobile pages, exercise saved checklists/search/note export, and print a worksheet with long notes before publishing.

## Publication boundary

The Pages artifact contains six guide pages, static assets and explicitly selected current downloads. Old two-cabinet budgets, media and local revision archives are excluded. The manufacturer PDF is linked at its official source rather than republished. Local `references/`, `revisions/` and `output/previous-*` directories are ignored.

Historical Richmond supplier leads are dated and are not current prices or stock confirmations. No current project total or mattress purchase price is represented.
