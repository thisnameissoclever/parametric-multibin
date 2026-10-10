"""Locate the worst deviations between a reference shell and a render, from a
sweep of every vertex in both directions (the same sweep compare.py reports as
its all-vertices maximum, with locations).

Usage: python worst_points.py KEY STL [N] [--away-from-holes] [--below D]
KEY is a reference key from refs.py, STL a render of the same configuration
(compare.py writes them to .local-build/out/shell/KEY.stl). Prints the N worst
points per direction (default 12) in the generator's frame: first cell centred
on the origin, base at z = 0.

--away-from-holes leaves out vertices within 4.9 mm of a threaded hole's axis
below z 5.3, where the holes' faceting (DEVIATIONS.md M1) is the largest
difference, so smaller differences elsewhere show. --below D lists only
points less than D mm away, to show the differences under a known larger one.
"""

import sys

import numpy as np
import trimesh

from refs import STL_DIR, fname


def near_holes(p):
    """Points of the generator's frame within 4.9 of a threaded hole's axis,
    below z 5.3. The holes sit on the 25 mm grid offset 12.5 from the cell
    centres, so at x and y = 12.5 + 25k."""
    hx = (p[:, 0] + 25) % 25 - 12.5
    hy = (p[:, 1] + 25) % 25 - 12.5
    return (np.hypot(hx, hy) < 4.9) & (p[:, 2] < 5.3)


def main():
    args = sys.argv[1:]
    away = "--away-from-holes" in args
    args = [a for a in args if a != "--away-from-holes"]
    below = float("inf")
    if "--below" in args:
        i = args.index("--below")
        if i + 1 == len(args):
            sys.exit(__doc__)
        below = float(args[i + 1])
        del args[i:i + 2]
    if len(args) not in (2, 3):
        sys.exit(__doc__)
    key, gen_path = args[0], args[1]
    n = int(args[2]) if len(args) == 3 else 12
    ref = trimesh.load_mesh(STL_DIR / fname(key))
    gen = trimesh.load_mesh(gen_path)
    gen.apply_translation(ref.bounds[0] - gen.bounds[0])
    to_frame = -ref.bounds[0] + [-25, -25, 0]
    for label, a, b in (("render vertex -> reference surface", gen, ref),
                        ("reference vertex -> render surface", ref, gen)):
        v = np.unique(a.vertices.round(5), axis=0)
        if away:
            v = v[~near_holes(v + to_frame)]
        _, d, _ = trimesh.proximity.closest_point(b, v)
        v, d = v[d < below], d[d < below]
        print(f"[{key}] {label}{', away from the threaded holes' if away else ''}"
              f"{f', below {below:g} mm' if below < float('inf') else ''}")
        for i in np.argsort(-d)[:n]:
            p = v[i] + to_frame
            print(f"   d={d[i]:.4f} at ({p[0]:8.3f}, {p[1]:8.3f}, {p[2]:8.3f})")


if __name__ == "__main__":
    main()
