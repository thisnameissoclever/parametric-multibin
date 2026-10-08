"""Render a spread of configurations and check each mesh is sound.

Checks per config: OpenSCAD exits clean, the mesh is watertight, winding
consistent and a single body, the outer box matches 50w-7 by 50d+7 by 50h-7,
and the base sits on z = 0.
"""

import subprocess
import sys
from itertools import product
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import mbpaths  # noqa: E402  (path resolution shared across the repo)
ROOT = Path(__file__).resolve().parent.parent   # drawers/simple-drawer
SCAD = ROOT / "MultiBin Simple Drawer - Parametric.scad"
OUT = mbpaths.out_dir("drawer", "sweep")
OPENSCAD = mbpaths.OPENSCAD


def check(w, h, d, ws, ds, mag, lab, dh=12):
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"w{w}_h{h}_d{d}_c{ws}x{ds}_{'M' if mag else 'n'}_{lab}_dh{dh}"
    stl = OUT / f"{name}.stl"
    args = [OPENSCAD, "-o", str(stl), str(SCAD),
            "-D", f"width_lu={w}", "-D", f"height_lu={h}", "-D", f"depth_lu={d}",
            "-D", f"width_sections={ws}", "-D", f"depth_sections={ds}",
            "-D", f"magnet={'true' if mag else 'false'}", "-D", f'label="{lab}"',
            "-D", f"divider_height_lu={dh}"]
    r = subprocess.run(args, capture_output=True, text=True, timeout=1800)
    bad = [l for l in r.stderr.splitlines() if "ERROR" in l or ("WARNING" in l and "ECHO" not in l)]
    if not stl.exists():
        return name, "RENDER FAILED", bad
    m = trimesh.load_mesh(stl)
    m.merge_vertices()
    exp = np.array([50 * w - 7, 50 * d + 7, 50 * h - 7])
    ok = (m.is_watertight and m.is_winding_consistent and m.body_count == 1
          and m.volume > 0 and np.allclose(m.extents, exp, atol=0.011)
          and abs(m.bounds[0][2]) < 1e-6)
    detail = (f"watertight={m.is_watertight} winding={m.is_winding_consistent} "
              f"bodies={m.body_count} ext={np.round(m.extents, 3)} exp={exp} "
              f"zmin={m.bounds[0][2]:.6f}")
    return name, ("PASS" if ok and not bad else "FAIL"), [detail] + bad


CASES = [
    # width, height, depth, cols, rows, magnet, label, divider height
    (1, 0.5, 1, 1, 1, True, "large", 12),
    (1, 1, 1, 1, 1, False, "large", 12),
    (1.5, 1, 1, 1, 1, False, "large", 12),
    (2.5, 1, 1.5, 2, 2, True, "large", 12),
    (3, 1.5, 3, 4, 3, True, "large", 12),
    (2, 2, 2, 3, 2, False, "large", 0.5),
    (1, 1, 1, 12, 12, False, "none", 12),
    (12, 1, 1.5, 12, 1, False, "large", 12),
    (1, 12, 1, 1, 1, False, "none", 12),
    (11.5, 2, 1.5, 6, 2, True, "large", 1),
    (1, 1, 8, 1, 4, False, "small", 12),
    (4, 1, 2, 4, 1, False, "large", 12),
    (2, 0.5, 1, 2, 1, True, "large", 12),
    (1, 9, 1, 1, 1, False, "none", 12),
    (3, 3.5, 2.5, 2, 2, True, "small", 2),
]

if __name__ == "__main__":
    fails = 0
    for c in CASES:
        name, verdict, detail = check(*c)
        print(f"{verdict:4s} {name}")
        if verdict != "PASS":
            fails += 1
            for line in detail:
                print(f"       {line}")
    print(f"\n{len(CASES) - fails}/{len(CASES)} configurations sound")
    sys.exit(1 if fails else 0)
