# Interactive Assembly Guide — Phase 1 (engine + bookcase) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use ml:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the guide engine (catalogue, joints/holes, fasteners, steps, GLB, SVG, staged generation),
the phone-first 3D viewer page with offline support, and the full bookcase step list including its HOLD
steps.

**Architecture:** Hand-edited data (`assembly_parts.py`, `assembly_steps.py`) is validated and turned
into one output directory (`output/assembly-guide/`: GLB + step JSON + per-step SVGs) by a stdlib-only
generator. `site/build.py` imports the generator, publishes the directory, a new "Step-by-step" page,
a Three.js viewer and a root service worker. Phases 2 (bed cabinet) and 3 (steel mechanism) get their own
plans on top of this engine.

**Tech Stack:** Python 3 standard library (`unittest`, `struct`, `json`, `xml.etree`), vanilla ES modules,
Three.js 0.170.0 vendored, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-11-18-interactive-assembly-guide-design.md`

## Global Constraints

- Generator and its modules: Python standard library only (CI runs `python site/build.py` on 3.12 with no installs).
- Units: inches in data; GLB in metres, Y-up, with the same axis map as `export_web_models.py`: `(x, y, z) -> (-x, z, y)`, `IN = 0.0254`.
- Dowel holes: 3/8 in, 1/2 in deep into a face, 1 1/16 in deep into an edge.
- #8 × 2 in screws through a side: 3/16 in clearance through the side, countersunk outside; 1/8 in pilot 1 1/4 in deep into the panel edge.
- 16 in joints: dowels 4 and 12 in from the datum end; screws 2, 8 and 14 in. Datum = front edge (`y = 16`, room side) for panel-to-side joints.
- Blind holes and screw tips leave ≥ 1/8 in; edge holes ≥ 1/8 in each side across the thickness. Thickness: 0.703 in for 3/4 stock, nominal − 1/32 in for 1/2 and 1/4 stock.
- Holes in one part ≥ 1 in centre to centre unless the step is HOLD or the pattern is `verified`.
- Bookcase joint bands (up the side): bottom 2.5–3.25, fixed shelf 14.0–14.75, top 63.25–64.0 in.
- Bookcase used quantities: 12 dowels, 18 #8 × 2 in screws (bed shares are added in Phase 2).
- Tests: `python3 -m unittest discover tests -v`. Three.js `0.170.0` from `cdn.jsdelivr.net/npm/three@0.170.0/`.
- Outputs only in `output/assembly-guide/`; page slug `build-steps`, placed after `assembly` in `PAGES`; `site/sw.js` published at the site root.
- Parts named by tape-label ID. L01 (model `SC Left side`) sits against the bed's M02; L02 (`SC Right side`) is the visible outer end.

## Review Focus

1. Phone with no signal after one online visit → the guide still opens and plays (Task 8 browser check).
2. Deep link to an unknown or HOLD step id → unknown falls back to step 1; a HOLD step opens with its banner (Task 8).
3. `localStorage` blocked (private mode) → the page works, it just does not remember the step (Task 7 test + Task 8).
4. Tapping Next repeatedly mid-animation → the current tween finishes instantly, no duplicated or half-placed parts (Task 8).
5. `prefers-reduced-motion` → parts appear without sliding (Task 8).

---

### Task 1: Part catalogue

**Files:** Create `MurphyBedQueen/assembly_parts.py`, `tests/__init__.py`, `tests/test_assembly_parts.py`

**Interfaces:**
- Produces: `Part` (dataclass: `id: str, label: str, assembly: str, min: tuple[float,float,float], max: tuple[float,float,float], stock: float, thickness: float`); `load_parts(geometry: Path = ROOT/'output/drawing-geometry.json') -> dict[str, Part]`; `drilling_thickness(part: Part) -> float`.

- [ ] **Step 1: Write failing tests** — `test_all_27_parts_loaded` (keys == M01–M11, L01–L16); `test_name_mapping` (`'SC Left side'` → `L01`, `'1R Right side | 3/4 x 16 x 64'` → `M01`, `'3 Upper headboard — REQUIRED'` → `M05`); `test_boxes_match_geometry` (L04 min `(87.5, 0, 2.5)`, max `(116, 16, 3.25)` within 1e-6); `test_drilling_thickness` (L04 → 0.703, L11 → 0.46875, L06 → 0.21875); `test_l01_is_next_to_bed` (`L01.min[0] == parts['M02'].max[0]`).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_assembly_parts -v` → FAIL (module missing).
- [ ] **Step 3: Implement.** Map names by stripping text after `|` and ` — `, replacing the `SC ` prefix with `Left cabinet: `, then matching `PART_SPECS` keys imported from `generate_cut_layouts` (id, label, nominal thickness). `stock` = nominal thickness (M07's stock is 0.75; its finished 0.625).
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: assembly guide part catalogue`.

### Task 2: Joints, holes and hole checks

**Files:** Modify `MurphyBedQueen/assembly_parts.py`; Test `tests/test_assembly_holes.py`

**Interfaces:**
- Consumes: `Part`, `load_parts`, `drilling_thickness`.
- Produces: `Hole` (dataclass: `part, surface: str ('face'|'edge'), ref_edge: str, ref_end: str, u: float, v: float, diameter: float, depth: float, kind: str ('dowel'|'clearance'|'pilot'|'transfer'|'stud'), countersink: bool, verified: str|None, world: tuple[float,float,float], axis: tuple[float,float,float]`); `Joint` (dataclass: `id, a: str (side), b: str (panel), band: tuple[float,float], datum: str, dowels: list[float], screws: list[float]`); `JOINTS: dict[str, Joint]` with `L04-L01, L04-L02, L07-L01, L07-L02, L03-L01, L03-L02`; `joint_holes(joint, parts) -> list[Hole]`; `check_holes(holes, parts, held: set[str]) -> list[str]` (error messages).

- [ ] **Step 1: Write failing tests** —
  - `test_bookcase_joint_counts`: each joint → 2 dowel holes in the side face, 2 in the panel edge, 3 clearance + 3 pilot.
  - `test_positions_from_front`: L04-L01 dowels at world `y = 12, 4`, screws at `y = 14, 8, 2`; side-face hole `z` centred in L04 (2.875).
  - `test_depths`: side-face dowel 0.5, panel-edge dowel 1.0625, pilot 1.25, clearance through (depth = 0.75).
  - `test_mirror_sides`: L04-L01 and L04-L02 holes mirror in world x about the bookcase centreline and both have `u` measured from their own front edge.
  - `test_bands`: every side hole's z lies in its joint band; a hole moved to z = 4.0 makes `check_holes` report "outside joint band".
  - `test_wall_rule`: face dowel 0.5 in 0.703 passes; a 0.625 face hole fails "less than 1/8 in"; an edge dowel passes (0.164 each side).
  - `test_spacing`: two holes 0.75 in apart fail; the same pair passes when `verified="Rockler p. 12"`.
  - `test_held_joint_skips`: `check_holes(..., held={'L07-L01'})` ignores that joint's spacing errors but not its out-of-part errors.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_assembly_holes -v` → FAIL.
- [ ] **Step 3: Implement.** Holes are built in world space from the joint (contact plane = the side's inner face, datum = `y = 16`), then projected into each part: on a face, `u` across the width from `ref_edge`, `v` along the length from `ref_end`; on an edge, `u` along the edge, hole centred in thickness. Names: sides `ref_edge='front edge'`, `ref_end='bottom end'`; panels `ref_edge='front edge'`, `ref_end='end at L01'`.
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: bookcase joints and hole checks`.

### Task 3: Fasteners and discrepancies

**Files:** Modify `MurphyBedQueen/assembly_parts.py`; Test `tests/test_assembly_fasteners.py`

**Interfaces:**
- Produces: `Fastener` (dataclass: `code, name, source ('kit'|'bought'|'bundled'), used: dict[str,int] (per assembly), bought: int, supplied: int`); `load_fasteners(inventory: Path, bom: Path) -> dict[str, Fastener]`; `DISCREPANCIES: dict[str, dict]` (BB, W, OO: `used`, `supplied`, `question`, `clear_when: list[str]`, `recorded: list[str]`); `check_fasteners(totals: dict[str,int], fasteners, assemblies: set[str]) -> list[str]`; `discrepancy_holds() -> dict[str, str]` (code → banner text).

- [ ] **Step 1: Write failing tests** — `test_kit_codes_loaded` (T, U, V, W, Z, AA, BB, DD, EE, FF, II, JJ, KK, OO present; KK supplied 12); `test_bought_codes` (`dowel` bought 50, `screw-8x2` bought 100, `screw-8x1.25` 25, `screw-8x1-washer` 25); `test_used_bookcase` (`dowel.used['bookcase'] == 12`, `screw-8x2.used['bookcase'] == 18`); `test_check_passes_bookcase` (totals `{dowel: 12, screw-8x2: 18}`, assemblies `{'bookcase'}` → no errors); `test_check_fails_mismatch` (dowel 10 → error names `dowel`); `test_used_exceeds_supply` (a bundled entry with used 8, supplied 0, bought 0 → error); `test_w_hold_text` (W banner mentions 88 used and 56 supplied and says to buy 32); `test_bb_needs_length` (BB with quantity recorded but not length → still held).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** reading `output/rockler-kit-inventory.csv` (`Code`, `Queen_quantity`) and `output/bill-of-materials.csv` (fastener rows by `Item`). Codes for bought items: `dowel`, `screw-8x2`, `screw-8x1.25`, `screw-8x1-washer`, `screw-6x1.25`, `screw-6x0.75`. **Step 4: Run** → PASS. **Step 5: Commit** `feat: fastener catalogue and discrepancy holds`.

### Task 4: Bookcase steps, validation and HOLD propagation

**Files:** Create `MurphyBedQueen/assembly_steps.py`; Modify `MurphyBedQueen/assembly_parts.py` (`OPEN_DECISIONS`); Create `MurphyBedQueen/assembly_guide.py`; Test `tests/test_assembly_steps.py`

**Interfaces:**
- Produces: `OPEN_DECISIONS: dict[str, str]` (ids `back`, `slide`, `shelf-pins`, `restraint`, `plinth`, `drawer-box`, `pulls`, `pilot-depth`, `screw-tips`, `kit`); `STEPS: list[dict]` (spec data model incl. `requires`, `hold` = decision id or None, `pose`, `move`, `camera`); `ResolvedStep` (dataclass: `step: dict, held_by: list[str], holes: list[Hole], fasteners: dict[str,int]`); `resolve(steps, parts, fasteners) -> list[ResolvedStep]`; `validate(resolved, parts, fasteners) -> list[str]`.

- [ ] **Step 1: Write failing tests** —
  - `test_bookcase_step_order`: ids in order `bookcase-drill`, `bookcase-drill-shelf`, `bookcase-bottom`, `bookcase-plinth`, `bookcase-shelf`, `bookcase-top`, `bookcase-right-side`, `bookcase-back`, `bookcase-drawer-box`, `bookcase-slides`, `bookcase-drawer-pull`, `bookcase-shelves`, `bookcase-place`.
  - `test_every_bookcase_part_added_once`: L01–L16 each added exactly once; `bookcase-drill` adds L01 and L02 with `pose: {'L02': 'bench'}`.
  - `test_holds`: `bookcase-drill-shelf` held by `slide`; `bookcase-shelf` held by `slide` via propagation (uses joint L07-L01); `bookcase-plinth` by `plinth`; `bookcase-back` by `back`; `bookcase-drawer-box` by `drawer-box`; `bookcase-drawer-pull` by `pulls`; `bookcase-shelves` by `shelf-pins`; `bookcase-place` by `restraint`.
  - `test_ready_steps`: only `bookcase-drill`, `bookcase-bottom` and `bookcase-top` have no holds; `bookcase-right-side` is held by `slide` because it makes joint L07-L02.
  - `test_step_joints`: `bookcase-drill` drills the side-face holes of L04-L01, L04-L02, L03-L01, L03-L02; `bookcase-drill-shelf` drills L07-L01, L07-L02; `bookcase-bottom` makes L04-L01; `bookcase-shelf` L07-L01; `bookcase-top` L03-L01; `bookcase-right-side` L04-L02, L07-L02, L03-L02 (panel-edge holes are drilled in the step that makes the joint).
  - `test_unknown_part_rejected`, `test_unknown_joint_rejected`, `test_part_added_twice_rejected`, `test_requires_unknown_step_rejected`.
  - `test_fastener_totals`: bookcase totals equal 12 dowels and 18 #8 × 2 in screws; `validate` returns `[]`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** `assembly_guide.resolve/validate`. Propagation: a step is held by its own `hold`, by any decision holding a joint/part it makes or uses, and by any held step in `requires` (transitively). Text, warnings and cameras are written for each bookcase step in plain imperative sentences using tape IDs and physical words ("the side next to the bed", "the outer end"). **Step 4: Run** → PASS. **Step 5: Commit** `feat: bookcase assembly steps with hold propagation`.

### Task 5: GLB writer

**Files:** Create `MurphyBedQueen/assembly_glb.py`; Test `tests/test_assembly_glb.py`

**Interfaces:**
- Consumes: `Part`, `Hole`, `ResolvedStep`.
- Produces: `build_glb(parts, resolved) -> bytes` — one node per part (name = part id) and per hardware instance (name `<joint>-<kind>-<n>`, e.g. `L04-L01-dowel-1`); materials `wood`, `hardware`; `read_glb(data: bytes) -> dict` (JSON chunk) for tests.

- [ ] **Step 1: Write failing tests** — `test_magic_and_chunks` (`glTF`, version 2, JSON + BIN chunks 4-byte aligned); `test_node_names` (all 27 part ids plus 12 dowel and 18 screw nodes — 2 + 3 for each of the six bookcase joints — matching the hardware instances `resolve` produced); `test_axis_map` (L04 node bounds in metres equal `(-116, 2.5, 0)…(-87.5, 3.25, 16)` × 0.0254 after the `(-x, z, y)` map); `test_accessor_bounds_present`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** boxes (24 vertices, normals) and cylinders (16 sides) packed with `struct`; follow the glTF layout of `export_web_models.GlbWriter`. **Step 4: Run** → PASS. **Step 5: Commit** `feat: stdlib GLB writer for the assembly guide`.

### Task 6: SVG drawings

**Files:** Create `MurphyBedQueen/assembly_drawings.py`; Test `tests/test_assembly_drawings.py`

**Interfaces:**
- Produces: `step_svg(index: int, resolved: list[ResolvedStep], parts) -> str` (exploded isometric view + hardware panel + HOLD banner); `holes_svg(rs: ResolvedStep, parts) -> str` (dimensioned close-up, empty string when the step has no `drill`).

- [ ] **Step 1: Write failing tests** — `test_svg_parses` (every step's SVG parses with `xml.etree`); `test_contains_new_part_ids` (each added id appears in a `<text>`); `test_earlier_parts_grey` (`bookcase-top` draws L04 with class `done`, L03 with class `new`); `test_hardware_panel_counts` (`bookcase-bottom` panel contains `×2` dowel and `×3` screw per joint shown); `test_hole_closeup` (`bookcase-drill` close-up contains labels `4"`, `12"`, `Ø3/8 × 1/2 deep` and the band note "keep shelf-pin rows and slide screws out"); `test_hold_banner` (`bookcase-back` SVG contains `HOLD` and the decision text); `test_depth_order` (boxes are emitted back to front by isometric depth).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** an isometric view from the room side, outer end and above. In Fusion axes the eye looks along `d = (−1, −1, −1)/√3` (from +x, +y, +z toward the model); project with `sx = (y − x)·cos30°`, `sy = (x + y)·sin30° − z` (already SVG coordinates: y grows down, so taller parts rise); draw boxes farthest first, sorted by `dot(centre, d)` descending (`test_depth_order` pins this key); new parts offset along `move` with arrow paths; dimensions as fractions via `generate_cut_layouts.inches`. **Step 4: Run** → PASS. **Step 5: Commit** `feat: exploded and hole drawings`.

### Task 7: Staged generation

**Files:** Create `MurphyBedQueen/generate_assembly_guide.py`; Test `tests/test_generate_assembly_guide.py`

**Interfaces:**
- Produces: `generate(out_dir: Path = ROOT/'output/assembly-guide') -> dict` (summary: `steps`, `holds`, `files`); writes `assembly.glb`, `assembly-steps.json` (`[{id, title, adds, hardware: [{code, count, nodes}], pose, move, camera, text, warnings, hold: [banner…], requires, source, svg, holes_svg}]`), `step-NN.svg`, `step-NN-holes.svg`; CLI `python3 MurphyBedQueen/generate_assembly_guide.py` prints the summary and exits non-zero on any validation error.

- [ ] **Step 1: Write failing tests** — `test_generates_all_files` (tmp dir: 13 step SVGs, JSON lists 13 steps, GLB parses); `test_clean_checkout` (out dir absent → created); `test_stale_files_removed` (pre-existing `step-99.svg` gone after generate); `test_failure_keeps_previous` (patch `validate` to return an error → `generate` raises and the previous directory's files are unchanged, no staging dir left behind); `test_hold_count` (summary `holds == 10`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** staging in a sibling `assembly-guide.staging-<pid>`, validate the full set (parse every SVG, `read_glb`, JSON ids == `STEPS` ids), then rename current → backup (skip if absent), staging → current, delete backup; restore backup if the second rename fails. **Step 4: Run** → PASS. **Step 5: Commit** `feat: staged assembly guide generation`.

### Task 8: Viewer page, offline cache and site build

**Files:** Create `site/content/build-steps.html`, `site/assets/assembly-viewer.js`, `site/sw.js`, `site/assets/vendor/three/` (`three.module.min.js`, `OrbitControls.js`, `GLTFLoader.js`, `BufferGeometryUtils.js` from three@0.170.0); Modify `site/build.py`; Test `tests/test_site_build.py`

**Interfaces:**
- Consumes: `generate(out_dir)`; JSON schema from Task 7.
- Produces: page `build-steps.html` (`PAGES` entry `('build-steps', 'Step-by-step', 'Step-by-step assembly', 'Interactive 3D steps for the bed and bookcase.')` after `assembly`); published `assembly-guide/` directory; `sw.js` at the site root.

- [ ] **Step 1: Write failing tests** — `test_build_publishes_guide` (run `site/build.py main()` → `_site/build-steps.html`, `_site/assembly-guide/assembly-steps.json`, `_site/sw.js` exist); `test_failed_build_keeps_site` (patch `generate` to raise → previous `_site/index.html` unchanged); `test_importmap_and_scripts` (page has an import map for `three` and module script `assets/assembly-viewer.js`); `test_sw_precache_list` (`sw.js` lists the page, viewer, three files, GLB, JSON and every SVG; cache name contains the JSON's SHA-256 prefix).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `site/build.py`**: build into `site/_site.tmp-<pid>`, call `generate()` first, copy `output/assembly-guide/` to `assembly-guide/`, write `sw.js` with the precache list and hash, validate, then swap into `site/_site`.
- [ ] **Step 4: Implement the viewer** (`assembly-viewer.js`): load GLB and JSON; per step show earlier nodes solid, hide later ones, tween new nodes from `move` offset with accent material then settle; hardware nodes tween after their panel; camera eases to `camera`; `#<step id>` deep links (unknown → first step); last step in `localStorage` inside try/catch; Back/Replay/Next bar + swipe; Next during a tween completes it instantly first; `prefers-reduced-motion` skips tweens; HOLD banner, part chips (tap flashes node), hardware counts, text, warnings, SVG with tap-to-fullscreen; register `sw.js`.
- [ ] **Step 5: Run** `python3 -m unittest discover tests -v` and `python3 site/build.py` → all pass, "Validated 7 pages".
- [ ] **Step 6: Browser check** (ml:agent-browser, served from `site/_site` with `python3 -m http.server`): at 390×844 and 1280×800 step through all 13 steps (no console errors, node count visible = parts so far); `#bookcase-back` opens with the HOLD banner; `#nope` opens step 1; tap Next 5× fast → state equals step 6 with no duplicate nodes; reduced-motion emulation shows no tween; storage disabled → page still steps; after one visit, offline reload still renders. Save screenshots under `.tmp/`.
- [ ] **Step 7: Commit** `feat: interactive step-by-step page with offline cache`.

### Task 9: Docs

**Files:** Modify `README.md`, `site/content/assembly.html`

- [ ] **Step 1:** README: add the guide generator to the regenerate steps (`python3 MurphyBedQueen/generate_assembly_guide.py`, runs automatically in `site/build.py`) and the test command. Correct the bookcase note: the visible outer end is L02; L01 sits against the bed (screw holes to fill are on L02's outer face).
- [ ] **Step 2:** `assembly.html` Stage 4: link to `build-steps.html#bookcase-drill` and apply the same L01/L02 correction.
- [ ] **Step 3:** `python3 site/build.py` → validates. **Step 4: Commit** `docs: point to the step-by-step guide`.
