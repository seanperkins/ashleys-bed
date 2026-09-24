#!/usr/bin/env python3
"""Build web-viewable GLB models from the current open/closed STEP exports.

Requires cascadio and trimesh (pip install cascadio trimesh); the site build does not.
Outputs in output/web/, Y-up, metres, centred on X/Z, floor at Y=0:
  queen-horizontal-closed.glb, queen-horizontal-open.glb  static endpoint poses
  queen-horizontal-motion.glb  one 'OpenClose' animation: t=0 closed, t=MOTION_SECONDS open

The motion is rebuilt from the two STEP poses: every part must match the open pose exactly,
rotated by the bed and leg joints in MurphyBedQueen.py. Gas springs are regenerated with
fixed cylinder/rod lengths so the rod slides instead of the cylinder stretching.
"""
import ast
import json
import math
import struct
import tempfile
from pathlib import Path

import cascadio
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
WEB = OUT / 'web'
IN = 0.0254
MOTION_SECONDS = 5.0
FRAMES = 121
TOLERANCE = 0.01 * IN


def generator_constants():
    """Read the numeric module constants from the Fusion script (which imports adsk)."""
    tree = ast.parse((ROOT / 'MurphyBedQueen/MurphyBedQueen.py').read_text())
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        try:
            value = ast.literal_eval(node.value)
        except ValueError:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name):
            found[target.id] = value
        elif isinstance(target, ast.Tuple):
            found.update(zip((t.id for t in target.elts), value))
    return found


C = generator_constants()
PIVOT = np.array([0, C['PY'], C['PZ']]) * IN
LEG_AXIS = PIVOT + np.array([0, C['LEG_Y'], C['LEG_Z']]) * IN
WIDTH = C['W'] + C['SIDE_W']
# Fusion STEP is Z-up with the room on +Y. glTF is Y-up and viewers look from +Z.
# (x, y, z) -> (-x, z, y) is a proper rotation: bookcase on the viewer's left, room toward the camera.
Z_UP_TO_Y_UP = np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], dtype=float)


def rot_x(points, angle, centre):
    p = np.asarray(points, dtype=float) - centre
    c, s = math.cos(angle), math.sin(angle)
    return np.c_[p[:, 0], p[:, 1]*c - p[:, 2]*s, p[:, 1]*s + p[:, 2]*c] + centre


def quat_x(angle):
    return [math.sin(angle/2), 0.0, 0.0, math.cos(angle/2)]


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x*x*(3 - 2*x)


def pose(u):
    """u=0 closed, u=1 open. The leg unfolds early so its feet clear the floor."""
    return {'bed': math.pi/2 * (1 - smoothstep(u)),
            'leg': math.pi * (1 - smoothstep((u - 0.05) / 0.6))}


def load_parts(state):
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / f'{state}.glb'
        if cascadio.step_to_glb(str(OUT / f'queen-horizontal-{state}.step'), str(raw), tol_linear=0.5, tol_angular=0.5):
            raise RuntimeError(f'cascadio failed on {state} STEP')
        scene = trimesh.load(raw)
    parts = []
    for node in scene.graph.nodes_geometry:
        transform, geometry = scene.graph[node]
        mesh = scene.geometry[geometry].copy()
        mesh.apply_transform(transform)
        parts.append({'name': node, 'mesh': mesh})
    return parts


def classify(open_parts, closed_parts):
    """Assign each open-pose part to static / bed / leg by checking it lands on its closed-pose twin."""
    closed_pose = pose(0)
    groups = {'static': [], 'bed': [], 'leg': [], 'pistons': []}
    unused = [p for p in closed_parts if not p['name'].startswith('Pistons')]
    for part in open_parts:
        if part['name'].startswith('Pistons'):
            groups['pistons'].append(part)
            continue
        v = part['mesh'].vertices
        candidates = {
            'static': v,
            'bed': rot_x(v, closed_pose['bed'], PIVOT),
            'leg': rot_x(rot_x(v, closed_pose['leg'], LEG_AXIS), closed_pose['bed'], PIVOT),
        }
        for twin in unused:
            w = twin['mesh'].vertices
            if len(w) != len(v):
                continue
            group = next((g for g, moved in candidates.items() if np.abs(moved - w).max() < TOLERANCE), None)
            if group:
                groups[group].append(part)
                unused.remove(twin)
                break
        else:
            raise ValueError(f'{part["name"]}: no rigid match between open and closed STEP poses')
    if unused or not groups['bed'] or len(groups['leg']) != 1:
        raise ValueError('Open/closed STEP parts do not pair up as static, bed and one leg')
    return groups


def piston_ends(bed_angle):
    ly, lz = C['PISTON_BED_YZ']
    ends = []
    for x in (C['PISTON_X_INSET'], C['W'] - C['PISTON_X_INSET']):
        fixed = np.array([x, *C['PISTON_FIXED_YZ']]) * IN
        moving = rot_x([[x*IN, PIVOT[1] + ly*IN, PIVOT[2] + lz*IN]], bed_angle, PIVOT)[0]
        ends.append((fixed, moving))
    return ends


def check_step_pistons(parts, bed_angle, state):
    """The STEP gas springs must span the same mounts this exporter animates."""
    vertices = np.vstack([p['mesh'].vertices for p in parts if p['name'].startswith('Pistons')])
    for fixed, moving in piston_ends(bed_angle):
        side = vertices[np.abs(vertices[:, 0] - fixed[0]) < 1*IN]
        axis = (moving - fixed) / np.linalg.norm(moving - fixed)
        t = (side - fixed) @ axis
        if abs(t.min()) > 0.05*IN or abs(t.max() - np.linalg.norm(moving - fixed)) > 0.05*IN:
            raise ValueError(f'{state} STEP gas spring mounts moved; update PISTON_* handling')


def spring_mesh(radius, length):
    mesh = trimesh.creation.cylinder(radius=radius*IN, height=length*IN, sections=32)
    mesh.apply_translation([0, 0, length*IN/2])
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-math.pi/2, [1, 0, 0]))  # +Z -> +Y
    return mesh


def check_motion(groups):
    leg = groups['leg'][0]['mesh'].vertices
    moving = np.vstack([p['mesh'].vertices for p in groups['bed']])
    mattress = next(p['mesh'] for p in groups['bed'] if p['name'].startswith('03 Queen'))
    lo, hi = mattress.bounds[0] + 0.05*IN, mattress.bounds[1] - 0.05*IN
    lengths = C['GAS_CYLINDER_LENGTH'], C['GAS_ROD_LENGTH']
    for u in np.linspace(0, 1, 201):
        p = pose(u)
        folded = rot_x(leg, p['leg'], LEG_AXIS)
        if np.all((folded > lo) & (folded < hi), axis=1).any():
            raise ValueError(f'Leg passes through the mattress at u={u:.3f}')
        world = rot_x(np.vstack([moving, folded]), p['bed'], PIVOT)
        if world[:, 2].min() < -0.05*IN:
            raise ValueError(f'Bed or leg goes below the floor at u={u:.3f}')
        for fixed, end in piston_ends(p['bed']):
            span = np.linalg.norm(end - fixed) / IN
            if not sum(lengths) > span >= max(lengths):
                raise ValueError(f'Gas spring cannot span {span:.2f} in at u={u:.3f}')


class GlbWriter:
    def __init__(self):
        self.gltf = {'asset': {'version': '2.0', 'generator': 'ashleys-bed export_web_models.py'},
                     'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [], 'meshes': [],
                     'materials': [], 'accessors': [], 'bufferViews': [], 'buffers': []}
        self.blob = bytearray()
        self.materials = {}

    def accessor(self, array, kind, target=None, bounds=False):
        array = np.ascontiguousarray(array)
        while len(self.blob) % 4:
            self.blob.append(0)
        view = {'buffer': 0, 'byteOffset': len(self.blob), 'byteLength': array.nbytes}
        if target:
            view['target'] = target
        self.blob += array.tobytes()
        self.gltf['bufferViews'].append(view)
        component = {np.dtype('float32'): 5126, np.dtype('uint32'): 5125}[array.dtype]
        acc = {'bufferView': len(self.gltf['bufferViews']) - 1, 'componentType': component,
               'count': len(array), 'type': kind}
        if bounds:
            acc['min'] = array.min(0).tolist() if array.ndim > 1 else [float(array.min())]
            acc['max'] = array.max(0).tolist() if array.ndim > 1 else [float(array.max())]
        self.gltf['accessors'].append(acc)
        return len(self.gltf['accessors']) - 1

    def material(self, mesh):
        m = getattr(mesh.visual, 'material', None)
        colour = tuple(np.round(np.asarray(getattr(m, 'baseColorFactor', None) if m is not None else None
                                           or [200, 200, 200, 255]) / 255, 4).tolist())
        metallic = float(getattr(m, 'metallicFactor', None) or 0)
        roughness = float(getattr(m, 'roughnessFactor', None) or 0.8)
        key = (colour, metallic, roughness)
        if key not in self.materials:
            self.gltf['materials'].append({'pbrMetallicRoughness': {
                'baseColorFactor': list(colour), 'metallicFactor': metallic, 'roughnessFactor': roughness}})
            self.materials[key] = len(self.gltf['materials']) - 1
        return self.materials[key]

    def mesh(self, name, mesh, colour=None):
        if colour is not None:
            mesh = mesh.copy()
            mesh.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
                baseColorFactor=colour, metallicFactor=0.3 if colour[0] > 50 else 0.0, roughnessFactor=0.5))
        primitive = {'attributes': {
            'POSITION': self.accessor(mesh.vertices.astype('float32'), 'VEC3', 34962, bounds=True),
            'NORMAL': self.accessor(mesh.vertex_normals.astype('float32'), 'VEC3', 34962)},
            'indices': self.accessor(mesh.faces.astype('uint32').ravel(), 'SCALAR', 34963),
            'material': self.material(mesh)}
        self.gltf['meshes'].append({'name': name, 'primitives': [primitive]})
        return len(self.gltf['meshes']) - 1

    def node(self, name, parent=None, **fields):
        self.gltf['nodes'].append({'name': name, **fields})
        index = len(self.gltf['nodes']) - 1
        if parent is not None:
            self.gltf['nodes'][parent].setdefault('children', []).append(index)
        return index

    def save(self, path):
        self.gltf['buffers'] = [{'byteLength': len(self.blob)}]
        text = json.dumps(self.gltf, separators=(',', ':')).encode()
        text += b' ' * (-len(text) % 4)
        self.blob += b'\0' * (-len(self.blob) % 4)
        body = (struct.pack('<II', len(text), 0x4E4F534A) + text +
                struct.pack('<II', len(self.blob), 0x004E4942) + bytes(self.blob))
        path.write_bytes(struct.pack('<III', 0x46546C67, 2, 12 + len(body)) + body)


CYLINDER_RGBA, ROD_RGBA = [5, 6, 7, 255], [172, 180, 187, 255]


def build(groups, rest_u, animate, path):
    """Write one GLB whose node transforms hold pose(rest_u); optionally animate u from 0 to 1."""
    rest = pose(rest_u)
    vertices = lambda group: np.vstack([p['mesh'].vertices for p in groups[group]])
    everything = np.vstack([vertices('static'), rot_x(np.vstack([
        vertices('bed'), rot_x(vertices('leg'), rest['leg'], LEG_AXIS)]), rest['bed'], PIVOT)])
    lo, hi = everything.min(0), everything.max(0)
    size = (hi - lo) / IN
    if abs(size[0] - WIDTH) > 0.5 or abs(size[2] - C['H']) > 0.5:
        raise ValueError(f'{path.name}: unexpected W x H {size[0]:.2f} x {size[2]:.2f} in')
    matrix = np.eye(4)
    matrix[:3, :3] = Z_UP_TO_Y_UP
    matrix[:3, 3] = [(lo[0] + hi[0]) / 2, -lo[2], -(lo[1] + hi[1]) / 2]

    out = GlbWriter()
    root = out.node('Ashley bed', matrix=matrix.T.ravel().tolist())
    for part in groups['static']:
        out.node(part['name'], root, mesh=out.mesh(part['name'], part['mesh']))
    bed = out.node('Bed fold joint', root, translation=PIVOT.tolist(), rotation=quat_x(rest['bed']))
    bed_space = out.node('Bed platform', bed, translation=(-PIVOT).tolist())
    for part in groups['bed']:
        out.node(part['name'], bed_space, mesh=out.mesh(part['name'], part['mesh']))
    leg = out.node('Leg fold joint', bed_space, translation=LEG_AXIS.tolist(), rotation=quat_x(rest['leg']))
    leg_space = out.node('Folding leg', leg, translation=(-LEG_AXIS).tolist())
    part = groups['leg'][0]
    out.node(part['name'], leg_space, mesh=out.mesh(part['name'], part['mesh']))

    cylinder = out.mesh('Gas spring cylinder | REPRESENTATIVE', spring_mesh(0.43, C['GAS_CYLINDER_LENGTH']), CYLINDER_RGBA)
    rod = out.mesh('Gas spring rod | REPRESENTATIVE', spring_mesh(0.19, C['GAS_ROD_LENGTH']), ROD_RGBA)

    def spring_nodes(u):
        result = []
        for fixed, moving in piston_ends(pose(u)['bed']):
            d = moving - fixed
            angle = math.atan2(d[2], d[1])  # aims local +Y along the spring
            result.append({'cylinder': (fixed, quat_x(angle)), 'rod': (moving, quat_x(angle + math.pi))})
        return result

    springs = []
    for index, spring in enumerate(spring_nodes(rest_u)):
        c = out.node(f'Gas spring {"LR"[index]} cylinder', root, mesh=cylinder,
                     translation=spring['cylinder'][0].tolist(), rotation=spring['cylinder'][1])
        r = out.node(f'Gas spring {"LR"[index]} rod', root, mesh=rod,
                     translation=spring['rod'][0].tolist(), rotation=spring['rod'][1])
        springs.append((c, r))

    if animate:
        us = np.linspace(0, 1, FRAMES)
        times = out.accessor((us * MOTION_SECONDS).astype('float32'), 'SCALAR', bounds=True)
        channels, samplers = [], []

        def track(node, path_name, values):
            samplers.append({'input': times, 'interpolation': 'LINEAR',
                             'output': out.accessor(np.asarray(values, dtype='float32'),
                                                    'VEC4' if path_name == 'rotation' else 'VEC3')})
            channels.append({'sampler': len(samplers) - 1, 'target': {'node': node, 'path': path_name}})

        track(bed, 'rotation', [quat_x(pose(u)['bed']) for u in us])
        track(leg, 'rotation', [quat_x(pose(u)['leg']) for u in us])
        frames = [spring_nodes(u) for u in us]
        for index, (c, r) in enumerate(springs):
            track(c, 'rotation', [f[index]['cylinder'][1] for f in frames])
            track(r, 'rotation', [f[index]['rod'][1] for f in frames])
            track(r, 'translation', [f[index]['rod'][0] for f in frames])
        out.gltf['animations'] = [{'name': 'OpenClose', 'channels': channels, 'samplers': samplers}]

    out.save(path)
    print(f'{path.relative_to(ROOT)}: {size[0]:.2f} W x {size[2]:.2f} H x {size[1]:.2f} D in, '
          f'{path.stat().st_size // 1024} KB' + (f', {MOTION_SECONDS:g}s open/close animation' if animate else ''))


def main():
    open_parts, closed_parts = load_parts('open'), load_parts('closed')
    check_step_pistons(open_parts, pose(1)['bed'], 'open')
    check_step_pistons(closed_parts, pose(0)['bed'], 'closed')
    groups = classify(open_parts, closed_parts)
    check_motion(groups)
    WEB.mkdir(exist_ok=True)
    build(groups, 0, False, WEB / 'queen-horizontal-closed.glb')
    build(groups, 1, False, WEB / 'queen-horizontal-open.glb')
    # Rest pose open so viewers frame the full swing; the animation starts closed.
    build(groups, 1, True, WEB / 'queen-horizontal-motion.glb')


if __name__ == '__main__':
    main()
