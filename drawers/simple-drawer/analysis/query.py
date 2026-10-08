"""Locate triangles lying in a given axis-aligned plane; print their bounding rectangles.

Usage: python query.py <key> <axis x|y|z> <coord> [tol]
Groups coplanar triangles into connected clusters and prints each cluster's extent.
"""

import sys
from pathlib import Path
import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).parent))
from fingerprint import FILES, STL_DIR, load_stl, tri_normals_areas

AXIS = {"x": 0, "y": 1, "z": 2}


def main():
    key, axis, coord = sys.argv[1], sys.argv[2], float(sys.argv[3])
    tol = float(sys.argv[4]) if len(sys.argv) > 4 else 0.05
    ax = AXIS[axis]
    tris = load_stl(STL_DIR / FILES[key])
    normals, areas = tri_normals_areas(tris)
    on_plane = (np.abs(np.abs(normals[:, ax]) - 1.0) < 1e-4) & (
        np.abs(tris[:, :, ax] - coord).max(axis=1) < tol
    )
    idx = np.where(on_plane)[0]
    print(f"[{key}] {len(idx)} triangles on plane {axis}={coord} (+/-{tol})")
    if not len(idx):
        return
    # cluster by vertex sharing
    sel = tris[idx]
    keyof = lambda v: (round(v[0], 3), round(v[1], 3), round(v[2], 3))
    parent = list(range(len(idx)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    vmap = {}
    for i, t in enumerate(sel):
        for v in t:
            k = keyof(v)
            if k in vmap:
                a, b = find(i), find(vmap[k])
                if a != b:
                    parent[a] = b
            else:
                vmap[k] = i
    clusters = {}
    for i in range(len(idx)):
        clusters.setdefault(find(i), []).append(i)
    other = [a for a in "xyz" if a != axis]
    o0, o1 = AXIS[other[0]], AXIS[other[1]]
    for root, members in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        pts = sel[members].reshape(-1, 3)
        a = areas[idx[members]].sum()
        n = normals[idx[members][0]][ax]
        print(f"  cluster: {len(members)} tris, area={a:.2f}, facing {'+' if n>0 else '-'}{axis}, "
              f"{other[0]}=[{pts[:,o0].min():.3f},{pts[:,o0].max():.3f}] {other[1]}=[{pts[:,o1].min():.3f},{pts[:,o1].max():.3f}]")


if __name__ == "__main__":
    main()
