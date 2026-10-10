"""Mesh artifacts in an STL: zero-area triangles, separate vertices closer
together than 0.0001 mm, and triangles that cross each other.

Usage: python export_check.py STL|3MF [...]

For a 3MF file, which stores each vertex once with an index, it counts
groups of separate vertices written at identical coordinates, and the edges
left shared by other than two triangles once vertices closer together than
0.00001 mm, and then 0.0001 mm, are merged. A program that merges vertices by
position, as many do on import, would fold the mesh at either kind of fault.

Vertices are merged only where their coordinates are exactly equal, as written
in the file. Two triangles cross when an edge of one passes through the inside
of the other, inside it or across one of its edges, away from its corners, and
they share at most one vertex. Not detected: triangles that overlap while lying
in one plane, and neighbours that share an edge. For each
crossing pair the overlap depth is how far the shallower triangle reaches
through the other's plane. A triangle has zero area when twice its area is
under 2e-12 mm2.
"""

import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter

import numpy as np
import trimesh
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

import policy


def load_exact(path):
    m = trimesh.load_mesh(path, process=False)
    flat = np.asarray(m.triangles, dtype=np.float64).reshape(-1, 3) + 0.0   # -0.0 becomes 0.0
    v, inv = np.unique(flat, axis=0, return_inverse=True)
    return v, inv.reshape(-1, 3)


def segment_crosses(p0, p1, a, b, c, tol=1e-10):
    """Whether each segment p0 -> p1 passes through triangle abc, its inside or
    its edges, at a point strictly inside the segment and away from the
    triangle's corners. A segment lying in the triangle's plane is not tested."""
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
    hit = p0 + t[:, None] * d
    corner = np.min([np.linalg.norm(hit - x, axis=1) for x in (a, b, c)], axis=0) < policy.CORNER_TOL
    return ok & (u > -tol) & (w > -tol) & (u + w < 1 + tol) & (t > tol) & (t < 1 - tol) & ~corner


def depth(ta, tb):
    """How far triangle ta reaches through the plane of tb, on its shallower
    side; None when tb has no area and so no plane."""
    n = np.cross(tb[1] - tb[0], tb[2] - tb[0])
    length = np.linalg.norm(n)
    if length < 1e-15:
        return None
    s = (ta - tb[0]) @ (n / length)
    return min(max(s.max(), 0.0), max(-s.min(), 0.0))


def pair_depth(ta, tb):
    """Overlap of a crossing pair: the smaller of the two reaches, measured
    against whichever triangles have a plane."""
    d = [x for x in (depth(ta, tb), depth(tb, ta)) if x is not None]
    return min(d) if d else 0.0


def crossings(v, f):
    """Number of crossing triangle pairs, and the deepest overlap in mm."""
    tri = v[f]
    tree = trimesh.Trimesh(v, f, process=False).triangles_tree
    lo, hi = tri.min(1) - 1e-9, tri.max(1) + 1e-9
    pairs = [(i, j) for i in range(len(f)) for j in tree.intersection(np.concatenate([lo[i], hi[i]])) if j > i]
    I, J = (np.array(x, dtype=np.int64) for x in zip(*pairs)) if pairs else (np.zeros(0, int),) * 2
    # neighbours sharing an edge (two vertices) are left out; a pair sharing one
    # vertex is kept, since its other edges can still pass through each other
    shared = (f[I][:, :, None] == f[J][:, None, :]).any(axis=2).sum(axis=1)
    I, J = I[shared < 2], J[shared < 2]
    hit = np.zeros(len(I), bool)
    for A, B in ((I, J), (J, I)):
        for k in range(3):
            hit |= segment_crosses(tri[A][:, k], tri[A][:, (k + 1) % 3], tri[B][:, 0], tri[B][:, 1], tri[B][:, 2])
    deepest = max((pair_depth(tri[i], tri[j]) for i, j in zip(I[hit], J[hit])), default=0.0)
    return int(hit.sum()), float(deepest)


def zero_area_count(v, f):
    tri = v[f]
    return int((np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) < 2e-12).sum())


def read_3mf(path):
    """The vertex coordinates of a 3MF file's mesh, as written, and its
    triangles, read as XML. A file with no vertices or no triangles is an
    error, so a reader that finds nothing cannot pass the checks."""
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith(".model"))))
    elements = [(e.tag.rsplit("}", 1)[-1], e) for e in root.iter()]
    coords = [(e.get("x"), e.get("y"), e.get("z")) for tag, e in elements if tag == "vertex"]
    tri = [(e.get("v1"), e.get("v2"), e.get("v3")) for tag, e in elements if tag == "triangle"]
    if not coords or not tri:
        raise ValueError(f"{path}: no mesh in the 3MF model ({len(coords)} vertices, {len(tri)} triangles)")
    return coords, np.array(tri, dtype=np.int64).reshape(-1, 3)


def coincident_3mf(path):
    """Groups of separate vertices with identical coordinates in a 3MF file."""
    coords, _ = read_3mf(path)
    # compared as numbers, so "0.000000" and "-0.000000" are the same position
    return sum(1 for n in Counter(tuple(float(c) + 0.0 for c in v) for v in coords).values() if n > 1)


def merge_faults(path, tol):
    """Edges of a 3MF file's mesh shared by other than two triangles once all
    vertices closer together than tol are merged, chains included, as a program
    that merges vertices by position on import would. A triangle the merge
    collapses is dropped."""
    coords, tri = read_3mf(path)
    v = np.array(coords, dtype=np.float64).reshape(-1, 3)
    pairs = np.array(sorted(cKDTree(v).query_pairs(tol)), dtype=np.int64).reshape(-1, 2)
    links = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(v), len(v)))
    _, label = connected_components(links, directed=False)
    t = label[tri]
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 2] != t[:, 0])]
    edges = np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), axis=1)
    _, count = np.unique(edges, axis=0, return_counts=True)
    return int((count != 2).sum())


def check(path):
    if str(path).lower().endswith(".3mf"):
        merged = "; ".join(f"merged within {tol:g} mm, {merge_faults(path, tol)} edges not shared by two triangles"
                           for tol in policy.MERGE_TOLS)
        print(f"{path}: {coincident_3mf(path)} groups of separate vertices at identical coordinates; {merged}")
        return
    v, f = load_exact(path)
    close = len(cKDTree(v).query_pairs(1e-4))
    n, deepest = crossings(v, f)
    print(f"{path}: {len(f)} triangles; {zero_area_count(v, f)} with zero area; "
          f"{close} vertex pairs closer than 0.0001 mm; {n} crossing triangle pairs, "
          f"deepest overlap {deepest:.2g} mm")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for path in sys.argv[1:]:
        check(path)


if __name__ == "__main__":
    main()
