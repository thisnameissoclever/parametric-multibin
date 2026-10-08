"""Sweep depth x height and report any export that is not a clean single shell.

Catches the failure mode where CGAL emits a facet more than once, which leaves
edges shared by four faces and splits the mesh into several components even
though the underlying solid is correct.
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import mbpaths  # noqa: E402  (path resolution shared across the repo)
ROOT = Path(__file__).resolve().parent.parent   # drawers/simple-drawer
SCAD = ROOT / "MultiBin Simple Drawer - Parametric.scad"
OUT = mbpaths.out_dir("drawer", "grid")
OPENSCAD = mbpaths.OPENSCAD


def render(w, h, d, ws=1, ds=1, mag=False, lab="none"):
    OUT.mkdir(parents=True, exist_ok=True)
    stl = OUT / f"g_{w}_{h}_{d}_{ws}_{ds}.stl"
    subprocess.run([OPENSCAD, "-o", str(stl), str(SCAD),
                    "-D", f"width_lu={w}", "-D", f"height_lu={h}", "-D", f"depth_lu={d}",
                    "-D", f"width_sections={ws}", "-D", f"depth_sections={ds}",
                    "-D", f"magnet={'true' if mag else 'false'}", "-D", f'label="{lab}"'],
                   capture_output=True, text=True, timeout=1800)
    return stl


def audit(stl):
    m = trimesh.load_mesh(stl)
    m.merge_vertices()
    e, c = np.unique(m.edges_sorted, axis=0, return_counts=True)
    bad = int((c != 2).sum())
    tri = np.sort(m.faces, axis=1)
    _, counts = np.unique(tri, axis=0, return_counts=True)
    dup = int((counts > 1).sum())
    return dict(watertight=m.is_watertight, bodies=m.body_count,
                bad_edges=bad, dup_faces=dup, euler=m.euler_number)


if __name__ == "__main__":
    depths = [1, 1.5, 2, 2.5, 3]
    heights = [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8]
    fails = []
    for d in depths:
        row = []
        for h in heights:
            r = audit(render(1, h, d))
            ok = r["watertight"] and r["bodies"] == 1 and r["bad_edges"] == 0 and r["dup_faces"] == 0
            row.append("." if ok else "X")
            if not ok:
                fails.append((d, h, r))
        print(f"depth {d:4}: " + " ".join(row))
    print("heights:    " + " ".join(f"{h:g}"[-1] for h in heights))
    if fails:
        print(f"\n{len(fails)} FAILING combinations:")
        for d, h, r in fails:
            print(f"  depth={d} height={h}: {r}")
    else:
        print(f"\nall {len(depths)*len(heights)} depth/height combinations export a clean single shell")
    sys.exit(1 if fails else 0)
