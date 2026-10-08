"""Fit the internal screw thread of one base hole of a reference shell.

Usage: python thread_fit.py KEY CX CY
Collects mesh vertices on the hole wall, then searches pitch and handedness
for the helix coordinate u = (z - s * p * theta / 2pi) mod p that makes the
radius a single-valued function of u. Prints the best fit and the profile
(radius at the kink points) so it can be rebuilt exactly.
"""

import sys

import numpy as np

from refs import load_tris


def main():
    key, cx, cy = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    v = load_tris(key).reshape(-1, 3)
    v = np.unique(np.round(v, 5), axis=0)
    r = np.hypot(v[:, 0] - cx, v[:, 1] - cy)
    sel = (r > 2.7) & (r < 3.85) & (v[:, 2] > 0.7) & (v[:, 2] < 5.0)
    p3 = v[sel]
    r = r[sel]
    th = np.arctan2(p3[:, 1] - cy, p3[:, 0] - cx)
    z = p3[:, 2]
    print(f"{len(r)} wall vertices, r range {r.min():.3f} .. {r.max():.3f}")
    best = None
    for s in (1, -1):
        for p in np.arange(2.9, 3.3, 0.0025):
            u = np.mod(z - s * p * th / (2 * np.pi), p)
            order = np.argsort(u)
            # roughness: how much r jumps between neighbours in u
            rough = np.abs(np.diff(r[order])).mean()
            if best is None or rough < best[0]:
                best = (rough, s, p)
    rough, s, p = best
    print(f"best: handedness {'right' if s > 0 else 'left'} (z rises with {'counter' if s > 0 else ''}clockwise angle), "
          f"pitch {p:.4f}, roughness {rough:.4f}")
    u = np.mod(z - s * p * th / (2 * np.pi), p)
    order = np.argsort(u)
    # flat crest / root bands and their phase
    for lvl, name in ((r.max(), "major (groove floor)"), (r.min(), "minor (crest)")):
        band = np.abs(r - lvl) < 0.01
        uu = np.sort(u[band])
        # handle wrap: find the largest gap
        gaps = np.diff(np.r_[uu, uu[0] + p])
        k = np.argmax(gaps)
        start, end = uu[(k + 1) % len(uu)], uu[k]
        width = (end - start) % p
        print(f"{name}: r = {lvl:.4f}, u from {start:.4f} spanning {width:.4f}")
    # sample the profile
    bins = np.linspace(0, p, 26)
    prof = [np.median(r[(u >= a) & (u < b)]) if ((u >= a) & (u < b)).any() else np.nan
            for a, b in zip(bins[:-1], bins[1:])]
    print("profile r(u) in 25 bins:", " ".join(f"{x:.3f}" for x in prof))


if __name__ == "__main__":
    main()
