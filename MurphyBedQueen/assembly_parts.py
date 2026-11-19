"""Part catalogue, joints, holes and fasteners for the step-by-step assembly guide.

Standard library only. Units are inches in Fusion axes: x across (bed 0-86.75, bookcase
86.75-116.75), y from the wall (0) to the room side (16), z up.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from generate_cut_layouts import PART_SPECS

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = ROOT / "output" / "drawing-geometry.json"

MEASURED_MIN_34 = 0.703  # measured minimum of the 3/4 in plywood
NATURAL_PARTS = {"L11", "L12", "L13", "L14", "L15"}
FINISH_COLOURS = {"navy": "#182B49", "natural": "rgb(217,191,151)"}


@dataclass(frozen=True)
class Part:
    id: str
    label: str
    assembly: str  # 'bed' | 'bookcase'
    min: tuple
    max: tuple
    stock: float
    finish: str  # 'navy' | 'natural'

    @property
    def centre(self):
        return tuple((a + b) / 2 for a, b in zip(self.min, self.max))

    @property
    def size(self):
        return tuple(b - a for a, b in zip(self.min, self.max))


def model_key(name):
    """Fusion body name -> PART_SPECS key."""
    key = name.split(" |", 1)[0].split(" —", 1)[0].strip()
    if key.startswith("SC "):
        key = "Left cabinet: " + key[3:]
    return key


_SPECS = {key: (pid, label, thickness) for pid, key, label, _w, _l, thickness in PART_SPECS}


def part_id_for(name):
    key = model_key(name)
    if key not in _SPECS:
        raise ValueError(f"Unknown model part: {name}")
    return _SPECS[key][0]


def load_parts(geometry=GEOMETRY):
    data = json.loads(Path(geometry).read_text(encoding="utf-8"))
    if data.get("units") != "inches":
        raise ValueError("drawing-geometry.json must be in inches")
    parts = {}
    for body in data["wood"]:
        key = model_key(body["name"])
        if key not in _SPECS:
            raise ValueError(f"Unknown model part: {body['name']}")
        pid, label, thickness = _SPECS[key]
        if pid in parts:
            raise ValueError(f"Duplicate model part: {body['name']}")
        parts[pid] = Part(
            id=pid, label=label,
            assembly="bookcase" if pid.startswith("L") else "bed",
            min=tuple(float(v) for v in body["min"]),
            max=tuple(float(v) for v in body["max"]),
            stock=thickness,
            finish="natural" if pid in NATURAL_PARTS else "navy",
        )
    if set(parts) != {spec[0] for spec in PART_SPECS}:
        raise ValueError("drawing-geometry.json does not hold all 27 parts")
    return dict(sorted(parts.items()))


def drilling_thickness(part):
    """Thickness used for wall checks: measured minimum for 3/4 stock, nominal - 1/32 otherwise."""
    if part.stock == 0.75:
        return MEASURED_MIN_34
    return part.stock - 1 / 32
