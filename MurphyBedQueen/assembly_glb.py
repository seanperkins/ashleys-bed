"""Standard-library GLB writer for the step-by-step guide's 3D model.

Every node holds its mesh in installed (closed-bed) scene coordinates with an identity transform;
the viewer moves nodes with the per-step pose matrices from the step JSON. Scene axes follow
export_web_models.py: (x, y, z) Fusion inches -> (-x, z, y) * 0.0254 metres, Y up, no centring.
"""

import json
import math
import struct

import assembly_parts as ap
import assembly_steps as st

IN = 0.0254
MATERIALS = {
    "navy": [0x18 / 255, 0x2B / 255, 0x49 / 255, 1.0],
    "natural": [217 / 255, 191 / 255, 151 / 255, 1.0],
    "hardware": [0.72, 0.74, 0.76, 1.0],
    "steel": [0.55, 0.57, 0.6, 1.0],
    "context": [0.80, 0.82, 0.85, 0.35],
}
METAL = {"hardware", "steel"}
DOWEL_LENGTH = 1.5
SCREW_LENGTH = 2.0
SCREW_SHANK = 0.164  # #8 major diameter
SCREW_HEAD = 0.32
SIDES = 16


def to_scene(p):
    return (-p[0] * IN, p[2] * IN, p[1] * IN)


def _normal_to_scene(n):
    return (-n[0], n[2], n[1])


def scene_matrix(m):
    """Fusion row-major 4x4 (inches) -> column-major 16 floats acting on scene metres."""
    a = ((-1, 0, 0), (0, 0, 1), (0, 1, 0))  # its own inverse
    r = [[sum(a[i][k] * m[k][l] * a[l][j] for k in range(3) for l in range(3)) for j in range(3)]
         for i in range(3)]
    t = to_scene((m[0][3], m[1][3], m[2][3]))
    cols = []
    for c in range(3):
        cols += [r[0][c], r[1][c], r[2][c], 0.0]
    return cols + [t[0], t[1], t[2], 1.0]


def box_mesh(lo, hi):
    """24 vertices with face normals, Fusion inches in, scene metres out."""
    positions, normals, indices = [], [], []
    for axis in range(3):
        for sign in (-1, 1):
            u, v = [i for i in range(3) if i != axis]
            corners = []
            for a, b in ((0, 0), (1, 0), (1, 1), (0, 1)):
                p = [0.0, 0.0, 0.0]
                p[axis] = hi[axis] if sign > 0 else lo[axis]
                p[u] = hi[u] if a else lo[u]
                p[v] = hi[v] if b else lo[v]
                corners.append(p)
            n = [0, 0, 0]
            n[axis] = sign
            base = len(positions)
            positions += [to_scene(c) for c in corners]
            normals += [_normal_to_scene(n)] * 4
            indices += _outward([base, base + 1, base + 2, base, base + 2, base + 3], positions,
                                _normal_to_scene(n))
    return positions, normals, indices


def _outward(tri, positions, normal):
    """Order each triangle counter-clockwise when seen from outside."""
    out = []
    for i in range(0, len(tri), 3):
        a, b, c = (positions[j] for j in tri[i:i + 3])
        e1 = [b[k] - a[k] for k in range(3)]
        e2 = [c[k] - a[k] for k in range(3)]
        cross = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
        dot = sum(cross[k] * normal[k] for k in range(3))
        out += tri[i:i + 3] if dot >= 0 else [tri[i], tri[i + 2], tri[i + 1]]
    return out


def _perpendicular(axis):
    helper = (0, 0, 1) if abs(axis[2]) < 0.9 else (1, 0, 0)
    u = (axis[1] * helper[2] - axis[2] * helper[1], axis[2] * helper[0] - axis[0] * helper[2],
         axis[0] * helper[1] - axis[1] * helper[0])
    length = math.sqrt(sum(c * c for c in u))
    u = tuple(c / length for c in u)
    v = (axis[1] * u[2] - axis[2] * u[1], axis[2] * u[0] - axis[0] * u[2], axis[0] * u[1] - axis[1] * u[0])
    return u, v


def cylinder_mesh(start, axis, length, radius, mesh=None):
    """Capped cylinder along a unit Fusion axis; appends to `mesh` (positions, normals, indices)."""
    positions, normals, indices = mesh or ([], [], [])
    u, v = _perpendicular(axis)
    end = tuple(start[k] + axis[k] * length for k in range(3))
    ring = [tuple(math.cos(2 * math.pi * i / SIDES) * u[k] + math.sin(2 * math.pi * i / SIDES) * v[k]
                  for k in range(3)) for i in range(SIDES)]
    base = len(positions)
    for d in ring:
        for centre in (start, end):
            positions.append(to_scene(tuple(centre[k] + radius * d[k] for k in range(3))))
            normals.append(_normal_to_scene(d))
    for i in range(SIDES):
        j = (i + 1) % SIDES
        a, b, c, e = base + 2 * i, base + 2 * i + 1, base + 2 * j, base + 2 * j + 1
        mid = tuple(sum(positions[x][k] for x in (a, b, c, e)) / 4 for k in range(3))
        centre_axis = to_scene(tuple((start[k] + end[k]) / 2 for k in range(3)))
        outward = tuple(mid[k] - centre_axis[k] for k in range(3))
        indices += _outward([a, c, b, b, c, e], positions, outward)
    for centre, sign in ((start, -1), (end, 1)):
        n = _normal_to_scene(tuple(sign * axis[k] for k in range(3)))
        first = len(positions)
        positions.append(to_scene(centre))
        normals.append(n)
        for d in ring:
            positions.append(to_scene(tuple(centre[k] + radius * d[k] for k in range(3))))
            normals.append(n)
        for i in range(SIDES):
            indices += _outward([first, first + 1 + i, first + 1 + (i + 1) % SIDES], positions, n)
    return positions, normals, indices


def hardware_meshes(joint, parts):
    """{node name: mesh} for a joint's dowels and screws, at their installed positions."""
    g = ap.joint_geometry(joint, parts)
    side = parts[joint.side]
    holes = ap.joint_holes(joint, parts)
    into = [0, 0, 0]
    into[g.contact_axis] = g.direction
    into = tuple(into)
    meshes = {}

    def at(hole, offset):
        p = list(hole.world)
        p[g.contact_axis] = g.contact - g.direction * offset
        return tuple(p)

    side_dowels = [h for h in holes if h.part == joint.side and h.kind == "dowel"]
    gap = (ap.DOWEL_FACE_DEPTH + ap.DOWEL_EDGE_DEPTH - DOWEL_LENGTH) / 2
    for n, hole in enumerate(side_dowels, 1):
        start = at(hole, ap.DOWEL_FACE_DEPTH - gap)
        meshes[f"{joint.id}-dowel-{n}"] = cylinder_mesh(start, into, DOWEL_LENGTH, ap.DOWEL_DIAMETER / 2)
    clearances = [h for h in holes if h.part == joint.side and h.kind == "clearance"]
    for n, hole in enumerate(clearances, 1):
        head = at(hole, side.stock)
        mesh = cylinder_mesh(head, into, SCREW_LENGTH, SCREW_SHANK / 2)
        cylinder_mesh(head, into, 0.12, SCREW_HEAD / 2, mesh)
        meshes[f"{joint.id}-screw-{n}"] = mesh
    return meshes


class _Writer:
    def __init__(self):
        self.gltf = {"asset": {"version": "2.0", "generator": "ashleys-bed assembly_glb.py"},
                     "scene": 0, "scenes": [{"nodes": []}], "nodes": [], "meshes": [],
                     "materials": [], "accessors": [], "bufferViews": [], "buffers": []}
        self.blob = bytearray()
        for name, colour in MATERIALS.items():
            material = {"name": name, "pbrMetallicRoughness": {
                "baseColorFactor": colour, "metallicFactor": 0.4 if name in METAL else 0.0,
                "roughnessFactor": 0.5 if name in METAL else 0.8}}
            if colour[3] < 1:
                material["alphaMode"] = "BLEND"
            self.gltf["materials"].append(material)
        self.material_index = {name: i for i, name in enumerate(MATERIALS)}

    def accessor(self, values, fmt, kind, count, target, bounds=None):
        while len(self.blob) % 4:
            self.blob.append(0)
        data = struct.pack(f"<{len(values)}{fmt}", *values)
        self.gltf["bufferViews"].append({"buffer": 0, "byteOffset": len(self.blob),
                                         "byteLength": len(data), "target": target})
        self.blob += data
        acc = {"bufferView": len(self.gltf["bufferViews"]) - 1,
               "componentType": 5126 if fmt == "f" else 5125, "count": count, "type": kind}
        if bounds:
            acc["min"], acc["max"] = bounds
        self.gltf["accessors"].append(acc)
        return len(self.gltf["accessors"]) - 1

    def add(self, name, mesh, material):
        positions, normals, indices = mesh
        bounds = ([min(p[k] for p in positions) for k in range(3)],
                  [max(p[k] for p in positions) for k in range(3)])
        flat = lambda rows: [c for row in rows for c in row]
        primitive = {"attributes": {
            "POSITION": self.accessor(flat(positions), "f", "VEC3", len(positions), 34962, bounds),
            "NORMAL": self.accessor(flat(normals), "f", "VEC3", len(normals), 34962)},
            "indices": self.accessor(indices, "I", "SCALAR", len(indices), 34963),
            "material": self.material_index[material]}
        self.gltf["meshes"].append({"name": name, "primitives": [primitive]})
        self.gltf["nodes"].append({"name": name, "mesh": len(self.gltf["meshes"]) - 1})
        self.gltf["scenes"][0]["nodes"].append(len(self.gltf["nodes"]) - 1)

    def bytes(self):
        self.gltf["buffers"] = [{"byteLength": len(self.blob)}]
        text = json.dumps(self.gltf, separators=(",", ":")).encode()
        text += b" " * (-len(text) % 4)
        blob = bytes(self.blob) + b"\0" * (-len(self.blob) % 4)
        self.gltf["buffers"][0]["byteLength"] = len(self.blob)
        body = (struct.pack("<II", len(text), 0x4E4F534A) + text
                + struct.pack("<II", len(blob), 0x004E4942) + blob)
        return struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body


def boxes_mesh(boxes):
    """One mesh holding every box of a part (a steel shape may be several)."""
    positions, normals, indices = [], [], []
    for lo, hi in boxes:
        p, n, i = box_mesh(lo, hi)
        indices += [k + len(positions) for k in i]
        positions += p
        normals += n
    return positions, normals, indices


def emitted_parts(parts):
    """Parts the GLB holds: everything but the stages whose steps do not exist yet."""
    return {pid: part for pid, part in parts.items() if part.stage not in st.PENDING_STAGES}


def build_glb(parts, resolved):
    writer = _Writer()
    for pid, part in emitted_parts(parts).items():
        material = part.finish if part.stage in st.ACTIVE_STAGES else "context"
        writer.add(pid, boxes_mesh(part.boxes), material)
    for rs in resolved:
        for jid in rs.step["joints"]:
            for name, mesh in hardware_meshes(ap.JOINTS[jid], parts).items():
                writer.add(name, mesh, "hardware")
    return writer.bytes()


def read_glb(data):
    magic, version, length = struct.unpack_from("<III", data)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise ValueError("Not a glTF 2 binary")
    json_len, json_type = struct.unpack_from("<II", data, 12)
    if json_type != 0x4E4F534A:
        raise ValueError("First GLB chunk is not JSON")
    gltf = json.loads(data[20:20 + json_len])
    offset = 20 + json_len
    bin_len, bin_type = struct.unpack_from("<II", data, offset)
    if bin_type != 0x004E4942:
        raise ValueError("Second GLB chunk is not BIN")
    blob = data[offset + 8:offset + 8 + bin_len]
    if len(blob) < gltf["buffers"][0]["byteLength"]:
        raise ValueError("GLB binary chunk is shorter than its buffer")
    for view in gltf["bufferViews"]:
        if view["byteOffset"] + view["byteLength"] > len(blob):
            raise ValueError("GLB buffer view runs past the binary chunk")
    return {"json": gltf, "bin": blob[:gltf["buffers"][0]["byteLength"]]}
