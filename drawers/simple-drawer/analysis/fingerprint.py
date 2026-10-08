"""Pass 1: structural fingerprint of each MultiBin drawer STL.

For every model, print:
  - bounding box, triangle count, volume
  - horizontal planes (normal ~ +/-Z): z, facing, total area
  - vertical planes (normal ~ +/-X or +/-Y): coordinate, facing, total area
  - slanted face groups (chamfers): unit normal, total area
Coordinates rounded to 0.001 mm for grouping (STL stores float32).
"""

import sys
import struct
from pathlib import Path
from collections import defaultdict

import numpy as np

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


def load_stl(path: Path):
    data = path.read_bytes()
    if data[:5].lower() == b"solid" and b"facet" in data[:1000]:
        # ASCII STL
        verts = []
        for line in data.decode(errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("vertex"):
                verts.append([float(v) for v in line.split()[1:4]])
        tris = np.array(verts, dtype=np.float64).reshape(-1, 3, 3)
        return tris
    n = struct.unpack_from("<I", data, 80)[0]
    rec = np.frombuffer(data, dtype=np.uint8, count=n * 50, offset=84)
    rec = rec.reshape(n, 50)
    floats = rec[:, :48].copy().view("<f4").reshape(n, 4, 3)
    return floats[:, 1:4, :].astype(np.float64)  # drop stored normal, keep 3 verts


def tri_normals_areas(tris):
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    cr = np.cross(v1 - v0, v2 - v0)
    area2 = np.linalg.norm(cr, axis=1)
    keep = area2 > 1e-12
    normals = np.zeros_like(cr)
    normals[keep] = cr[keep] / area2[keep][:, None]
    return normals, area2 / 2.0


def volume(tris):
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    return float(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0)


def r3(x):
    return round(float(x), 3)


def plane_report(tris, normals, areas, axis, sign_tol=0.9999):
    """Group triangles whose normal is +/- unit vector along `axis` by their plane coordinate."""
    out = defaultdict(float)
    comp = normals[:, axis]
    for s in (+1, -1):
        mask = s * comp > sign_tol
        if not mask.any():
            continue
        coords = tris[mask][:, :, axis].mean(axis=1)  # all three verts share it; mean is exact enough
        for c, a in zip(np.round(coords, 3), areas[mask]):
            out[(s, float(c))] += float(a)
    return sorted(out.items(), key=lambda kv: kv[0][1])


def slant_report(tris, normals, areas, tol=0.9999):
    """Group triangles not axis-aligned by rounded unit normal."""
    ax = np.abs(normals)
    mask = (ax[:, 0] < tol) & (ax[:, 1] < tol) & (ax[:, 2] < tol)
    out = defaultdict(float)
    for nrm, a in zip(np.round(normals[mask], 4), areas[mask]):
        out[tuple(nrm)] += float(a)
    return sorted(out.items(), key=lambda kv: -kv[1])


def describe(key, fname):
    tris = load_stl(STL_DIR / fname)
    normals, areas = tri_normals_areas(tris)
    lo = tris.reshape(-1, 3).min(axis=0)
    hi = tris.reshape(-1, 3).max(axis=0)
    print(f"\n{'='*88}\n[{key}] {fname}")
    print(f"  tris={len(tris)}  volume={volume(tris):.2f} mm^3")
    print(f"  bbox min=({lo[0]:.3f}, {lo[1]:.3f}, {lo[2]:.3f})  max=({hi[0]:.3f}, {hi[1]:.3f}, {hi[2]:.3f})")
    print(f"  size =({hi[0]-lo[0]:.3f}, {hi[1]-lo[1]:.3f}, {hi[2]-lo[2]:.3f})")
    for axis, name in ((2, "Z"), (0, "X"), (1, "Y")):
        rep = plane_report(tris, normals, areas, axis)
        if rep:
            print(f"  -- planes normal to {name} (facing, coord) : area")
            for (s, c), a in rep:
                face = ("+" if s > 0 else "-") + name
                print(f"     {face} @ {c:9.3f} : {a:9.2f}")
    sl = slant_report(tris, normals, areas)
    if sl:
        print("  -- slanted face groups (normal) : area")
        for nrm, a in sl:
            print(f"     n=({nrm[0]:7.4f},{nrm[1]:7.4f},{nrm[2]:7.4f}) : {a:9.2f}")


if __name__ == "__main__":
    keys = sys.argv[1:] or list(FILES)
    for k in keys:
        describe(k, FILES[k])
