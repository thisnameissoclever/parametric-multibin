"""Plane inventory of a reference shell: every flat face group with its area.

Usage: python fingerprint.py KEY [min_area]
Axis-aligned planes are grouped by facing and coordinate; other faces by
rounded unit normal and plane offset. Areas below min_area (default 1 mm^2)
are summarised rather than listed.
"""

import sys
from collections import defaultdict

import numpy as np

from refs import load_tris, normals_areas


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    key = sys.argv[1]
    min_area = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    tris = load_tris(key)
    n, a = normals_areas(tris)
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    print(f"[{key}] tris={len(tris)} bbox min={np.round(lo,3)} max={np.round(hi,3)}")
    for ax, name in ((2, "Z"), (0, "X"), (1, "Y")):
        groups = defaultdict(float)
        for s in (1, -1):
            m = s * n[:, ax] > 0.99999
            for c, ar in zip(np.round(tris[m][:, :, ax].mean(1), 3), a[m]):
                groups[(s, c)] += ar
        small = sum(v for v in groups.values() if v < min_area)
        print(f"-- planes normal to {name}  (listing area >= {min_area}; {small:.2f} mm2 in smaller groups)")
        for (s, c), ar in sorted(groups.items(), key=lambda kv: kv[0][1]):
            if ar >= min_area:
                print(f"   {'+' if s > 0 else '-'}{name} @ {c:9.3f} : {ar:9.2f}")
    ax = np.abs(n)
    m = (ax < 0.99999).all(1) & (a > 0)
    groups = defaultdict(float)
    for nrm, cen, ar in zip(np.round(n[m], 3), tris[m].mean(1), a[m]):
        d = round(float(np.dot(nrm, cen)), 2)
        groups[(tuple(nrm), d)] += ar
    print(f"-- slanted groups (normal, offset) with area >= {min_area}")
    for (nrm, d), ar in sorted(groups.items(), key=lambda kv: -kv[1]):
        if ar >= min_area:
            print(f"   n=({nrm[0]:6.3f},{nrm[1]:6.3f},{nrm[2]:6.3f}) d={d:8.2f} : {ar:9.2f}")


if __name__ == "__main__":
    main()
