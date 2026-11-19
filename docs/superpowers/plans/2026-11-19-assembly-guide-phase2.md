# Interactive Assembly Guide — Phase 2 (bed cabinet) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use ml:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the bed cabinet to the step-by-step guide, from drilling the sides to the wall brackets. That means 9 steps, with the Rockler mounting plates, the inserts and wall anchoring. The engine is generalised first so that the bookcase output stays byte-identical.

**Architecture:** Phase 1's engine assumes bookcase joints: contact along x, a run along y from the front edge, and fixed spacing. Phase 2 makes four changes:
- **Stages:** parts, fasteners and steps get a stage (`bookcase`, `bed-cabinet`, `bed-mechanism`), so the bed cabinet can be checked while the mechanism waits for Phase 3.
- **Joints:** a joint finds its own contact axis, run axis and datum end.
- **Hole patterns:** a new `Pattern` type covers holes that belong to no joint: Rockler's insert layout and the stud-located anchoring holes.
- **Steel shapes:** a small catalogue of steel shapes (mounting plates I, wall brackets HH).

Hardware inherits its host part's pose, so a plate fitted on the bench travels with its side.

**Tech Stack:** Python 3 standard library, vanilla ES modules, Three.js 0.170.0 (already vendored), GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-11-18-interactive-assembly-guide-design.md` (Phasing item 2; Step list "Bed cabinet"). Phase 1 plan: `docs/superpowers/plans/2026-11-18-assembly-guide-phase1.md`.

## Global Constraints

- Everything in Phase 1's Global Constraints still holds: stdlib only, axis map `(x, y, z) -> (-x, z, y)` × 0.0254, dowel 3/8 in × 1/2 in face / 1 1/16 in edge, #8 × 2 in clearance 3/16 through with a countersink outside and a 1/8 in × 1 1/4 in pilot, the wall rule ≥ 1/8 in, spacing ≥ 1 in, and the 0.703 in drilling thickness.
- Bed cabinet geometry (from `drawing-geometry.json`):
  - sides: M01 (`1R Right side`) at x 0–0.75 and M02 (`1L Left side`) at x 86–86.75, both 16 deep × 64 tall;
  - top M03 at z 63.25–64 and bottom M04 at z 0–0.75;
  - upper headboard M05 at y 0–0.75, z 47.25–63.25, and lower headboard M06 at y 0–0.75, z 0.75–16.75;
  - the wall is the plane y = 0 and the front edge is y = 16.
- Bed joints:
  - 8 side joints: M03, M04, M05 and M06 each to M01 and to M02;
  - 2 headboard joints: M05-M03 and M06-M04;
  - totals: 22 dowels, 32 #8 × 2 in screws.
  - Side joints use dowels at 4 and 12 in and screws at 2, 8 and 14 in from the datum. The datum is the front edge for the top and bottom, and the lower end for the headboards.
  - Headboard joints (85 1/4 in run, datum = the end at M01) have dowels at 1/4, 1/2 and 3/4 of the run, and screws 3 in from each end and at 1/3 and 2/3. The top or bottom takes the face holes and the clearance holes; the headboard takes the edge holes.
- Insert pattern (Rockler p. 8 drilling guide, the same on both sides, measured on the inside face):
  - `u` from the front edge and `v` up from the bottom end, in inches: (9 7/16, 11 7/16), (9 7/16, 17 11/16), (9 7/16, 25 1/4), (9 7/16, 27 3/4), (9 7/16, 30 1/4), (3 1/8, 11 7/16), (3 1/8, 13 7/8), (6 15/16, 17 11/16);
  - each hole is 27/64 in diameter × 9/16 in deep (leaves 0.1405 in);
  - `verified="Rockler p. 8"`;
  - the four column holes above (9 7/16, 11 7/16) and the hole at (3 1/8, 11 7/16) take their `u` from alignment on the drawing, not a printed dimension: `aligned=True`;
  - the undimensioned dark dot in the column is not a hole.
- Lag bolts (Rockler p. 11): one 3/16 in hole through the headboard at each stud line, 3 in down from the top of M05 (z 60.25) and 3 in up from the bottom of M06 (z 3.75): 6 KK.
- Wall brackets (Rockler p. 12, Fig. 6), on M03's top face along each stud line, measured from the wall:
  - A4 at 1 1/2 in: 1/8 in pilot;
  - A3 at 2 3/4 in: 1/8 in pilot;
  - A2 at 4 in: 5/16 in through;
  - A1 at 4 5/8 in: 13/64 in steel-dowel hole.
  - Blind depth is the proposed 1/2 in under decision `pilot-depth` (Rockler: 5/8 in).
  - Each bracket takes 2 JJ (A3, A4), 1 II (A2, from below) and 2 KK into the wall through A5/A6, which are marked through the bracket (no Rockler dimension).
- Stud-located holes have no cabinet x. Use `EXAMPLE_STUDS = (11.375, 43.375, 75.375)` for 3D placement only, never for checks or dimensions.
- Stage used quantities, cabinet: dowel 22, `screw-8x2` 32, T 16, U 16, KK 12, II 3, JJ 6. Bookcase: dowel 12, `screw-8x2` 18. Every other kit code and `screw-8x1.25` are `bed-mechanism`.
- Active stages after this phase: `{'bookcase', 'bed-cabinet'}`. `bed-mechanism` parts (M07–M11) are left out of the GLB and the drawings until Phase 3.
- Every bed step has a `source` ("Rockler p. N"). Bed steps come before the bookcase steps, and `bookcase-place` requires `bed-wall-brackets`.

## Review Focus

1. A phone that saved `bookcase-top` in Phase 1 opens `bookcase-top`, not whatever is now step N, because steps are remembered by id (Task 7 browser check).
2. "Show finished" and the bookcase steps never show the M07–M11 door panels across the cabinet front (Task 3 `test_pending_parts_omitted`).
3. A stud-located hole never shows an x dimension along the cabinet; its drawing says "on each stud line" (Task 6 `test_stud_closeup`).
4. Moving M01 from the bench to the cabinet carries its plate I-R and its 8 T and 8 U with it (Task 5 `test_host_poses`, Task 7 browser check).
5. Placing the bookcase before the bed is anchored is never shown as ready (Task 5 `test_place_requires_anchoring`).

---

### Task 1: Stages, and a drift check on the committed output

**Files:**
- Modify `MurphyBedQueen/assembly_parts.py`, `assembly_steps.py`, `assembly_guide.py`, `assembly_glb.py`, `assembly_drawings.py`.
- Test: `tests/test_assembly_stages.py`, `tests/test_output_drift.py`, plus updates to existing tests that read `assembly`.

**Interfaces:**
- Produces:
  - `Part.stage` (`'bookcase'|'bed-cabinet'|'bed-mechanism'`): M01–M06 `bed-cabinet`, M07–M11 `bed-mechanism`, L* `bookcase`. `Part.assembly` stays as it is.
  - `Fastener.used: dict[stage, int]`.
  - Step key `stage` replaces `assembly`.
  - `st.ACTIVE_STAGES` replaces `ACTIVE_ASSEMBLIES`, still `{'bookcase'}` in this task.
  - `fastener_totals` keyed by stage.

- [ ] **Step 1: Write the failing tests.**
  - `test_part_stages`;
  - `test_used_by_stage`: dowel `{'bed-cabinet': 22, 'bookcase': 12}`, T `{'bed-cabinet': 16}`, BB `{'bed-mechanism': 34}`, `screw-8x1.25` `{'bed-mechanism': 4}`;
  - `test_step_stage_key`: an `assembly` key is rejected as an unknown key;
  - `test_committed_output_matches` (in `tests/test_output_drift.py`): `generate()` into a temp dir equals every file in `output/assembly-guide/` byte for byte, and the file lists match. It passes already. Tasks 1, 2 and 4 must not change the output; every task that does change it regenerates and commits `output/assembly-guide/`, so this test stays green throughout.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_assembly_stages -v`. Expect FAIL.
- [ ] **Step 3: Implement.** `KIT_STAGE = {'T','U','KK','II','JJ'} -> 'bed-cabinet'`; every other kit code goes to `bed-mechanism`. Map the `BOM_FASTENERS` used dicts by stage. Every filter that read `assembly in ACTIVE_ASSEMBLIES` now reads `stage in ACTIVE_STAGES`.
- [ ] **Step 4: Run** `python3 -m unittest discover tests -v`. Expect all PASS, including the drift test (no output change).
- [ ] **Step 5: Commit** `refactor: stages for parts, fasteners and steps; committed-output drift test`.

### Task 2: General joints and the bed joints

**Files:**
- Modify `MurphyBedQueen/assembly_parts.py`, `assembly_glb.py` (`hardware_meshes`), `generate_assembly_guide.py` (`hardware_axis`).
- Test: `tests/test_assembly_joints.py`, plus `tests/test_assembly_holes.py`: its joint-set and 10-holes-per-joint assertions are limited to the six bookcase joints.

**Interfaces:**
- Produces:
  - `Joint(id, side, panel, dowels, screws, band=None, hold=None)`. `side` is the part that takes the face and clearance holes.
  - `joint_geometry(joint, parts) -> JointGeometry(contact_axis: int, contact: float, direction: ±1, run_axis: int, datum: float, run_sign: ±1, centre: (float, float, float), datum_name: str)`.
  - The datum rule:
    - run along y: datum at the max y, "front edge";
    - run along z: datum at the min z, "lower end";
    - run along x: datum at the min x, "end at M01".
  - The run axis is the longer of the two overlap extents. Holes are centred on the overlap in the third axis.
  - `Hole` gains `located: str = 'rule'` (`'rule'|'rockler'|'stud'|'transfer'`), `aligned: bool = False` and `example: tuple|None = None`.
  - `headboard_joint(panel, side)` computes the fraction positions from the run length.
  - `JOINTS` adds `M03-M01, M04-M01, M05-M01, M06-M01, M03-M02, M04-M02, M05-M02, M06-M02, M05-M03, M06-M04`.
  - `hardware_axis` reads the axis from the hardware item's holes, no longer by parsing node names.

- [ ] **Step 1: Write the failing tests.**
  - `test_bookcase_unchanged`: for every bookcase joint, hole world, `u`, `v`, axis, depth and labels equal the Phase 1 values (the drift test also covers this).
  - `test_side_horizontal`: M03-M01 has its dowels at world `y = 12, 4`, `z = 63.625`, entering M01 at `x = 0.75` along `-x`, with edge dowels into M03 along `+x`.
  - `test_side_headboard`: M05-M01 has its dowels at `z = 51.25, 59.25` and screws at `z = 49.25, 55.25, 61.25`, all at `y = 0.375`. The M06-M01 screws are at `z = 2.75, 8.75, 14.75`. The datum name is "lower end".
  - `test_headboard_joint`: M05-M03 has its contact at `z = 63.25`, dowel `x = 0.75 + 85.25 × (1/4, 1/2, 3/4)`, screw `x = 3.75, 0.75 + 85.25/3, 0.75 + 2 × 85.25/3, 83.0`, and `y = 0.375`. Face dowels go into M03 along `+z`, 1/2 deep; clearance through M03 is countersunk; edge dowels go into M05 along `-z`, 1 1/16 deep.
  - `test_bed_mirror`: the M0x-M01 and M0x-M02 holes mirror about `x = 43.375`.
  - `test_bed_checks_pass`: `check_holes` over all 10 bed joints returns `[]`.
  - `test_bed_counts`: the 10 joints sum to 22 dowels and 32 screws.
  - `test_no_contact`: a joint between parts that do not touch, or that touch only along an edge or at a corner, raises `ValueError` naming both.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_assembly_joints -v`. Expect FAIL.
- [ ] **Step 3: Implement.** Find the contact axis where `side.max == panel.min` or `side.min == panel.max` and both other extents overlap by a positive length. `ref_edge` and `ref_end` come from the datum name, and `u` is the distance from the datum along the run. `hardware_meshes` uses `joint_geometry` instead of the fixed x axis. `check_holes` checks bands only when `joint.band` is set.
- [ ] **Step 4: Run** `python3 -m unittest discover tests -v`. Expect all PASS, with the drift test still identical.
- [ ] **Step 5: Commit** `feat: general joint geometry and the bed cabinet joints`.

### Task 3: Hole patterns, steel shapes and pending parts

**Files:**
- Modify `MurphyBedQueen/assembly_parts.py`, `assembly_glb.py` (`build_glb`), `generate_assembly_guide.py` (`check_outputs`), and `output/assembly-guide/` (regenerated).
- Test: `tests/test_assembly_patterns.py`, `tests/test_assembly_parts.py` (part count), `tests/test_assembly_glb.py`.

**Interfaces:**
- Produces:
  - `Pattern(id, part, holes: list[Hole], hardware: list[Fixing], hold=None, source: str)`.
  - `Fixing(code, kind, at)`. `kind` is a glyph name: `'insert'|'screw'|'lag'|'bolt'`. `at` is either `'all'` (one node per hole) or a tuple of hole names (one node per named hole, per stud).
  - `Hole` gains `name: str | None` (`'A1'`…`'A6'` on bracket holes).
  - `PATTERNS`:
    - `inserts-M01`, `inserts-M02`: T and U per hole;
    - `lag-M05`, `lag-M06`: KK per stud;
    - `brackets-M03`: holes A1–A6 per stud, with `Fixing('II','bolt',('A2',))`, `Fixing('JJ','screw',('A3','A4'))` and `Fixing('KK','lag',('A5','A6'))`. A1 takes the bracket's own steel dowel.
  - A5 and A6 are wall holes:
    - `part='wall'`, `located='transfer'`, 3/16 in pilots, marked through the fitted bracket (Rockler gives no dimension);
    - their `example` is on the bracket leg at the stud, `y = 0`, at `z = 65.0` (A5) and `z = 66.5` (A6);
    - `check_holes` skips `part='wall'` holes.
  - `pattern_holes(pattern_id, parts) -> list[Hole]`.
  - `STEEL`: a dict of `Part`-compatible entries with `finish='steel'`, `stage='bed-cabinet'`, `host: str`, `boxes: list[(lo, hi)]` and `representative: bool`:
    - `I-R` on M01 and `I-L` on M02: a column `u` 8.75–10.125 and `v` 10.875–31.0, plus a foot `u` 2.5–10.125 and `v` 10.875–12.25, 3/16 in thick on the inside face;
    - `HH-1`…`HH-3` at the example studs: a foot 1 1/4 wide × 5 1/4 from the wall on M03's top, and a leg 3 in up the wall, both 3/16 thick.
  - `load_parts()` includes `STEEL`. Wood parts get `boxes = [(min, max)]` and `host = None`.
  - `PENDING_STAGES = {'bed-mechanism'}`.
  - `build_glb` omits pending-stage parts. It writes multi-box meshes, and material `steel` = `[0.55, 0.57, 0.6, 1]` for steel in an active stage, `context` otherwise.
  - `check_outputs` expects only the parts the GLB emits.

- [ ] **Step 1: Write the failing tests.**
  - `test_insert_pattern`: 8 holes per side, at the Global Constraints values. The M01 and M02 sets have identical `(u, v)`. Each hole is 27/64 × 9/16 and leaves 0.1405 in. Exactly the 5 alignment holes have `aligned=True`. All carry `verified='Rockler p. 8'`.
  - `test_insert_checks`: `check_holes` passes; moving one hole to `v = 0.2` fails "not on its face".
  - `test_lag_pattern`: per headboard, 3 through holes of 3/16 in with `located='stud'`, `u=None`, `world=None`, and `example` on the M05 front face at `z = 60.25` (M06: `z = 3.75`) at each example stud.
  - `test_bracket_pattern`:
    - A1–A4 at `v` 4.625, 4.0, 2.75 and 1.5 from the wall;
    - A1, A3 and A4 blind at 1/2 in (leaves 0.203), A2 through;
    - A5 and A6 are wall transfer holes at distinct examples;
    - the pattern hold is `pilot-depth`.
  - `test_stud_holes_skip_spacing_and_position`: `check_holes` on stud holes runs only the wall rule. A stud hole 5/8 in deep in M03 reports "less than 1/8 in".
  - `test_steel_shapes`: `I-R` and `I-L` lie on their side's inside face within the side's outline. `HH-n` sits on M03's top at `z = 64`, against the wall. Every steel part has `representative=True`.
  - `test_part_count` (in `test_assembly_parts`): 27 wood + 5 steel.
  - `test_pending_parts_omitted` (in `test_assembly_glb`): no M07–M11 node; the steel nodes are present.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_assembly_patterns tests.test_assembly_glb -v`. Expect FAIL.
- [ ] **Step 3: Implement.** Stud holes keep `world=None` and `u=None`; `v` is the fixed offset (from the wall, or from the headboard's top or bottom); `example` is the 3D position at the example stud. In `check_holes`, holes with `world=None` get only the depth/wall rule (face holes against `drilling_thickness`), and wall holes get none.
- [ ] **Step 4: Regenerate** with `python3 MurphyBedQueen/generate_assembly_guide.py`. The GLB changes: M07–M11 drop out and 5 context steel nodes appear. Then run `python3 -m unittest discover tests -v` and expect all PASS, drift test included.
- [ ] **Step 5: Commit** `feat: Rockler insert pattern, stud-located anchoring holes, steel shapes; pending parts left out`.

### Task 4: GLB hardware for patterns

**Files:**
- Modify `MurphyBedQueen/assembly_glb.py`.
- Test: `tests/test_assembly_glb.py`.

**Interfaces:**
- Produces:
  - `pattern_meshes(pattern, parts) -> dict[node name, mesh]`. Nodes are named `<pattern>-<code>-<n>`, in hole order and then stud order.
  - Shapes:
    - T: a 0.42 × 0.5625 in cylinder in its hole;
    - U: an M8 screw;
    - II: a 1/4 in bolt up through A2;
    - JJ: a #12 × 3/4 in screw;
    - KK: a 1/4 × 3 in lag, along the hole axis.
  - Stud and wall holes use `example`.
  - `build_glb` adds `pattern_meshes` for every pattern a resolved step lists in `fix`. No step does yet, so the output is unchanged.

- [ ] **Step 1: Write the failing tests.**
  - `test_insert_at_hole`: the centre of `inserts-M01-T-1` equals its hole world, mapped to the scene.
  - `test_pattern_node_counts`: `inserts-M01` 8 T + 8 U; `lag-M05` 3 KK; `brackets-M03` 3 II + 6 JJ + 6 KK.
  - `test_wall_lags_distinct`: the six bracket KK nodes have six distinct centres, two per stud, on the wall plane `y = 0`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_assembly_glb -v`. Expect FAIL. **Step 3: Implement** with `box_mesh` and `cylinder_mesh`.
- [ ] **Step 4: Run** `python3 -m unittest discover tests -v`. Expect all PASS, drift test included. **Step 5: Commit** `feat: GLB hardware for hole patterns`.

### Task 5: Bed cabinet steps, host poses and holds

**Files:**
- Modify `MurphyBedQueen/assembly_steps.py`, `assembly_guide.py`, `generate_assembly_guide.py` (pose JSON), and `output/assembly-guide/` (regenerated).
- Test: `tests/test_bed_steps.py`, plus updates to `tests/test_assembly_steps.py`, the hold count and file counts in `tests/test_generate_assembly_guide.py`, and the node count in `tests/test_assembly_glb.py`.

**Interfaces:**
- Consumes: `JOINTS`, `PATTERNS`, `STEEL`, `pattern_meshes` (Tasks 2–4).
- Produces:
  - `ACTIVE_STAGES = {'bookcase', 'bed-cabinet'}`.
  - New step keys:
    - a `drill` entry may be `{'pattern': id}` (its holes go into `drilled`);
    - `fix: list[pattern id]` creates hardware nodes `<pattern>-<code>-<n>`, counted toward the totals.
  - The existing drilling rule is unchanged: a step that lists a joint in `joints` drills that joint's panel-edge holes, so `bed-right-side` and `bed-left-side` have `joined` holes and get a holes drawing.
  - `ResolvedStep.poses` covers every visible node (parts, steel and hardware). A steel part or hardware node takes its host's pose name: a joint's nodes take the joint's side, and a pattern's nodes take the pattern's part.
  - `ResolvedStep.hosts: dict[node, host part id]`.
  - The generator's JSON `poses` computes each node's matrix with `pose_matrix(parts[hosts[node]], pose)`.
  - `_rotation` uses the side's own stage centre (bookcase 101.75, bed cabinet 43.375).
  - The bench poses are reused for M01 and M02.
  - Each hardware item's `axis` comes from its holes.

Steps, in order, before `bookcase-drill`:

| id | adds | drill / joints / fix | pose | hold | requires | source |
|---|---|---|---|---|---|---|
| `bed-drill-sides` | M01, M02 | drill side holes of the 8 side joints | M01 `bench-1`, M02 `bench-2` | — | — | Rockler p. 10 |
| `bed-inserts` | I-R, I-L | drill + fix `inserts-M01`, `inserts-M02` | hosts | — | — | Rockler pp. 7–8 |
| `bed-top-headboard` | M03, M05 | drill M05-M03 (M03); join M05-M03 | installed | — | — | Rockler p. 9 |
| `bed-bottom-headboard` | M04, M06 | drill M06-M04 (M04); join M06-M04 | installed | — | — | Rockler p. 9 |
| `bed-right-side` | — | join M03-M01, M04-M01, M05-M01, M06-M01 | M01 → installed | — | — | Rockler p. 10 |
| `bed-left-side` | — | join the four M0x-M02 joints | M02 → installed | — | — | Rockler p. 10 |
| `bed-stand-up` | — | — | — | — | `bed-left-side` | Rockler p. 11 |
| `bed-lag-bolts` | — | drill + fix `lag-M05`, `lag-M06` | — | — | `bed-stand-up` | Rockler p. 11 |
| `bed-wall-brackets` | HH-1…3 | drill + fix `brackets-M03` | — | `pilot-depth` (pattern), `screw-tips` (step) | `bed-lag-bolts` | Rockler p. 12 |

- [ ] **Step 1: Write the failing tests.**
  - `test_bed_step_order`: the 9 ids above, then the 13 bookcase ids.
  - `test_bed_completeness`: M01–M06, I-R, I-L and HH-1…3 are each added once. M07–M11 are never added, with no error.
  - `test_stage_totals`: `bed-cabinet` dowel 22, `screw-8x2` 32, T 16, U 16, KK 12, II 3, JJ 6, and `validate` returns `[]`.
  - `test_host_poses`: in both `bed-inserts` and `bed-right-side`, every node hosted by M01 (I-R, all 16 `inserts-M01-*` nodes) has the same pose name and the same scene matrix as M01: `bench-1`, then `installed`. M02 and its nodes stay at `bench-2` through `bed-right-side` and are `installed` from `bed-left-side`.
  - `test_bed_holds`: only `bed-wall-brackets` is held, by `pilot-depth` and `screw-tips`. The total HOLD count is 11.
  - `test_place_requires_anchoring`: `bookcase-place` requires `bed-wall-brackets`; with `restraint` resolved in a test copy, it is still held by `pilot-depth`.
  - `test_bed_sources`: every `bed-*` step has a non-empty source.
  - `test_safety_warnings`:
    - `bed-inserts` warns not to use wood screws for the plates;
    - `bed-stand-up` says two adults and plumb the front edges with shims;
    - `bed-lag-bolts` and `bed-wall-brackets` say wooden studs only, no drywall anchors, no masonry or metal studs, no impact driver, do not overtighten, and at least three studs;
    - `bed-wall-brackets` says flush on the top and flush to the wall with all six fasteners, and to mark A5 and A6 through the bracket.
  - `test_aligned_note`: `bed-inserts` text tells the builder to lay the plate on the marks and check every hole lines up before drilling.
  - `test_hardware_poses_in_json`: in `bed-inserts`, the JSON poses include `inserts-M01-T-1`, equal to the pose of `M01`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_bed_steps -v`. Expect FAIL.
- [ ] **Step 3: Implement.** Write the step text in tape IDs and physical words ("the right side M01, at the bed's open end", "the wall side"). Text tells the builder how to lay parts down (top inside face up for the headboard joint; the cabinet on its front edges to fit the sides), while the 3D keeps the installed orientation. `bed-drill-sides` also says to check every part against the cut list.
- [ ] **Step 4: Regenerate** (CLI as in Task 3). Then `python3 -m unittest discover tests -v`: all PASS.
- [ ] **Step 5: Commit** `feat: bed cabinet steps with host poses and anchoring holds`.

### Task 6: Drawings for bed steps

**Files:**
- Modify `MurphyBedQueen/assembly_drawings.py` and `output/assembly-guide/` (regenerated).
- Test: `tests/test_assembly_drawings.py`.

**Interfaces:**
- Produces:
  - `step_svg` draws the active-stage parts of the step's stage, plus the steel boxes, labelled "representative shape".
  - `_hardware_panel` gets a generic glyph with the fastener's catalogue name and "×N" for kit codes. Names come from the loaded fasteners, not `FASTENER_NAMES`.
  - `holes_svg` has three paths:
    - **Joint strips:** the length is the joint run, scaled to fit 600 px; the datum label comes from the joint; there is no band text when `joint.band` is None.
    - **Pattern face view:** the side's inside face, with every hole dimensioned from the front edge and up from the bottom end. Holes with `aligned` are marked "position by alignment — check against the plate".
    - **Stud table:**
      - "On each stud line:", then each cabinet hole's offset from the wall (or from the headboard's top or bottom), diameter and depth;
      - for bracket steps, "A5, A6: mark through the bracket onto the wall, 3/16 in pilots into the stud";
      - no x dimension;
      - "Find the stud centres with a stud finder; at least three studs."

- [ ] **Step 1: Write the failing tests.**
  - `test_bed_drill_closeup`: `bed-drill-sides` shows `M05` "lower end" strips with `2"`, `8"`, `14"`, and no "shelf-pin" text.
  - `test_headboard_strip_fits`: the M05-M03 close-up has a width of 600 or less, with `3"` and `21 5/16"`.
  - `test_insert_face_view`: `9 7/16"`, `11 7/16"`, `30 1/4"`, `Ø27/64 × 9/16 deep`, and "position by alignment".
  - `test_stud_closeup`: `bed-wall-brackets` shows "On each stud line", `4 5/8"`, `Ø13/64 × 1/2 deep`, `Ø5/16 through`, "mark through the bracket", and no `11 3/8"` or `43 3/8"` (example stud x).
  - `test_hardware_names`: `bed-inserts` lists "Threaded insert ×16" and "M8 x 16 mm screw ×16".
  - `test_no_pending_parts`: no bed or bookcase step SVG contains `M08`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_assembly_drawings -v`. Expect FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Regenerate**, then `python3 -m unittest discover tests -v`: all PASS.
- [ ] **Step 5: Commit** `feat: bed drawings: general joint strips, insert face view, stud table`.

### Task 7: Viewer and site

**Files:**
- Modify `site/assets/assembly-viewer.js`, `site/build.py`, `site/content/build-steps.html`.
- Test: `tests/test_generate_assembly_guide.py`, `tests/test_site_build.py`.

**Interfaces:**
- Produces:
  - The viewer places hardware with `poseOf(name, index)`, no longer identity, and tweens hardware whose pose changes, together with its host.
  - The JSON hardware `name` comes from the fastener catalogue.
  - `PAGES` description: "Interactive 3D steps for the bed cabinet and the bookcase; the bed mechanism steps follow."

- [ ] **Step 1: Write the failing tests.**
  - `test_generates_all_files`: 22 step SVGs; holes SVGs for the 6 bookcase drilling steps plus `bed-drill-sides`, `bed-inserts`, `bed-top-headboard`, `bed-bottom-headboard`, `bed-right-side`, `bed-left-side`, `bed-lag-bolts` and `bed-wall-brackets`.
  - `test_page_description`.
  - `test_step_fragments`: `#bed-drill-sides` and `#bookcase-drill` both pass.
- [ ] **Step 2: Run** and expect FAIL. **Step 3: Implement.** **Step 4:** `python3 -m unittest discover tests -v` all PASS, and `python3 site/build.py` prints "Validated 7 pages".
- [ ] **Step 5: Browser check** (ml:agent-browser, `python3 -m http.server` in `site/_site`) at 390×844 and 1280×800:
  - all 22 steps, with no console errors;
  - M01 and M02 on the bench in steps 1–2, with the plates and inserts on them;
  - at `bed-right-side`, M01, I-R and its inserts move together into place;
  - `#bed-wall-brackets` shows the HOLD banner;
  - `localStorage` preset to `bookcase-top` opens `bookcase-top`;
  - "Show finished" has no door panels;
  - an offline reload after one visit works.

  Screenshots go in `.tmp/`.
- [ ] **Step 6: Commit** `feat: bed cabinet steps on the step-by-step page`.

### Task 8: Docs

**Files:** Modify `README.md`, `site/content/assembly.html`.

- [ ] **Step 1: README.**
  - The Pages artifact has seven pages.
  - The guide covers the bed cabinet and bookcase.
  - Add the stage list and "to add a stage's steps, move its parts' stage into `ACTIVE_STAGES`".
- [ ] **Step 2: `assembly.html`.** The bed-cabinet stage links `build-steps.html#bed-drill-sides`. Its hole-location text is replaced by a pointer to the guide's dimensioned holes; the 1/2 in face and 1 1/16 in edge depths stay.
- [ ] **Step 3:** `python3 site/build.py` validates. **Step 4: Commit** `docs: point the bed cabinet stage at the step-by-step guide`.
