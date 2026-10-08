"""Fit the offset of planes with a given unit normal across models.

Usage: python planefit.py nx ny nz key [key...]
Prints each cluster of coplanar triangles: offset c = n . p, area, extent.
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from fingerprint import FILES, STL_DIR, load_stl, tri_normals_areas


def main():
    n = np.array([float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])])
    n /= np.linalg.norm(n)
    for key in sys.argv[4:]:
        tris = load_stl(STL_DIR / FILES[key])
        normals, areas = tri_normals_areas(tris)
        mask = normals @ n > 0.9999
        sel = tris[mask]
        if not len(sel):
            print(f"[{key}] no faces with that normal")
            continue
        offs = np.round((sel.mean(axis=1) @ n), 3)
        print(f"[{key}] {len(sel)} tris, offsets:")
        for c in sorted(set(offs)):
            m = offs == c
            pts = sel[m].reshape(-1, 3)
            print(f"   c={c:9.3f} area={areas[mask][m].sum():7.2f} "
                  f"x=[{pts[:,0].min():.2f},{pts[:,0].max():.2f}] "
                  f"y=[{pts[:,1].min():.2f},{pts[:,1].max():.2f}] "
                  f"z=[{pts[:,2].min():.2f},{pts[:,2].max():.2f}]")


if __name__ == "__main__":
    main()
