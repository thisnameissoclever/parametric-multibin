"""Export artifacts in an STL: zero-area triangles, vertices closer together
than 0.001 mm, and triangles that cross each other.

Usage: python export_check.py STL [STL ...]

Vertices are merged only where their coordinates are exactly equal, as written
in the file. Two triangles cross when an edge of one passes through the inside
of the other and they share no vertex; triangles that overlap while lying in
one plane are not detected. For each crossing pair the overlap depth is how
far the shallower triangle reaches through the other's plane.
"""

import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree


def load_exact(path):
    m = trimesh.load_mesh(path, process=False)
    flat = np.asarray(m.triangles, dtype=np.float64).reshape(-1, 3) + 0.0   # -0.0 becomes 0.0
    v, inv = np.unique(flat, axis=0, return_inverse=True)
    return v, inv.reshape(-1, 3)


def segment_crosses(p0, p1, a, b, c, tol=1e-10):
    """Whether each segment p0 -> p1 passes strictly through triangle abc."""
    d, e1, e2 = p1 - p0, b - a, c - a
    h = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, h)
    ok = np.abs(det) > 1e-14
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = p0 - a
    u = inv * np.einsum("ij,ij->i", s, h)
    q = np.cross(s, e1)
    w = inv * np.einsum("ij,ij->i", d, q)
    t = inv * np.einsum("ij,ij->i", e2, q)
    return ok & (u > tol) & (w > tol) & (u + w < 1 - tol) & (t > tol) & (t < 1 - tol)


def depth(ta, tb):
    """How far triangle ta reaches through the plane of tb, on its shallower side."""
    n = np.cross(tb[1] - tb[0], tb[2] - tb[0])
    n /= np.linalg.norm(n)
    s = (ta - tb[0]) @ n
    return min(max(s.max(), 0.0), max(-s.min(), 0.0))


def check(path):
    v, f = load_exact(path)
    tri = v[f]
    area2 = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    close = len(cKDTree(v).query_pairs(1e-3))
    tree = trimesh.Trimesh(v, f, process=False).triangles_tree
    lo, hi = tri.min(1) - 1e-9, tri.max(1) + 1e-9
    pairs = [(i, j) for i in range(len(f)) for j in tree.intersection(np.concatenate([lo[i], hi[i]])) if j > i]
    I, J = (np.array(x, dtype=np.int64) for x in zip(*pairs)) if pairs else (np.zeros(0, int),) * 2
    apart = ~(f[I][:, :, None] == f[J][:, None, :]).any(axis=(1, 2))
    I, J = I[apart], J[apart]
    hit = np.zeros(len(I), bool)
    for A, B in ((I, J), (J, I)):
        for k in range(3):
            hit |= segment_crosses(tri[A][:, k], tri[A][:, (k + 1) % 3], tri[B][:, 0], tri[B][:, 1], tri[B][:, 2])
    deepest = max((min(depth(tri[i], tri[j]), depth(tri[j], tri[i])) for i, j in zip(I[hit], J[hit])), default=0.0)
    print(f"{path}: {len(f)} triangles; {int((area2 < 2e-12).sum())} with zero area; "
          f"{close} vertex pairs closer than 0.001 mm; {int(hit.sum())} crossing triangle pairs, "
          f"deepest overlap {deepest:.2g} mm")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for path in sys.argv[1:]:
        check(path)


if __name__ == "__main__":
    main()
