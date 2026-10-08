"""Locate the worst deviations between a reference shell and a render, from a
sweep of every vertex in both directions (the same sweep compare.py reports as
its all-vertices maximum, with locations).

Usage: python worst_points.py KEY STL [N]
KEY is a reference key from refs.py, STL a render of the same configuration
(compare.py writes them to .local-build/out/shell/KEY.stl). Prints the N worst
points per direction (default 12) in the generator's frame: first cell centred
on the origin, base at z = 0.
"""

import sys

import numpy as np
import trimesh

from refs import STL_DIR, fname


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    key, gen_path = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) == 4 else 12
    ref = trimesh.load_mesh(STL_DIR / fname(key))
    gen = trimesh.load_mesh(gen_path)
    gen.apply_translation(ref.bounds[0] - gen.bounds[0])
    to_frame = -ref.bounds[0] + [-25, -25, 0]
    for label, a, b in (("render vertex -> reference surface", gen, ref),
                        ("reference vertex -> render surface", ref, gen)):
        v = np.unique(a.vertices.round(5), axis=0)
        _, d, _ = trimesh.proximity.closest_point(b, v)
        print(f"[{key}] {label}")
        for i in np.argsort(-d)[:n]:
            p = v[i] + to_frame
            print(f"   d={d[i]:.4f} at ({p[0]:8.3f}, {p[1]:8.3f}, {p[2]:8.3f})")


if __name__ == "__main__":
    main()
