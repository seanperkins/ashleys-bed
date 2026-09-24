#!/usr/bin/env python3
"""Convert the current open/closed STEP models to web-viewable GLB files.

Requires cascadio and trimesh (pip install cascadio trimesh); the site build does not.
Output: output/web/queen-horizontal-{closed,open}.glb, Y-up, metres, centred on X/Z, floor at Y=0.
"""
import tempfile
from pathlib import Path

import cascadio
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
WEB = OUT / 'web'
INCH = 0.0254
# Fusion STEP is Z-up with the room on +Y. glTF is Y-up and viewers look from +Z.
# (x, y, z) -> (-x, z, y) is a proper rotation: bookcase on the viewer's left, room toward the camera.
Z_UP_TO_Y_UP = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=float)


def convert(state):
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / f'{state}.glb'
        if cascadio.step_to_glb(str(OUT / f'queen-horizontal-{state}.step'), str(raw), tol_linear=0.5, tol_angular=0.5):
            raise RuntimeError(f'cascadio failed on {state} STEP')
        scene = trimesh.load(raw)
    scene.apply_transform(Z_UP_TO_Y_UP)
    lo, hi = scene.bounds
    scene.apply_translation([-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2])
    size = scene.extents / INCH
    if abs(size[0] - 116.75) > 0.5 or abs(size[1] - 64) > 0.5:
        raise ValueError(f'{state}: unexpected W x H {size[0]:.2f} x {size[1]:.2f} in')
    WEB.mkdir(exist_ok=True)
    target = WEB / f'queen-horizontal-{state}.glb'
    target.write_bytes(scene.export(file_type='glb'))
    print(f'{target.relative_to(ROOT)}: {size[0]:.2f} W x {size[1]:.2f} H x {size[2]:.2f} D in, '
          f'{len(scene.geometry)} meshes, {target.stat().st_size // 1024} KB')


if __name__ == '__main__':
    for state in ('closed', 'open'):
        convert(state)
