"""Measure how deeply the front-bottom fillet cut reaches into a divider foot.

Answers the reviewer question of how the cut scales when a divider sits outside
its lip-gusset band. Prints, for columns inside and outside the protected band,
whether material is present just above the floor near the front wall.
"""

import sys
import numpy as np
import trimesh

path = sys.argv[1]
x_exposed = float(sys.argv[2])   # column inside the strip the cut can reach
x_protected = float(sys.argv[3])  # column inside the gusset-protected part
y_inner = float(sys.argv[4])      # front wall inner face

m = trimesh.load_mesh(path)
m.merge_vertices()
q = trimesh.proximity.ProximityQuery(m)

ys = [y_inner + 0.05, y_inner + 0.2, y_inner + 1.0, y_inner + 2.0, y_inner + 3.0]
zs = [1.62, 1.70, 1.75, 1.90, 2.50]


def row(x, y):
    pts = np.array([[x, y, z] for z in zs])
    d = q.signed_distance(pts)
    return "  ".join(f"z{z:<4}:{'solid' if v > 0 else 'void '}" for z, v in zip(zs, d))


print(f"exposed column x={x_exposed} (outside the gusset band, cut can reach it)")
for y in ys:
    print(f"  y={y:8.2f}  {row(x_exposed, y)}")
print(f"\nprotected column x={x_protected} (inside the gusset band)")
for y in ys:
    print(f"  y={y:8.2f}  {row(x_protected, y)}")
