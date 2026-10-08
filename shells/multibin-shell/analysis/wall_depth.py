"""Recess depth along a vertical line on a wall face, measured by casting
horizontal rays from a point inside the cavity toward the wall.

Usage: python wall_depth.py KEY|STL DIR X Y PLANE Z0 Z1 [STEP]
  KEY|STL  a reference key from refs.py, or the path of a rendered STL
  DIR      ray direction: +x, -x, +y or -y (toward the wall)
  X Y      ray start, inside the cavity, in the generator's frame (first cell
           centred on the origin, base at z = 0)
  PLANE    the wall's flat face coordinate along DIR, for example 22 for the
           inner face of the +x wall of a 1 LU wide shell
  Z0 Z1    height range; STEP defaults to 0.1
Prints each height where the wall surface sits more than 0.01 mm beyond PLANE,
with that depth.
"""

import sys
from pathlib import Path

import numpy as np
import trimesh

from refs import STL_DIR, SIZES, fname

DIRS = {"+x": (0, 1), "-x": (0, -1), "+y": (1, 1), "-y": (1, -1)}


def load(arg):
    if arg[1:] in SIZES and arg[0] in "TOS":
        return trimesh.load_mesh(STL_DIR / fname(arg))
    if Path(arg).is_file():
        return trimesh.load_mesh(arg)
    sys.exit(f"not a reference key or an STL file: {arg}")


def main():
    if len(sys.argv) not in (8, 9) or sys.argv[2] not in DIRS:
        sys.exit(__doc__)
    mesh = load(sys.argv[1])
    axis, sign = DIRS[sys.argv[2]]
    x, y, plane, z0, z1 = map(float, sys.argv[3:8])
    step = float(sys.argv[8]) if len(sys.argv) == 9 else 0.1
    mesh.apply_translation(-mesh.bounds[0] + [-25, -25, 0])
    zs = np.round(np.arange(z0, z1 + step / 2, step), 4)
    origins = np.column_stack([np.full_like(zs, x), np.full_like(zs, y), zs])
    dirs = np.zeros_like(origins)
    dirs[:, axis] = sign
    loc, idx, _ = mesh.ray.intersects_location(origins, dirs, multiple_hits=False)
    depth = np.full(len(zs), np.nan)
    depth[idx] = sign * (loc[:, axis] - plane)
    print(f"{sys.argv[1]} ray {sys.argv[2]} from ({x}, {y}), wall plane {plane}:")
    for z, d in zip(zs, depth):
        if np.isnan(d):
            print(f"   z={z:8.3f}  no hit")
        elif d > 0.01:
            print(f"   z={z:8.3f}  depth {d:.3f}")


if __name__ == "__main__":
    main()
