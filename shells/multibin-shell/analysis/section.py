"""Print a planar section of a reference shell as polygons.

Usage: python section.py KEY AXIS VALUE [--raw]
AXIS is x, y or z. Each closed loop is printed as its vertices in the two
remaining axes, with collinear points merged unless --raw is given.
"""

import sys

import numpy as np
import trimesh

from refs import STL_DIR, fname

AX = {"x": 0, "y": 1, "z": 2}


def merge_collinear(pts, tol=1e-4):
    out = []
    n = len(pts)
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        u, v = b - a, c - b
        if abs(u[0] * v[1] - u[1] * v[0]) > tol * max(1e-9, np.linalg.norm(c - a)):
            out.append(b)
    return np.array(out)


def fit_circle(pts):
    """Least-squares circle; returns (cx, cy, r, worst radial error)."""
    A = np.c_[2 * pts, np.ones(len(pts))]
    b = (pts ** 2).sum(1)
    cx, cy, c = np.linalg.lstsq(A, b, rcond=None)[0]
    r = np.sqrt(c + cx * cx + cy * cy)
    err = np.abs(np.linalg.norm(pts - [cx, cy], axis=1) - r).max()
    return cx, cy, r, err


def describe(pts):
    """Circle summary for a round loop, otherwise its merged vertices."""
    if len(pts) > 24:
        cx, cy, r, err = fit_circle(pts)
        if err < 0.02:
            return f"CIRCLE c=({cx:.3f},{cy:.3f}) r={r:.3f} (fit err {err:.3f})"
    if len(pts) > 60:
        return f"{len(pts)} vertices, not a circle; rerun with --raw to list them"
    return " ".join(f"({p[0]:.3f},{p[1]:.3f})" for p in pts)


def main():
    if len([a for a in sys.argv[1:] if a != "--raw"]) != 3:
        sys.exit(__doc__)
    key, axis, value = sys.argv[1], sys.argv[2].lower(), float(sys.argv[3])
    raw = "--raw" in sys.argv
    mesh = trimesh.load_mesh(STL_DIR / fname(key))
    normal = np.zeros(3)
    normal[AX[axis]] = 1
    origin = np.zeros(3)
    origin[AX[axis]] = value
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None:
        print("no intersection")
        return
    keep = [i for i in range(3) if i != AX[axis]]
    names = "xyz"
    for i, loop in enumerate(sec.discrete):
        pts = loop[:, keep]
        if np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        if not raw:
            pts = merge_collinear(pts)
        area = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
        lo, hi = pts.min(0), pts.max(0)
        print(f"loop {i}: {len(pts)} pts, signed area {area:.2f}, "
              f"{names[keep[0]]}[{lo[0]:.3f},{hi[0]:.3f}] {names[keep[1]]}[{lo[1]:.3f},{hi[1]:.3f}]")
        print("   " + (" ".join(f"({p[0]:.3f},{p[1]:.3f})" for p in pts) if raw else describe(pts)))


if __name__ == "__main__":
    main()
