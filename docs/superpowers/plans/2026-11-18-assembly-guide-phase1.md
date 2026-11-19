# Interactive Assembly Guide — Phase 1 (engine + bookcase) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use ml:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the guide engine (catalogue, joints/holes, fasteners, steps, GLB, SVG, staged generation),
the phone-first 3D viewer page with offline support, and the full bookcase step list including its HOLD
steps.

**Architecture:** Hand-edited data (`assembly_parts.py`, `assembly_steps.py`) is validated and turned
into one output directory (`output/assembly-guide/`: GLB + step JSON + SVGs) by a stdlib-only generator.
`site/build.py` imports the generator and publishes that directory, a new "Step-by-step" page, a Three.js
viewer and a root service worker. Phases 2 (bed cabinet) and 3 (steel mechanism) get their own plans.

**Tech Stack:** Python 3 standard library (`unittest`, `struct`, `json`, `xml.etree`, `tempfile`),
vanilla ES modules, Three.js 0.170.0 vendored, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-11-18-interactive-assembly-guide-design.md`

## Global Constraints

- Generator and its modules: Python standard library only (CI runs `python site/build.py` on 3.12 with no installs).
- Units: inches in data; GLB in metres, Y-up, axis map `(x, y, z) -> (-x, z, y)` × `0.0254` (as `export_web_models.py`, no centring).
- Dowel holes: 3/8 in, 1/2 in deep into a face, 1 1/16 in deep into an edge (blind).
- #8 × 2 in screws through a side: 3/16 in clearance hole through the side, countersunk outside; 1/8 in blind pilot 1 1/4 in deep into the panel edge.
- 16 in joints: dowels 4 and 12 in from the datum end; screws 2, 8 and 14 in. Datum = front edge (`y = 16`, room side).
- Blind holes and screw tips leave ≥ 1/8 in; edge holes ≥ 1/8 in each side across the thickness; through holes are exempt. Thickness: 0.703 in for 3/4 stock, nominal − 1/32 in for 1/2 and 1/4 stock.
- Holes in one part ≥ 1 in centre to centre unless their joint is held or the pattern is `verified`.
- Bookcase joint bands (up the side): bottom 2.5–3.25, fixed shelf 14.0–14.75, top 63.25–64.0 in.
- Phase 1 active assemblies: `{'bookcase'}`. Completeness and fastener totals are checked for active assemblies only; all 27 parts stay in the catalogue and GLB (inactive parts render as faint context).
- Bookcase used quantities: 12 dowels, 18 #8 × 2 in screws.
- Finishes: navy `#182B49` for all wood except the drawer box L11–L15, natural `rgb(217,191,151)` (as `MurphyBedQueen.py`).
- Tests: `python3 -m unittest discover tests -v`. Three.js `0.170.0` from `cdn.jsdelivr.net/npm/three@0.170.0/`.
- The generator CLI writes only `output/assembly-guide/`; the site build generates into its own staging dir and never writes there; page slug `build-steps` after `assembly` in `PAGES`; `site/sw.js` published at the site root.
- Parts named by tape-label ID. L01 (model `SC Left side`) sits against the bed's M02; L02 (`SC Right side`) is the visible outer end.
- Kit discrepancies never tell the builder to buy before confirmation: W shows "possible shortage of 32 — confirm with Rockler".

## Review Focus

1. Phone with no signal after one online visit → the guide still opens with its full layout and plays (Task 8).
2. Deep link to an unknown or HOLD step id → unknown falls back to step 1; a HOLD step opens with its banner (Task 8).
3. `localStorage` blocked (private mode) → the page works, it just does not remember the step (Task 8).
4. Tapping Next repeatedly mid-animation → the current tween finishes instantly, no duplicated or half-placed parts (Task 8).
5. An interrupted earlier build left staging folders behind → the next build cleans them and succeeds (Task 7).

---

### Task 1: Part catalogue

**Files:** Create `MurphyBedQueen/assembly_parts.py`, `tests/__init__.py`, `tests/test_assembly_parts.py`

**Interfaces:**
- Produces: `Part` (dataclass: `id, label, assembly ('bed'|'bookcase'), min: tuple[float,float,float], max: tuple[float,float,float], stock: float, finish ('navy'|'natural')`); `load_parts(geometry: Path = ROOT/'output/drawing-geometry.json') -> dict[str, Part]`; `drilling_thickness(part) -> float`.

- [ ] **Step 1: Write failing tests** — `test_all_27_parts_loaded`; `test_name_mapping` (`'SC Left side'` → `L01`, `'1R Right side | 3/4 x 16 x 64'` → `M01`, `'3 Upper headboard — REQUIRED'` → `M05`); `test_boxes_match_geometry` (L04 min `(87.5, 0, 2.5)`, max `(116, 16, 3.25)` within 1e-6); `test_drilling_thickness` (L04 0.703, L11 0.46875, L06 0.21875); `test_l01_is_next_to_bed` (`L01.min[0] == M02.max[0]`); `test_finish` (L11–L15 natural, L04 and M01 navy); `test_assembly` (M* bed, L* bookcase).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_assembly_parts -v` → FAIL (module missing).
- [ ] **Step 3: Implement.** Strip text after `|` and ` — `, replace the `SC ` prefix with `Left cabinet: `, match `PART_SPECS` keys from `generate_cut_layouts` (id, label, and `stock` = the `PART_SPECS` thickness, so M07 is 0.625).
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: assembly guide part catalogue`.

### Task 2: Joints, holes and hole checks

**Files:** Modify `MurphyBedQueen/assembly_parts.py`; Test `tests/test_assembly_holes.py`

**Interfaces:**
- Produces: `Hole` (dataclass: `joint: str, part: str, surface ('face'|'edge'), kind ('dowel'|'clearance'|'pilot'|'transfer'|'stud'), through: bool, diameter, depth, countersink: bool, ref_edge: str, ref_end: str, u: float|None, v: float|None, world: tuple|None, axis: tuple[float,float,float], verified: str|None`) — `u`/`v`/`world` are `None` only for `transfer`/`stud` holes; `Joint` (dataclass: `id, side: str, panel: str, band: tuple[float,float], dowels: list[float], screws: list[float]`); `JOINTS` with `L04-L01, L04-L02, L07-L01, L07-L02, L03-L01, L03-L02`; `joint_holes(joint, parts) -> list[Hole]`; `check_holes(holes, parts, held_joints: set[str]) -> list[str]`.

- [ ] **Step 1: Write failing tests** —
  - `test_joint_hole_set`: per joint, the side gets 2 blind face dowel holes + 3 through clearance holes (countersunk); the panel gets 2 blind edge dowel holes + 3 blind pilots.
  - `test_positions_from_front`: L04-L01 dowels at world `y = 12, 4`, screws `y = 14, 8, 2`; side holes centred on L04's thickness (`z = 2.875`).
  - `test_depths`: face dowel 0.5, edge dowel 1.0625, pilot 1.25, clearance `through=True` depth 0.75.
  - `test_mirror_sides`: L04-L01 and L04-L02 holes mirror about `x = 101.75`; each side's `u` is measured from its own front edge.
  - `test_bands`: side hole z in band; moving one to z = 4.0 → `check_holes` reports "outside joint band".
  - `test_wall_rule`: 0.5 face hole in 0.703 passes; 0.625 fails "less than 1/8 in"; edge dowel passes (0.164 each side); a through clearance hole is not wall-checked.
  - `test_spacing`: two holes 0.75 in apart fail; pass when `verified="Rockler p. 12"`; pass when their joint is in `held_joints`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_assembly_holes -v` → FAIL.
- [ ] **Step 3: Implement.** Build holes in world space (contact plane = the side's inner face, datum `y = 16`), then project per part: on a face `u` across the width from `ref_edge`, `v` along the length from `ref_end`; on an edge `u` along the edge, centred in thickness. Sides: `ref_edge='front edge'`, `ref_end='bottom end'`; panels: `ref_edge='front edge'`, `ref_end='end at L01'`.
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: bookcase joints and hole checks`.

### Task 3: Fasteners and discrepancies

**Files:** Modify `MurphyBedQueen/assembly_parts.py`; Test `tests/test_assembly_fasteners.py`

**Interfaces:**
- Produces: `Fastener` (dataclass: `code, name, source ('kit'|'bought'|'bundled'), used: dict[str,int], bought: int, supplied: int | None`) — `supplied=None` means unknown until the hardware is chosen; the check treats an entry with unknown supply and non-empty `used` as an error; `load_fasteners(inventory: Path, bom: Path) -> dict[str, Fastener]`; `DISCREPANCIES` (BB, W, OO: `used`, `supplied`, `question`, `clear_when: list[str]`, `recorded: list[str]`); `check_fasteners(totals, fasteners, assemblies: set[str]) -> list[str]`; `discrepancy_holds() -> dict[str, str]`.

- [ ] **Step 1: Write failing tests** — `test_kit_codes_loaded` (T, U, V, W, Z, AA, BB, DD, EE, FF, II, JJ, KK, OO; KK supplied 12; OO supplied 0); `test_bought_codes` (`dowel` 50, `screw-8x2` 100, `screw-8x1.25` 25, `screw-8x1-washer` 25); `test_used_bookcase` (dowel 12, screw-8x2 18); `test_check_passes_bookcase`; `test_check_fails_mismatch` (dowel 10 → error names `dowel`); `test_used_exceeds_supply` (bundled used 8, supplied 0 → error); `test_w_banner_conditional` (mentions 88 used, 56 supplied, "possible shortage of 32", "confirm with Rockler"; does not contain "buy 32"); `test_w_banner_after_confirm` (recorded `confirmed-supply-56` → banner says "buy 32"); `test_bb_needs_length` (quantity recorded, length not → still held); `test_bundled_hold_entries` (`screw-slide`, `screw-pull`, `restraint-fasteners` exist with source `bundled`, empty `used`, and `check_fasteners` ignores them); `test_current_bom_loads` (the real BOM loads without error).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** reading `output/rockler-kit-inventory.csv` (`Code`, `Queen_quantity`) and fastener rows of `output/bill-of-materials.csv` through an explicit `Item` → code map: `3/8 x 1-1/2-inch dowels` → `dowel`, `#8 x 2-inch wood/cabinet screws` → `screw-8x2`, `#8 x 1-1/4-inch wood screws` → `screw-8x1.25`, `#8 x 1-inch washer-head wood screws` → `screw-8x1-washer`, `#6 x 1-1/4-inch wood screws` → `screw-6x1.25`, `#6 x 3/4-inch panel-attachment screws` → `screw-6x0.75`; `Slide mounting screws` → `screw-slide` (source `bundled`, bought 0, supplied unknown until the slide is chosen; used only by HOLD steps, so skipped by the check). Bundled entries `screw-pull` and `restraint-fasteners` are created in code with source `bundled`, bought 0, supplied 0, used `{}` (HOLD-only, skipped) until the pulls and restraint are chosen. Fastener rows are the BOM rows in category `Fasteners and adhesives`; `Wood glue` and `Removable threadlocker` are consumables (shown as step badges, not counted). Any other unmapped row in that category is an error. OO's inventory row is a requirement, not supply: `supplied = 0`, `used = 4`. **Step 4: Run** → PASS. **Step 5: Commit** `feat: fastener catalogue and discrepancy holds`.

### Task 4: Bookcase steps, validation and HOLD propagation

**Files:** Create `MurphyBedQueen/assembly_steps.py`, `MurphyBedQueen/assembly_guide.py`; Modify `MurphyBedQueen/assembly_parts.py` (`OPEN_DECISIONS`); Test `tests/test_assembly_steps.py`

**Interfaces:**
- Produces: `OPEN_DECISIONS` (ids `back`, `slide`, `shelf-pins`, `restraint`, `plinth`, `drawer-box`, `pulls`, `pilot-depth`, `screw-tips`, `kit`); `ACTIVE_ASSEMBLIES = {'bookcase'}`; `STEPS` (spec model plus `drill: list[{'joint', 'part'}]` and `consumables: list[str]` from `{'glue', 'threadlocker'}`); `POSES` (`'bench-1'`, `'bench-2'`: part lying inside-face-up on the floor, 30 in and 50 in beyond the outer end, so the two sides never overlap); `ResolvedStep` (dataclass: `step, held_by: list[str], drilled: list[Hole], joined: list[Hole], hardware: list[dict], poses: dict[str,str]`); `resolve(steps, parts, fasteners) -> list[ResolvedStep]`; `validate(resolved, parts, fasteners) -> list[str]`.

Drilling rule: a joint's side-face and clearance holes belong to the step listing `{'joint', 'part': side}` in `drill`; its panel-edge dowel holes and pilots belong to the step that lists the joint in `joints`.

- [ ] **Step 1: Write failing tests** —
  - `test_bookcase_step_order`: `bookcase-drill`, `bookcase-drill-shelf`, `bookcase-bottom`, `bookcase-plinth`, `bookcase-shelf`, `bookcase-top`, `bookcase-right-side`, `bookcase-back`, `bookcase-drawer-box`, `bookcase-slides`, `bookcase-drawer-pull`, `bookcase-shelves`, `bookcase-place`.
  - `test_completeness_active_only`: L01–L16 each added once; M01–M11 never added and no error.
  - `test_step_joints`: `bookcase-drill` drills L04/L03 joints on L01 and L02; `bookcase-drill-shelf` L07-L01, L07-L02; `bookcase-bottom` joins L04-L01; `bookcase-shelf` L07-L01; `bookcase-top` L03-L01; `bookcase-right-side` L04-L02, L07-L02, L03-L02.
  - `test_bench_poses`: L01 `bench-1` in `bookcase-drill` and `bookcase-drill-shelf`, installed from `bookcase-bottom`; L02 `bench-2` from `bookcase-drill` until `bookcase-right-side`, installed from it; the two bench boxes do not intersect.
  - `test_holds`: ready = `bookcase-drill`, `bookcase-bottom`, `bookcase-top`; `bookcase-drill-shelf`, `bookcase-shelf`, `bookcase-right-side`, `bookcase-slides` held by `slide`; plinth→`plinth`, back→`back`, drawer-box→`drawer-box`, drawer-pull→`pulls`, shelves→`shelf-pins`, place→`restraint`.
  - `test_requires_chain`: `bookcase-back`, `-drawer-box`, `-slides`, `-drawer-pull`, `-shelves` and `-place` declare `requires: ['bookcase-right-side']`; with their own decisions marked resolved in a test copy of `OPEN_DECISIONS`, each is still held by `slide` through that link.
  - `test_rejects` unknown part, unknown joint, part added twice, unknown `requires` id.
  - `test_fastener_totals`: bookcase totals 12 dowels, 18 #8 × 2 in; `validate` returns `[]`.
  - `test_consumables`: `bookcase-bottom`, `-shelf`, `-top`, `-right-side` list `glue`; an unknown consumable is rejected.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** Holds propagate from a step's own `hold`, from any held joint/part it drills, joins or adds, and transitively through `requires`. Step text uses tape IDs and physical words ("the side against the bed", "the outer end"). **Step 4: Run** → PASS. **Step 5: Commit** `feat: bookcase steps with hold propagation`.

### Task 5: GLB writer

**Files:** Create `MurphyBedQueen/assembly_glb.py`; Test `tests/test_assembly_glb.py`

**Interfaces:**
- Produces: `build_glb(parts, resolved) -> bytes` — one node per part (name = id) and per hardware instance (`<joint>-<kind>-<n>`, e.g. `L04-L01-dowel-1`), installed positions; materials `navy`, `natural`, `hardware`, `context`; `read_glb(data) -> dict`.

- [ ] **Step 1: Write failing tests** — `test_magic_and_chunks` (`glTF`, version 2, aligned JSON + BIN); `test_node_names` (27 parts + 12 dowel + 18 screw nodes); `test_axis_map` (L04 bounds `(-116, 2.5, 0)…(-87.5, 3.25, 16)` × 0.0254); `test_materials` (L11 natural, L04 navy, M01 context, dowels hardware); `test_accessor_bounds_present`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** boxes (24 vertices with normals) and 16-sided cylinders with `struct`, glTF layout as `export_web_models.GlbWriter`. **Step 4: Run** → PASS. **Step 5: Commit** `feat: stdlib GLB writer`.

### Task 6: SVG drawings

**Files:** Create `MurphyBedQueen/assembly_drawings.py`; Test `tests/test_assembly_drawings.py`

**Interfaces:**
- Produces: `step_svg(index, resolved, parts) -> str`; `holes_svg(rs, parts) -> str | None` — a close-up of every hole the step drills (its `drill` holes and the panel-edge holes of the joints it makes); `None` when it drills nothing.

- [ ] **Step 1: Write failing tests** — `test_svg_parses`; `test_contains_new_part_ids`; `test_classes` (`bookcase-top`: L04 `done`, L03 `new`); `test_hardware_panel` (`bookcase-bottom`: `×2` dowel, `×3` screw); `test_hole_closeup` (`bookcase-drill`: `4"`, `12"`, `Ø3/8 × 1/2 deep`, `Ø3/16 through, countersink`, band note "keep shelf-pin rows and slide screws out"); `test_joint_step_closeup` (`bookcase-top` close-up shows L03's edge dowels `Ø3/8 × 1 1/16 deep` and pilots `Ø1/8 × 1 1/4 deep`); `test_no_holes_svg` (`bookcase-shelves` → `None`); `test_hold_banner` (`bookcase-back` contains `HOLD` and the decision text); `test_depth_order`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** isometric view from the room side, outer end and above: eye direction `d = (−1, −1, −1)/√3` in Fusion axes; `sx = (y − x)·cos30°`, `sy = (x + y)·sin30° − z` (SVG coordinates); draw boxes sorted by `dot(centre, d)` descending (`test_depth_order` pins this). New parts offset along `move` with arrows; fractions via `generate_cut_layouts.inches`. **Step 4: Run** → PASS. **Step 5: Commit** `feat: exploded and hole drawings`.

### Task 7: Staged generation

**Files:** Create `MurphyBedQueen/generate_assembly_guide.py`; Test `tests/test_generate_assembly_guide.py`

**Interfaces:**
- Produces: `generate(out_dir: Path = ROOT/'output/assembly-guide') -> dict` (`steps`, `holds`, `files`); writes `assembly.glb`, `assembly-steps.json` (`[{id, title, adds, hardware: [{code, count, nodes, phase ('dowel'|'panel'|'screw')}], poses: {node: [16 floats]}, move, camera, text, warnings, consumables, hold: [banners], requires, source, svg, holes_svg: str|null}]`), `step-NN.svg`, `step-NN-holes.svg` (drilling steps only). CLI prints the summary; exit 1 on errors.

- [ ] **Step 1: Write failing tests** — `test_generates_all_files` (13 step SVGs, holes SVGs for the 6 steps that drill (`bookcase-drill`, `-drill-shelf`, `-bottom`, `-shelf`, `-top`, `-right-side`), JSON has 13 steps with `holes_svg: null` elsewhere, GLB parses); `test_clean_checkout`; `test_stale_files_removed`; `test_failure_keeps_previous` (forced validation error → raises, previous files unchanged, no staging or backup folders left); `test_leftover_staging_cleaned` (current dir present plus leftover `assembly-guide.staging-x` and `assembly-guide.backup-x` → generate succeeds and removes them); `test_interrupted_swap_restored` (current dir absent, `assembly-guide.backup-x` present → the backup is restored before anything else, then generation proceeds); `test_hold_count` (`holds == 10`); `test_json_consumables` (`bookcase-bottom` JSON has `consumables: ['glue']`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** in this order: (1) if the current dir is absent and a `.backup-*` exists, rename the newest backup back into place; (2) remove leftover `assembly-guide.staging-*`/`.backup-*`; (3) only then `tempfile.mkdtemp(dir=out_dir.parent, prefix='assembly-guide.staging-')`; validate the full set (parse every SVG, `read_glb`, JSON ids == `STEPS`); rename current → backup (skip if absent), staging → current, delete backup; on failure restore the backup; `finally` removes the staging dir. **Step 4: Run** → PASS. **Step 5: Commit** `feat: staged assembly guide generation`.

### Task 8: Viewer page, offline cache and site build

**Files:** Create `site/content/build-steps.html`, `site/assets/assembly-viewer.js`, `site/sw.js` (template), `site/assets/vendor/three/` keeping three.js's own layout so relative imports resolve: `build/three.module.min.js`, `examples/jsm/controls/OrbitControls.js`, `examples/jsm/loaders/GLTFLoader.js`, `examples/jsm/utils/BufferGeometryUtils.js` (three@0.170.0); import map `"three": "./assets/vendor/three/build/three.module.min.js"`; Modify `site/build.py`; Test `tests/test_site_build.py`

**Interfaces:**
- Consumes: `generate(out_dir)`, Task 7 JSON.
- Produces: `PAGES` entry `('build-steps', 'Step-by-step', 'Step-by-step assembly', 'Interactive 3D steps for the bed and bookcase.')`; `validate_site(dest: Path, fragments: dict[str, set[str]])`; published `assembly-guide/` and root `sw.js`.

- [ ] **Step 1: Write failing tests** — `test_build_publishes_guide`; `test_build_does_not_touch_output` (a failed site validation leaves `output/assembly-guide/` unchanged); `test_validates_staged_dir` (a broken link in the staged page fails the build and leaves the previous `_site` unchanged); `test_step_fragments` (`build-steps.html#bookcase-drill` passes, `#nope` fails validation); `test_importmap_and_scripts`; `test_sw_precache` (lists the page, `assets/style.css`, `assets/guide.js`, `assets/favicon.svg`, viewer, all four three.js modules at their vendored paths (`assets/vendor/three/build/three.module.min.js`, `…/examples/jsm/controls/OrbitControls.js`, `…/examples/jsm/loaders/GLTFLoader.js`, `…/examples/jsm/utils/BufferGeometryUtils.js`), GLB, JSON, every SVG; cache name contains a SHA-256 prefix over the bytes of every precached file, in list order; `test_sw_hash_tracks_assets` (changing only `assets/style.css` changes `sw.js`); `activate` deletes other `guide-` caches); `test_leftover_tmp_cleaned`; `test_guide_footer` (`build-steps.html` footer says the steps are drawn from the Rockler manual and this project's design and does not say "use this guide alongside"; other pages keep their footer).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `site/build.py`.** Remove leftover `_site.tmp-*`; build into `tempfile.mkdtemp(dir=SITE, prefix='_site.tmp-')`; call `generate(tmp / 'assembly-guide')` so the guide is generated inside the site staging dir (the canonical `output/assembly-guide/` is written only by the generator CLI); render `sw.js`; give `render()` a per-slug footer so `build-steps` uses the source-note wording; `validate_site(tmp, {'build-steps.html': step ids})`; swap into `site/_site` (backup/restore as Task 7); `finally` removes the temp dir.
- [ ] **Step 4: Implement the viewer.** Per step: earlier nodes solid at their step pose, later nodes hidden, inactive-assembly nodes faint; existing nodes whose pose changes (L02 bench → installed) tween to the new pose; new parts animate in three phases — dowels slide into their holes, the panel slides in along `move`, screws advance and spin — in an accent colour, then settle to their finish. Camera eases to `camera`; double-tap resets it. "Show finished" toggle shows every node installed. `#<step id>` deep links (unknown → step 1); last step in `localStorage` inside try/catch; Back/Replay/Next + swipe; Next during a tween completes it first; `prefers-reduced-motion` skips tweens. HOLD banner, part chips (tap flashes node), hardware counts, consumable badges (glue, threadlocker), text, warnings, SVGs with tap-to-fullscreen; register `sw.js`.
- [ ] **Step 5: Run** `python3 -m unittest discover tests -v` and `python3 site/build.py` → all pass, "Validated 7 pages".
- [ ] **Step 6: Browser check** (ml:agent-browser, `python3 -m http.server` in `site/_site`), 390×844 and 1280×800: all 13 steps, no console errors; L01 and L02 on separate bench spots in steps 1–2, L01 installed from step 3, L02 on the bench through step 6 and installed at step 7; `#bookcase-back` shows the HOLD banner; `#nope` opens step 1; Next ×5 fast → step 6 state, no duplicate nodes; double-tap resets camera; "show finished" shows all; reduced motion → no tween; storage disabled → still steps; offline reload after one visit keeps the full layout. Screenshots in `.tmp/`.
- [ ] **Step 7: Commit** `feat: interactive step-by-step page with offline cache`.

### Task 9: Docs

**Files:** Modify `README.md`, `site/content/assembly.html`

- [ ] **Step 1:** README: add `python3 MurphyBedQueen/generate_assembly_guide.py` (also run by `site/build.py`) and the test command; bookcase note: L02 is the visible outer end, L01 sits against the bed (fill screw holes on L02's outer face); bed dowel face holes are 1/2 in deep (not Rockler's 5/8) with 1 1/16 in edge holes.
- [ ] **Step 2:** `assembly.html`: Stage 4 links `build-steps.html#bookcase-drill` and applies the L01/L02 correction; the bed-cabinet stage states the 1/2 in face / 1 1/16 in edge depths and keeps its hole-location text until the Phase 2 bed steps replace it.
- [ ] **Step 3:** `python3 site/build.py` → validates. **Step 4: Commit** `docs: point to the step-by-step guide and 1/2 in face holes`.
