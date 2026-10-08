"""Cross-section extractor: prints exact polygon loops (lines + fitted arcs) and saves a plot.

Usage:
  python sections.py <key-or-path> <axis x|y|z> <coord> [--png out.png] [--raw]

Prints each closed loop in the section plane as 2D coordinates (the two in-plane axes),
with collinear points merged and circular-arc runs fitted and summarized.
"""

import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import mbpaths  # noqa: E402  (path resolution shared across the repo)
STL_DIR = mbpaths.refs("drawer")
FILES = {
    "n111": "1x1x1 LU  - MultiBin Simple Drawer (no label).stl",
    "s111": "1x1x1 LU - Labelled (small label) - MultiBin Simple Drawer.stl",
    "m212": "2x1x2 LU - Labelled - Magnetic - Simple Multibin Drawer.stl",
    "c212": "2x1x2 LU - Labelled - Column Divided - MultiBin Simple Drawer.stl",
    "g212": "2x1x2 LU - Labelled - Grid Divided - MultiBin Simple Drawer.stl",
    "L323": "3x2x3 LU - Labelled - MultiBin Simple Drawer.stl",
    "L332": "3x3x2 LU - Labelled - MultiBin Simple Drawer.stl",
    "c313": "3x1x3 LU - Labelled - Column Divided - MultiBin Simple Drawer.stl",
    "c3135": "3x1x3.5 LU - Labelled - Column Divided - MultiBin Simple Drawer.stl",
}
AXIS = {"x": 0, "y": 1, "z": 2}


def get_mesh(key):
    p = Path(key) if key.lower().endswith(".stl") else STL_DIR / FILES[key]
    return trimesh.load_mesh(p), p


def section_loops(mesh, axis, coord):
    normal = np.zeros(3)
    normal[AXIS[axis]] = 1.0
    origin = normal * coord
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None:
        return []
    # Use discrete 3D loops and drop the section axis ourselves so axis meaning stays obvious.
    loops3d = sec.discrete
    keep = [i for i in range(3) if i != AXIS[axis]]
    return [np.asarray(loop)[:, keep] for loop in loops3d]


def merge_collinear(pts, tol=1e-4):
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    out = []
    n = len(pts)
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        v1, v2 = b - a, c - b
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        if abs(cross) > tol * (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-12):
            out.append(b)
    return np.array(out)


def fit_circle(pts):
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([2 * x, 2 * y, np.ones(len(pts))])
    b = x**2 + y**2
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = sol[0], sol[1]
    r = np.sqrt(sol[2] + cx**2 + cy**2)
    resid = np.abs(np.hypot(x - cx, y - cy) - r).max()
    return (cx, cy), r, resid


def describe_loop(pts, seg_thresh=1.2, arc_min=4):
    """Split loop vertices into straight segments and arc runs; print both."""
    n = len(pts)
    seglen = np.array([np.linalg.norm(pts[(i + 1) % n] - pts[i]) for i in range(n)])
    is_short = seglen < seg_thresh
    print(f"    loop with {n} corner vertices (after collinear merge)")
    i = 0
    used = np.zeros(n, bool)
    # find arc runs: consecutive short segments
    runs = []
    i = 0
    while i < n:
        if is_short[i] and not used[i]:
            j = i
            run = [i]
            while is_short[(j + 1) % n] and len(run) < n:
                j = (j + 1) % n
                if j in run:
                    break
                run.append(j)
            if len(run) >= arc_min:
                runs.append(run)
                for k in run:
                    used[k] = True
            i = max(run) + 1 if run and max(run) >= i else i + 1
        else:
            i += 1
    arc_pts = set()
    for run in runs:
        idxs = [run[0]] + [(k + 1) % n for k in run]
        p = pts[idxs]
        (cx, cy), r, resid = fit_circle(p)
        a0 = np.degrees(np.arctan2(p[0][1] - cy, p[0][0] - cx))
        a1 = np.degrees(np.arctan2(p[-1][1] - cy, p[-1][0] - cx))
        print(f"      ARC: {len(idxs)} pts, center=({cx:8.3f},{cy:8.3f}) r={r:7.3f} resid={resid:.4f} "
              f"from ({p[0][0]:8.3f},{p[0][1]:8.3f})@{a0:7.1f}deg to ({p[-1][0]:8.3f},{p[-1][1]:8.3f})@{a1:7.1f}deg")
        for k in idxs[1:-1]:
            arc_pts.add(k)
    coords = []
    for k in range(n):
        if k in arc_pts:
            continue
        coords.append(f"({pts[k][0]:.3f},{pts[k][1]:.3f})")
    print("      corners: " + " ".join(coords))


def main():
    key, axis, coord = sys.argv[1], sys.argv[2], float(sys.argv[3])
    png = None
    raw = "--raw" in sys.argv
    if "--png" in sys.argv:
        png = sys.argv[sys.argv.index("--png") + 1]
    mesh, p = get_mesh(key)
    loops = section_loops(mesh, axis, coord)
    other = [a for a in "xyz" if a != axis]
    print(f"[{key}] section {axis}={coord}  ->  {len(loops)} loop(s); in-plane axes = ({other[0]}, {other[1]})")
    for lp in loops:
        m = merge_collinear(lp)
        if raw:
            print("    RAW: " + " ".join(f"({q[0]:.3f},{q[1]:.3f})" for q in lp))
        describe_loop(m)
    if png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(14, 10))
        for lp in loops:
            closed = np.vstack([lp, lp[:1]])
            ax.plot(closed[:, 0], closed[:, 1], "-", lw=1.2)
            m = merge_collinear(lp)
            ax.plot(m[:, 0], m[:, 1], ".", ms=4)
        ax.set_aspect("equal")
        ax.grid(True, which="both", lw=0.3)
        ax.minorticks_on()
        ax.set_title(f"{key}  {axis}={coord}  axes=({other[0]},{other[1]})")
        fig.savefig(png, dpi=110, bbox_inches="tight")
        print(f"    saved {png}")


if __name__ == "__main__":
    main()
