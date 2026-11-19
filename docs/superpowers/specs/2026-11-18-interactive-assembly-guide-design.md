# Interactive step-by-step assembly guide — design

Date: 2026-11-18. Status: approved in conversation; revised after panel review (round 1).

## Goal

A self-contained, IKEA-style (but better) assembly guide for the whole build — the Rockler queen horizontal
Murphy bed and the custom left bookcase — used on a phone or tablet in the shop. Every step has:

- an interactive 3D view where that step's parts and hardware animate into place;
- a flat exploded drawing, plus a dimensioned hole close-up on every drilling step;
- the exact parts (tape-label IDs), hardware with counts, every hole's position, diameter and depth, and
  the safety warnings that apply.

The guide does not send the builder to the Rockler manual. Bed steps carry a small source note
("from Rockler p. 9") for traceability only.

Success: someone can build the bed and bookcase from the guide alone, step by step on a phone. Where a
design detail is not decided yet (see Open decisions), the step is a visible HOLD step that names the
decision; the guide is complete when the generator reports zero HOLD steps.

## Decisions (owner, 2026-11-18)

| Topic | Decision |
|---|---|
| Scope | Bed + bookcase in one guide |
| Device | Phone/tablet first; one step per screen; works offline in the shop |
| Drawings | Exploded line drawing per step + dimensioned hole close-up on drilling steps |
| Hardware | Dowels, screws and every kit fastener shown with counts |
| Approach | Own Three.js viewer + generated step file (not model-viewer, not pre-rendered video) |
| Rockler references | Self-contained; small source note per bed step only |
| Bed cabinet hole positions | Defined by rule, like the bookcase (Rockler only says "mark locations") |
| Dowel face-hole depth | 1/2 in (not Rockler's 5/8): stock is 0.703–0.714 in; edge holes 1 1/16 in |
| Steel mechanism | One simplified, labelled shape per Rockler part, each bolt step animated |

## Open decisions (shown as HOLD steps until made)

1. Bookcase back L06 attachment (inset with cleats/screws, rabbet or groove).
2. Drawer-slide model, which sets the slide screw pattern and the drawer box clearance.
3. Shelf-pin hole layout (rows, spacing, setback), outside the joint bands.
4. Bookcase wall restraint (hardware and position).
5. Kit discrepancies to confirm with Rockler: BB bolt length (45 vs 50 mm); W screws (the assembly uses
   88 — 32 for the 16 door brackets plus 56 through the frame tabs — but the inventory lists 56); OO nuts
   (4 required, missing from the inventory table).
6. Rockler's 5/8 in blind holes leave about 0.08 in in 0.703 in stock: the door-bracket pilots in the
   door panels, the wall-bracket screw pilots in the cabinet top, and the 13/64 × 5/8 in hole for each
   wall bracket's steel dowel. The guide proposes 1/2 in for all three (the screws still bite past the
   pilot; the bracket dowel is checked against that depth on the actual bracket). Owner to confirm.
7. Plinth L05 attachment to the bottom L04 and sides.
8. Drawer box joints (L11–L14) and drawer-bottom L15 support.
9. Pulls: the two bed pulls and the drawer pull — model, fixing screws, which door panels get the bed
   pulls, each pull's height and edge offset, hole centres, and clearance to the steel frame. The pull
   steps stay HOLD until all of these are recorded.
10. Screw-tip clearance: a 1¼ in screw through the ⅝ in stop M07 ends 0.078 in below the cabinet top's
    upper surface, and the JJ #12 × ¾ in wall-bracket screws may come as close to the top's underside,
    depending on bracket thickness. Proposed: #8 × 1⅛ in screws for M07 (0.203 in left); JJ checked
    against the measured bracket thickness. Owner to confirm.

Each HOLD step shows what is known (parts, position, counts that are fixed) and names the decision.
Resolving a decision means editing the step/joint data; the HOLD disappears. HOLDs propagate: a step that
makes or uses a held joint, hole or part (for example installing L07 after its holes are held) is held
for the same decision, so no step is presented as ready while something it depends on is undecided.
Steps can also declare `requires` on earlier steps for safety order, and HOLDs propagate along those
links too: every step from seating the frame in the mounting plates onward requires the headboard lag
bolts and all three wall brackets, so the mechanism is never shown as ready while anchoring is held.

## Architecture

```
output/drawing-geometry.json ─┐
output/rockler-kit-inventory.csv ─┤
MurphyBedQueen.py constants ──────┼─> MurphyBedQueen/generate_assembly_guide.py ─> output/assembly-guide/
MurphyBedQueen/assembly_parts.py ─┤
MurphyBedQueen/assembly_steps.py ─┘   (all outputs in one directory: output/assembly-guide/
                                        assembly.glb, assembly-steps.json, step-NN.svg)
site/build.py (imports the generator) ─> build-steps.html, assembly-viewer.js, sw.js, vendored three.js
```

Units and their single jobs:

1. `MurphyBedQueen/assembly_steps.py` — hand-edited step data; the only place a person edits content.
2. `MurphyBedQueen/assembly_parts.py` — the part catalogue (wood, hardware, steel), joints, hole specs and
   the fastener catalogue.
3. `MurphyBedQueen/generate_assembly_guide.py` — validates steps against the catalogue and writes the
   GLB, step JSON and SVGs. Standard library only (like `generate_cut_layouts.py`) so CI can run it; it
   follows the glTF layout of `export_web_models.py`'s writer but packs buffers with `struct`.
4. `site/assets/assembly-viewer.js` — loads the GLB and step JSON once and plays steps.
5. `site/sw.js` — a service worker published at the site root (so its scope covers
   `build-steps.html`) that precaches the guide page and all its assets.
6. `site/build.py` — adds the "Step-by-step" page after "Build & finish" and publishes the outputs.

### Generation and build contract

- `site/build.py` imports `generate_assembly_guide.generate(staging_dir)` and calls it directly (no
  subprocess). Any exception stops the build with a non-zero exit.
- The generator CLI writes its outputs to one directory, `output/assembly-guide/`; `site/build.py` calls
  `generate()` with a directory inside its own site staging dir and never writes to `output/`. The generator writes a fresh sibling
  staging directory, validates the complete set (every step's SVG exists and parses, the GLB parses and
  has every expected node, the JSON matches the step list), then swaps it in: rename the current
  directory to a backup (skipped on a clean checkout where none exists yet), rename staging into place,
  delete the backup. If the second rename fails, the
  backup is renamed back. Stale files from removed steps disappear with the old directory, and a failure
  at any point leaves the previous outputs in place.
- `site/build.py` builds into a temporary directory and swaps it into `site/_site` only after validation
  passes, so a failed build never leaves a half-built site.

## Data model

`assembly_steps.py` defines `STEPS`, a list of dicts:

```python
{
    "id": "bookcase-bottom",            # stable slug, used in links (#bookcase-bottom)
    "title": "Fix the bottom L04 to the left side L01",
    "adds": ["L04"],                    # parts that appear in this step
    "joints": ["L04-L01"],              # joints made in this step; their holes and fasteners come from JOINTS
    "fasteners": {},                    # extra fasteners used here beyond the joint rules (catalogue codes)
    "drill": ["L04-L01"],              # joints whose holes get a dimensioned close-up
    "pose": {"bed": "closed", "subassembly": {"frame": "floor"}},  # see Poses
    "move": [0, 0, -1],                # direction new parts travel in (scene axes)
    "camera": {"orbit": "35deg 60deg 3.2m", "target": "L04"},
    "text": ["Glue the dowels into L01's face holes.", "..."],
    "warnings": ["Test the depth stop on scrap first."],
    "hold": None,                       # or "Back attachment not decided" (Open decisions)
    "requires": [],                     # earlier step ids that must be done first (safety order)
    "source": None,                     # bed steps only, e.g. "Rockler p. 10"
}
```

### Joints, holes and coordinates

`assembly_parts.py` defines `JOINTS`. Each joint names the two parts and is located in world space; the
generator projects every hole into each part's local frame:

- Hole frame: every hole is located on a named face or edge of its part. On a face, `u` and `v` are the
  face's two in-plane axes — `u` across the face's width from a named reference edge, `v` along its
  length from a named reference end — and `w` points into the part. On an edge, `u` runs along the edge
  from a named reference end and `w` points into the edge; the hole is centred in the thickness. This
  works the same for sides, horizontal panels, headboards, door panels (width and height on the inside
  face) and the drawer face. Each part's reference edges are named in the catalogue from its installed
  position (for example "front edge", "bottom end", "hinge-side edge"), and mirrored parts get their own
  frames from their world placement, never by copying the other side's numbers.
- Every hole records: part, face or edge, `u`/`v` position, diameter, depth, through or blind, and
  countersink. The generator checks that each hole lands on the named face/edge and inside the stock.

Hole and fastener rules:

- Dowel joints: 3/8 in holes, 1/2 in deep into a panel face, 1 1/16 in deep into a panel edge.
- #8 × 2 in screws through a side into a panel edge: 3/16 in clearance hole through the side with a
  countersink on the outside face, then a 1/8 in pilot 1 1/4 in deep into the panel edge (standard #8
  practice; the step says to test on scrap).
- 16 in joints (bed and bookcase): dowels at 4 and 12 in from the joint's datum end; screws at 2, 8 and
  14 in. The bed has eight of these (each side M01/M02 meets the top, bottom, upper and lower headboard:
  16 dowels, 24 screws, matching Rockler's counts); the bookcase has six (12 dowels, 18 screws). With the
  two headboard joints (6 dowels, 8 screws) the totals are 34 dowels and 50 #8 × 2 in screws. The datum end is the front edge for joints between horizontal panels and the sides, and the
  lower end of the joint line for the vertical joints where the headboards meet the sides.
- Bed headboard joints (85¼ in, 3 dowels + 4 screws): dowels at ¼, ½ and ¾ of the length; screws 3 in
  from each end and at ⅓ and ⅔.
- Rockler-dimensioned holes (mounting-plate inserts, Fig. 1: 27/64 × 9/16 in; the bottom hole of each
  door bracket; wall brackets and headboard lag bolts) are transcribed with their page reference and
  validated against their own specification.
- Transfer holes: holes the manual locates from the fitted hardware, not by dimension (the second hole of
  each door bracket, the 56 W and 28 V screws through the frame tabs), are marked `transfer`. Their
  drawings show the region and say "mark from the fitted bracket/frame"; they carry no coordinates
  (so representative steel shapes never set a drilling position) but still count toward fastener totals.
- Stud-located holes: the headboard lag bolts and wall brackets follow the actual studs. They are marked
  `stud`: the drawing shows how to find the studs and the offsets Rockler gives from each stud line, and
  the 3D view places them at example stud positions labelled "at your studs". They carry no fixed
  cabinet coordinates.
- Fitted-part holes: M07's four #8 × 1¼ in screws are marked `transfer` on the cabinet top (marked
  through the fitted stop, no cabinet coordinates). Their screw pattern is dimensioned on M07 itself, and
  the pilots are 1/8 in × 1 in deep measured from the stop's outer face, so they enter the cabinet top
  by 3/8 in (checked by the wall rule). The M07 step is HOLD under decision 10 until the screw length is
  chosen; that decision updates the step, the fastener catalogue and the BOM row together.
- Any blind hole must leave at least 1/8 in of material along its drilling direction, and an edge hole
  at least 1/8 in on each side across the panel's thickness (a 3/8 in dowel hole centred in 0.703 in stock
  leaves 0.164 in). Face holes are checked against the part's thickness; edge holes against the panel's
  dimension in the drilling direction. The same rule applies to screw tips: screw length minus the
  thickness of whatever it passes through first (bracket, stop, side) must leave 1/8 in before the far
  face. Thicknesses used: the measured minimum for 3/4 in stock (0.703 in), and nominal minus 1/32 in for the 1/2 and
  1/4 in stock until it is bought and measured. A hole that does not is a build error unless its step is
  a HOLD naming that decision.
- Bookcase joint holes stay inside their ¾ in bands (bottom 2½–3¼ in, fixed shelf 14–14¾ in, top
  63¼–64 in up the side).

### Fasteners

The fastener catalogue has two sources:

- Kit fasteners, read from `output/rockler-kit-inventory.csv` (every code: T, U, V, W, Z, AA, BB, DD, EE,
  FF, II, JJ, KK, OO …). Required quantity = the kit quantity, except the discrepancies below.
- Purchased fasteners, one entry per BOM fastener row (#8 × 2 in screws, 3/8 × 1½ in dowels, #8 × 1¼ in
  stop screws, #8 × 1 in washer-head drawer-face screws, #6 drawer and panel screws). The BOM quantity is
  a purchase quantity that includes spares, so `assembly_parts.py` records a separate *used* quantity per
  entry (#8 × 2 in: 50; dowels: 34; #8 × 1¼ in: 4; #8 × 1 in washer-head: 4). Entries used only by HOLD
  steps (the #6 screws) have no used quantity until their decision is made and are skipped by the check.

- Bundled fasteners: screws that come with bought hardware (drawer-slide screws, pull screws, the
  bookcase restraint kit's fasteners) get catalogue entries with a *supplied-with* source and count,
  recorded when that hardware is chosen; the steps that use them are HOLD until then.

Each purchased or bundled entry records three numbers: used, bought (BOM) and supplied-with-hardware.
The generator sums each fastener over all steps and fails when a total differs from its used quantity,
or when the used quantity exceeds bought plus supplied-with-hardware. For the three kit discrepancies, `assembly_parts.py` holds a
`DISCREPANCIES` table with the quantity the assembly uses (BB 34; W 88; OO 4), the supplied quantity
and the open question. Validation compares step totals with the *used* quantity, so generation passes;
the shortfall or doubt is shown as a HOLD note on every step that uses that fastener and counted in the
HOLD total. Each discrepancy lists its own clearing conditions, and its HOLD clears only when all are
recorded: for quantities, that the used quantity is on hand (supplied plus any extra bought covers it) or
the assembly count is corrected; for BB, also that the correct bolt length is confirmed and on hand; a confirmation that
leaves a shortfall (e.g. Rockler confirms 56 W screws while 88 are used) keeps the HOLD and states the
number to buy.

### Poses

Parts and named subassemblies (`frame`, `bed` = everything that pivots, `leg`) can be placed per step:

- `bed`: `closed`, `open`, or an angle; the pivot and leg axis come from `MurphyBedQueen.py` (as in
  `export_web_models.py`).
- `subassembly` placements such as `frame: floor` (assembled flat on the floor) and `frame: seated`
  (in the mounting plates). A single part can also be staged, e.g. `L02: bench` (lying beside the work
  until a later step installs it). Steps that move a subassembly or staged part animate that move.

## Parts in the scene

- Wood: all 27 parts as boxes from `drawing-geometry.json`, named by tape-label ID (M01–M11, L01–L16),
  with the existing finish colours.
- Hardware: dowels and screws placed from the hole data; kit fasteners drawn as small generic shapes
  (bolt, nut, washer, insert) at their positions. Transfer fasteners have no exact positions: the 3D view
  highlights the region they go into and shows them arriving there as a group with their count, never as
  a precise hole.
- Steel: one simplified shape per Rockler part (A1, A2, B, C, D, E, F, G1, H, I, J, L, M, N, O, P, Q, GG,
  HH), labelled with its letter. Sizes come from the manual where given; otherwise they are representative
  and the drawing says so.
- Mattress: a simple block in its step.

## Step list (outline; exact list fixed in the plan)

Bed cabinet: lay out and check parts → threaded inserts T and mounting plates I on M01/M02 (Fig. 1
positions) → upper headboard M05 to top M03 → lower headboard M06 to bottom M04 → right side M01 → left
side M02 → stand up and locate studs → headboard pilots and six KK lag bolts → three wall brackets HH
(six KK, three II, six JJ).

Mechanism (manual order): frame on the floor (A1, A2, B, C, D, E, F with BB/FF — BB length HOLD) →
slats O with caps P/Q, leaving the first and last rows out → frame-side piston G1 attachment → seat the
pivots in the mounting-plate saddles → saddle locking plates J (Z, EE, threadlocker) → controlled frame
positioning → cabinet-side piston attachment → temporary stops GG → legs M and foot bar N (AA, DD, OO —
OO HOLD) → bed pulls on the door panels (HOLD: pull choice) → door brackets L and door panels M08–M11, hang, adjust, clearance check, final attachment →
permanent stop M07, fitted so the actual frame closes plumb (position from the fit, not the CAD; the
3D view shows M07 at an illustrative spot labelled "position set from your frame" and its drawing
dimensions only its size, centring and screw pattern, not its distance from the cabinet edges) with
four #8 × 1¼ in screws → mattress supports H and the remaining slat rows → mattress → commissioning
checks. Pressure and helper warnings from the manual appear on every step after the pistons go on.

Bookcase: lay out L01 and L02 on the bench, inside faces up, and drill the top and bottom joint holes
(both sides are added here; L02 stays on the bench, `pose: bench`) → drill the fixed-shelf L07 joint holes
in both sides (HOLD until the drawer slide is chosen, since the slide sets the space under the shelf) → bottom L04 onto L01 → plinth L05 (HOLD: attachment) → fixed shelf
L07 → top L03 → right side L02 moves from the bench onto the assembly → back L06 (HOLD: attachment) → drawer box L11–L15
(HOLD: joints and bottom support) → slides, box and face L16 (HOLD: slide
model) → drawer pull (HOLD: pull choice) → shelf-pin holes and shelves L08–L10 (HOLD: layout) → place beside the bed and fasten (HOLD:
restraint).

## Viewer (phone first)

- 3D view takes the top ~55% of the screen: drag to orbit, pinch to zoom, double-tap to reset.
- Below it: "Step 12 of N" and the title; a HOLD banner when the step has one; part chips with tape-label
  IDs (tap flashes the part); hardware with counts and icons; numbered instructions; warnings in the
  site's warning style; the source note; the drawing (tap for full screen).
- Sticky bottom bar: Back · Replay · Next, large targets; swipe left/right also changes step.
- Animation (~1.5 s, replayable): camera eases to the step view; subassemblies move to the step's pose;
  new parts slide in along `move` in an accent colour; dowels slide into holes; the panel closes; screws
  advance and spin; parts settle to their finish colour. Earlier parts stay solid, later parts are hidden;
  a "show finished" toggle shows the whole model.
- `prefers-reduced-motion`: parts appear without sliding.
- Deep links per step (`build-steps.html#bookcase-bottom`); last step viewed is kept in `localStorage`
  (wrapped in try/catch, like the existing checklists).
- Offline: `sw.js` precaches the guide page, viewer, three.js, GLB, step JSON and all SVGs on first
  visit (cache name includes a content hash, old caches deleted on activate), so the guide opens with no
  signal after one online visit.
- Three.js is vendored under `site/assets/vendor/` at a pinned version, like `model-viewer` today.

## Drawings (generated SVG)

- Exploded view per step: isometric projection, white faces with dark outlines. Parts are
  non-overlapping axis-aligned boxes (validated), so they are drawn in back-to-front depth order;
  fasteners are drawn last. Earlier parts light grey; new parts bold, offset along `move` with arrows to
  their seats; tape-label IDs on new parts.
- Hardware panel per step (IKEA style): each fastener drawn at actual size with "×N".
- Hole close-up on drilling steps: flat view of each drilled face or edge, every hole dimensioned in the
  part frame (from the front edge and the panel end), diameter and depth labelled, countersinks marked,
  joint bands shaded, plus the "keep shelf-pin rows and slide screws out of the bands" note on bookcase
  sides.
- No new dependencies; works at phone width, prints cleanly. Drawings are reviewed by screenshot in the
  browser check.

## Checks and tests

The generator fails when:

- a step names an unknown part, joint, fastener code or pose;
- any catalogued part is never added, or is added twice;
- a fastener total over all steps differs from its required quantity (kit inventory or BOM);
- a hole leaves its part, face/edge or joint band, leaves less than 1/8 in of wall, or sits closer than
  1 in centre to centre to another hole in the same part (unless a HOLD step names it, or the holes belong
  to a transcribed Rockler pattern marked `verified` with its page, such as the Fig. 6 wall-bracket A1
  dowel and A2 bolt holes 5/8 in apart);
- any output is missing or fails to parse after generation (checked in the staging directory).

Tests (`tests/test_assembly_guide.py`, standard-library `unittest`, run with
`python3 -m unittest discover tests`, written first): the checks above; wood boxes match
`drawing-geometry.json`; left and right side holes are mirror images in world space and correct in each
part frame; every SVG parses and contains its step's part IDs; the GLB has one node per catalogued part
and hardware instance; a forced generator failure leaves the previous outputs untouched.

Site: `site/build.py` validation covers the new page, its assets and deep-link anchors. Browser check
(agent-browser): step through every step at phone and desktop widths, no console errors, screenshots,
and the page reloads with the network disabled after one visit.

## Related doc updates

The README and Build & finish page still describe 5/8 in bed face holes and point to Rockler's hole
locations. They are updated to the 1/2 in depth and to point at the new guide.

## Phasing (one spec, built in order)

1. Engine: catalogue, joints and hole frames, generator with staging, GLB/JSON/SVG output, viewer,
   service worker, site page — proven on the bookcase steps (HOLD steps included).
2. Bed cabinet steps, inserts, mounting plates, wall anchoring.
3. Steel mechanism, doors, stop, mattress and commissioning, with poses.

## Out of scope

Exact steel part geometry beyond the manual's dimensions; narration; translations; changes to the cut
plans. The open decisions above are made by the owner, not by this project.

## Risks

- Steel part sizes not given in the manual are representative; the drawings label them so.
- The bed hole layout and the 1/2 in face depth depart from the manual; both are owner decisions above.
- Three.js adds a vendored dependency (~600 KB); acceptable next to the existing 3D assets.
