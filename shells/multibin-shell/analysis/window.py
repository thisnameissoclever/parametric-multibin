"""Section a reference shell and print only the loop pieces inside a 2D window.

Usage: python window.py KEY AXIS VALUE U0 U1 V0 V1
U and V are the two remaining axes in xyz order (for AXIS=x: U=y, V=z).
Consecutive points along each loop that fall inside the window are printed as
runs, collinear points merged, so a feature's outline reads off directly.
"""

import sys

import numpy as np
import trimesh

from refs import STL_DIR, fname

AX = {"x": 0, "y": 1, "z": 2}


def runs(pts, inside):
    """Split a closed loop into maximal runs of consecutive inside points."""
    n = len(pts)
    if inside.all():
        return [pts]
    start = int(np.argmin(inside))           # an outside point to start from
    order = [(start + k) % n for k in range(n)]
    out, cur = [], []
    for i in order:
        if inside[i]:
            cur.append(pts[i])
        elif cur:
            out.append(np.array(cur))
            cur = []
    if cur:
        out.append(np.array(cur))
    return out


def merge(run, tol=1e-4):
    if len(run) < 3:
        return run
    keep = [run[0]]
    for i in range(1, len(run) - 1):
        a, b, c = keep[-1], run[i], run[i + 1]
        u, v = b - a, c - b
        if abs(u[0] * v[1] - u[1] * v[0]) > tol * max(1e-9, np.linalg.norm(c - a)):
            keep.append(b)
    keep.append(run[-1])
    return np.array(keep)


def main():
    key, axis, value = sys.argv[1], sys.argv[2].lower(), float(sys.argv[3])
    u0, u1, v0, v1 = (float(a) for a in sys.argv[4:8])
    mesh = trimesh.load_mesh(STL_DIR / fname(key))
    normal = np.zeros(3); normal[AX[axis]] = 1
    origin = np.zeros(3); origin[AX[axis]] = value
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    keep = [i for i in range(3) if i != AX[axis]]
    for li, loop in enumerate(sec.discrete):
        pts = loop[:, keep]
        if np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        inside = (pts[:, 0] >= u0) & (pts[:, 0] <= u1) & (pts[:, 1] >= v0) & (pts[:, 1] <= v1)
        if not inside.any():
            continue
        for r in runs(pts, inside):
            m = merge(r)
            print(f"loop {li} run ({len(r)} pts): " + " ".join(f"({p[0]:.3f},{p[1]:.3f})" for p in m))


if __name__ == "__main__":
    main()
