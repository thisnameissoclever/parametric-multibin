"""Print all triangles whose centroid falls inside a given box.

Usage: python region.py <key> x0 x1 y0 y1 z0 z1
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from fingerprint import FILES, STL_DIR, load_stl, tri_normals_areas


def main():
    key = sys.argv[1]
    x0, x1, y0, y1, z0, z1 = map(float, sys.argv[2:8])
    tris = load_stl(STL_DIR / FILES[key])
    normals, areas = tri_normals_areas(tris)
    c = tris.mean(axis=1)
    m = (c[:, 0] >= x0) & (c[:, 0] <= x1) & (c[:, 1] >= y0) & (c[:, 1] <= y1) \
        & (c[:, 2] >= z0) & (c[:, 2] <= z1)
    idx = np.where(m)[0]
    print(f"[{key}] {len(idx)} triangles in box")
    for i in idx:
        n = normals[i]
        v = tris[i]
        print(f"  n=({n[0]:7.4f},{n[1]:7.4f},{n[2]:7.4f}) a={areas[i]:6.2f} "
              + " ".join(f"({p[0]:.3f},{p[1]:.3f},{p[2]:.3f})" for p in v))


if __name__ == "__main__":
    main()
