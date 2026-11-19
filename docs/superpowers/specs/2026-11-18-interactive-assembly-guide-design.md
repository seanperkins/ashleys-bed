# Interactive step-by-step assembly guide — design

Date: 2026-11-18. Status: approved in conversation, pending written-spec review.

## Goal

A self-contained, IKEA-style (but better) assembly guide for the whole build — the Rockler queen horizontal
Murphy bed and the custom left bookcase — used on a phone or tablet in the shop. Every step has:

- an interactive 3D view where that step's parts and hardware animate into place;
- a flat exploded drawing, plus a dimensioned hole close-up on every drilling step;
- the exact parts (tape-label IDs), hardware with counts, hole positions and depths, and safety warnings.

The guide does not send the builder to the Rockler manual. Bed steps carry a small source note
("from Rockler p. 9") for traceability only.

Success: someone can build the bed and bookcase from the guide alone, step by step on a phone, and every
step says which parts, which hardware, how many, and where the holes go.

## Decisions (owner, 2026-11-18)

| Topic | Decision |
|---|---|
| Scope | Bed + bookcase in one guide |
| Device | Phone/tablet first; one step per screen; works with no signal once loaded |
| Drawings | Exploded line drawing per step + dimensioned hole close-up on drilling steps |
| Hardware | Dowels and screws shown and animated, with counts |
| Approach | Own Three.js viewer + generated step file (not model-viewer, not pre-rendered video) |
| Rockler references | Self-contained; small source note per bed step only |
| Bed hole positions | Defined by rule, like the bookcase (Rockler only says "mark locations") |
| Bed face-hole depth | 1/2 in (not Rockler's 5/8): stock is 0.703–0.714 in; edge holes 1 1/16 in |
| Steel mechanism | One simplified, labelled shape per Rockler part, each bolt step animated |

## Architecture

```
output/drawing-geometry.json ─┐                                   ┌─> output/web/assembly.glb
MurphyBedQueen.py constants   ├─> MurphyBedQueen/generate_assembly_guide.py ├─> output/web/assembly-steps.json
MurphyBedQueen/assembly_steps.py ┘                                   └─> output/assembly/step-NN.svg
site/build.py ──> site/_site/build-steps.html + assets/assembly-viewer.js + vendored three.js
```

Units and their single jobs:

1. `MurphyBedQueen/assembly_steps.py` — hand-edited step data, the only place a person edits content.
2. `MurphyBedQueen/assembly_parts.py` — the part catalogue: wood boxes from `drawing-geometry.json`,
   generated hardware (dowels, screws), and simplified steel shapes keyed by Rockler letter.
3. `MurphyBedQueen/generate_assembly_guide.py` — validates steps against the catalogue and writes the
   GLB, the step JSON and the SVG drawings. Standard library only (like `generate_cut_layouts.py`), so
   CI can run it; it follows the glTF layout of `export_web_models.py`'s writer but packs buffers with
   `struct` instead of numpy.
4. `site/assets/assembly-viewer.js` — loads the GLB and step JSON once and plays steps.
5. `site/build.py` — adds the "Step-by-step" page after "Build & finish", publishes the three outputs,
   and runs the generator before building (so the published guide can never lag the step data).

## Data model

`assembly_steps.py` defines `STEPS`, a list of dicts:

```python
{
    "id": "bookcase-bottom",            # stable slug, used in links (#bookcase-bottom)
    "title": "Fix the bottom L04 to the left side L01",
    "adds": ["L04"],                    # part IDs that appear in this step
    "hardware": [                       # each item becomes animated instances
        {"kind": "dowel", "joint": "L04-L01"},   # positions/depths come from the joint rule
        {"kind": "screw", "joint": "L04-L01"},
        {"kind": "glue"},
    ],
    "drill": ["L04-L01"],              # joints whose holes get a dimensioned close-up (optional)
    "move": [0, 0, -1],                # direction new parts travel in (scene axes)
    "camera": {"orbit": "35deg 60deg 3.2m", "target": "L04"},
    "text": ["Glue the dowels into L01's face holes.", "..."],
    "warnings": ["Test the depth stop on scrap first."],
    "source": "Rockler p. 10",         # bed steps only; omitted for bookcase steps
}
```

Joints are defined once in `assembly_parts.py` (`JOINTS`), each with the two parts, the joint line, the
dowel and screw positions, and the hole depths. The rules:

- 16 in side joints (bed and bookcase): 2 dowels at 4 and 12 in from the front edge; 3 #8 × 2 in screws
  at 2, 8 and 14 in, driven through the side into the panel edge.
- Bed headboard joints (85¼ in long, 3 dowels + 4 screws per Rockler): dowels at ¼, ½ and ¾ of the
  length; screws 3 in from each end and at ⅓ and ⅔.
- Hole depths: 3/8 × 1/2 in into a panel face, 3/8 × 1 1/16 in into a panel edge.
- Bookcase holes stay inside their ¾ in joint bands (bottom 2½–3¼ in, fixed shelf 14–14¾ in,
  top 63¼–64 in up the side).
- Exact-dimension Rockler data (mounting-plate inserts, Fig. 1; door brackets, p. 17; wall brackets)
  is transcribed into `assembly_parts.py` with its page reference.

## Parts in the scene

- Wood: all 27 parts as boxes from `drawing-geometry.json` (closed pose), named by tape-label ID
  (M01–M11, L01–L16) with the existing navy/finish colours.
- Hardware: dowels (3/8 × 1½ in cylinders) and #8 × 2 in screws (thin cylinders with a head), placed by
  the joint rules. Glue is a badge, not geometry.
- Steel: one simplified shape per Rockler part — A1, A2, B, C, D, E, F, G1, H, I, J, L, M, N, O, P, Q,
  HH, GG and the bolts/screws/nuts (T, U, V, W, Z, AA, BB, DD, EE, FF, JJ) — labelled with its letter.
  Sizes come from the manual where it gives them; otherwise they are representative and the drawing says
  so. The existing frame-and-slat group in `queen-horizontal-*.glb` is not reused.
- Mattress: the existing simple block, shown in its step.

## Step list (outline; exact list fixed in the plan)

Bed: lay out and check parts → threaded inserts and mounting plates on M01/M02 → upper headboard M05 to
top M03 → lower headboard M06 to bottom M04 → right side M01 → left side M02 → permanent stop M07 → stand
up, locate studs, wall brackets HH → assemble the steel frame (several steps, by Rockler letter) →
slats O with caps P/Q → frame into mounting plates, saddle locking plates J → gas springs G1 → temporary
stops GG and leg M/foot bar N → door brackets L and door panels M08–M11 → mattress → commissioning
checks.

Bookcase: drill joint holes in L01/L02 → bottom L04 and plinth L05 → fixed shelf L07 → top L03 → right
side L02 → back L06 (attachment still to decide: the step says so) → drawer box L11–L15 → slides, box and
face L16 → shelf pins and shelves L08–L10 → place beside the bed and fasten.

## Viewer (phone first)

- 3D view takes the top ~55% of the screen: drag to orbit, pinch to zoom, double-tap to reset.
- Below it: "Step 12 of N" and the title; part chips with tape-label IDs (tap flashes the part); hardware
  with counts and icons; numbered instructions; warnings in the site's warning style; the source note;
  the drawing (tap for full screen).
- Sticky bottom bar: Back · Replay · Next, large targets; swipe left/right also changes step.
- Animation (~1.5 s, replayable): camera eases to the step view; new parts slide in along `move` in an
  accent colour; dowels slide into holes; the panel closes; screws advance and spin; parts settle to
  their finish colour. Earlier parts stay solid, later parts are hidden; a "show finished" toggle shows
  the whole model.
- Deep links per step (`build-steps.html#bookcase-bottom`); last step viewed is kept in `localStorage`
  (wrapped in try/catch, like the existing checklists).
- All assets load with the page, so it keeps working with no signal.
- Three.js is vendored under `site/assets/vendor/` at a pinned version, like `model-viewer` today.
- Reduced motion: when `prefers-reduced-motion` is set, parts appear without the slide.

## Drawings (generated SVG)

- Exploded view per step: isometric projection, white faces with dark outlines, faces sorted back to
  front so hidden edges do not show. Earlier parts light grey; new parts bold, drawn offset along `move`
  with arrows to their seats; hardware on dashed lines into its holes; tape-label IDs on new parts.
- Hardware panel per step (IKEA style): each fastener drawn at actual size with "×N".
- Hole close-up on drilling steps: flat view of the drilled face or edge, every hole dimensioned from the
  front edge and the panel end, depth labelled, ¾ in joint band shaded, plus the "keep shelf-pin rows and
  slide screws out of the bands" note for bookcase sides.
- No new dependencies; works at phone width, prints cleanly.

## Checks and tests

The generator fails the build when:

- a step names an unknown part, joint or hardware kind;
- any catalogued part is never added, or is added twice;
- hardware totals exceed the purchase list (50 dowels, 100 #8 × 2 in screws) or a joint's counts differ
  from its rule;
- a hole leaves its joint band, a face hole is deeper than 1/2 in, or two holes in a joint are closer than
  1 in centre to centre.

Tests (`tests/test_assembly_guide.py`, pytest, written first): the checks above; wood boxes match
`drawing-geometry.json`; every SVG parses and contains its step's part IDs; the GLB has one node per
catalogued part and hardware instance.

Site: `site/build.py` validation covers the new page, its assets and deep-link anchors. Browser check
(agent-browser): step through every step at phone and desktop widths, no console errors, screenshots.

## Related doc updates

The existing README and Build & finish page still describe 5/8 in bed face holes and point to Rockler's
hole locations. They are updated to the 1/2 in depth and to point at the new guide.

## Phasing (one spec, built in order)

1. Engine: catalogue (wood + hardware), generator, GLB/JSON/SVG output, viewer, site page — proven on
   the bookcase steps.
2. Bed cabinet steps (wood + dowels/screws, mounting-plate inserts, wall brackets, door brackets).
3. Steel mechanism: simplified Rockler parts and their bolt-by-bolt steps.

## Out of scope

Exact steel part geometry beyond the manual's dimensions; back attachment and drawer-slide details beyond
"decide first" notes (the steps say so); narration; translations; changes to the cut plans.

## Risks

- Steel part sizes not given in the manual are representative; the drawings label them so.
- The bed hole layout departs from "mark at the bench" and the 5/8 in depth; both are owner decisions
  recorded above.
- Three.js adds a vendored dependency (~600 KB); acceptable next to the existing 3D assets.
