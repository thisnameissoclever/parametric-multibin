"""Measure the surface deviation confined to the divider end-flare transition.

The originals build that transition as a single plane through the divider-wall
corner, so its tip sits slightly lower in z than a hulled transition does. This
reports the perpendicular surface distance that difference actually produces,
which is what matters for printing, rather than the vertex z offset.
"""

import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).parent))
from compare import FILES, STL_DIR, OUT

key = sys.argv[1] if len(sys.argv) > 1 else "c212"
# argv is [script, key, x0, x1, y0, y1, z0, z1], so a supplied box makes len 8.
# Testing for more than 8 silently ignored the box and reused the default one.
if len(sys.argv) >= 8:
    box = [float(v) for v in sys.argv[2:8]]
elif len(sys.argv) > 2:
    raise SystemExit("box needs six numbers: x0 x1 y0 y1 z0 z1")
else:
    box = [24.9, 26.6, -3.1, -0.9, 28.5, 34.5]

ref = trimesh.load_mesh(STL_DIR / FILES[key])
gen = trimesh.load_mesh(OUT / f"{key}.stl")
gen.apply_translation(ref.bounds[0] - gen.bounds[0])

lo = np.array(box[0::2])
hi = np.array(box[1::2])

for a, b, tag in ((ref, gen, "ref->gen"), (gen, ref, "gen->ref")):
    pts, _ = trimesh.sample.sample_surface(a, 400000, seed=3)
    m = np.all((pts >= lo) & (pts <= hi), axis=1)
    if not m.any():
        print(f"[{key}] {tag}: no samples in box")
        continue
    _, d, _ = trimesh.proximity.closest_point(b, pts[m])
    i = d.argmax()
    print(f"[{key}] {tag}: {m.sum()} samples in the flare box, "
          f"mean={d.mean():.5f} max={d.max():.5f} at "
          f"({pts[m][i][0]:.3f}, {pts[m][i][1]:.3f}, {pts[m][i][2]:.3f})")
