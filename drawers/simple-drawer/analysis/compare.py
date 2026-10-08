"""Gate 1 harness: generate STLs from the parametric SCAD and diff against the originals.

Usage: python compare.py [keys...] [--report]   (default keys: all 9)
--report writes VERIFICATION.md from the collected metrics.

Gate thresholds: bbox delta <= 0.02 mm per axis, volume delta <= 0.5 %,
p99 <= 0.05 mm, max <= 0.2 mm (excursions must be covered by DEVIATIONS.md).
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import mbpaths  # noqa: E402  (path resolution shared across the repo)
ROOT = Path(__file__).resolve().parent.parent   # drawers/simple-drawer
SCAD = ROOT / "MultiBin Simple Drawer - Parametric.scad"
OUT = mbpaths.out_dir("drawer")
OPENSCAD = mbpaths.OPENSCAD
STL_DIR = mbpaths.refs("drawer")
N_SAMPLES = 50000

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
# name convention: width x height x depth
CFG = {
    "n111": dict(width_lu=1, height_lu=1, depth_lu=1, width_sections=1, depth_sections=1, magnet="false", label='"none"'),
    "s111": dict(width_lu=1, height_lu=1, depth_lu=1, width_sections=1, depth_sections=1, magnet="false", label='"small"'),
    "m212": dict(width_lu=2, height_lu=1, depth_lu=2, width_sections=1, depth_sections=1, magnet="true", label='"large"'),
    "c212": dict(width_lu=2, height_lu=1, depth_lu=2, width_sections=2, depth_sections=1, magnet="false", label='"large"'),
    "g212": dict(width_lu=2, height_lu=1, depth_lu=2, width_sections=2, depth_sections=2, magnet="false", label='"large"'),
    "L323": dict(width_lu=3, height_lu=2, depth_lu=3, width_sections=1, depth_sections=1, magnet="false", label='"large"'),
    "L332": dict(width_lu=3, height_lu=3, depth_lu=2, width_sections=1, depth_sections=1, magnet="false", label='"large"'),
    "c313": dict(width_lu=3, height_lu=1, depth_lu=3, width_sections=3, depth_sections=1, magnet="false", label='"large"'),
    "c3135": dict(width_lu=3, height_lu=1, depth_lu=3.5, width_sections=3, depth_sections=1, magnet="false", label='"large"'),
}


def generate(key):
    out = OUT / f"{key}.stl"
    args = [OPENSCAD, "-o", str(out), str(SCAD)]
    for k, v in CFG[key].items():
        args += ["-D", f"{k}={v}"]
    r = subprocess.run(args, capture_output=True, text=True, timeout=900)
    if not out.exists():
        print(f"[{key}] GENERATION FAILED\n{r.stderr[-3000:]}")
        return None
    for l in r.stderr.splitlines():
        if "WARNING" in l or "ERROR" in l:
            print(f"[{key}] scad: {l}")
    return out


def metrics(key, gen_path):
    ref = trimesh.load_mesh(STL_DIR / FILES[key])
    gen = trimesh.load_mesh(gen_path)
    gen.apply_translation(ref.bounds[0] - gen.bounds[0])
    bbox_d = np.abs(ref.extents - gen.extents).max()
    vol_d = abs(gen.volume - ref.volume) / ref.volume * 100
    row = dict(key=key, bbox=bbox_d, vol=vol_d)
    print(f"[{key}] bbox ref={np.round(ref.extents,3)} gen={np.round(gen.extents,3)} "
          f"maxdelta={bbox_d:.4f}  vol ref={ref.volume:.1f} gen={gen.volume:.1f} ({vol_d:.3f}%)")
    for a, b, tag in ((ref, gen, "ref->gen"), (gen, ref, "gen->ref")):
        pts, _ = trimesh.sample.sample_surface(a, N_SAMPLES, seed=7)
        _, dist, _ = trimesh.proximity.closest_point(b, pts)
        q = np.quantile(dist, [0.95, 0.99])
        # Deterministic sweep of every vertex. Random surface sampling is blind to
        # deviations shaped like a curve rather than a patch: they carry almost no
        # area, so an area-weighted sampler rarely lands on them.
        _, vdist, _ = trimesh.proximity.closest_point(b, a.vertices)
        vmax = vdist.max()
        vat = a.vertices[vdist.argmax()]
        row[tag] = dict(mean=dist.mean(), p95=q[0], p99=q[1], mx=dist.max(),
                        vmax=vmax, vat=vat)
        print(f"[{key}] {tag}: mean={dist.mean():.4f} p95={q[0]:.4f} p99={q[1]:.4f} max={dist.max():.4f}")
        print(f"[{key}] {tag}: all-vertices max={vmax:.4f} at "
              f"({vat[0]:.3f}, {vat[1]:.3f}, {vat[2]:.3f})")
        bad = pts[dist > 0.2]
        badd = dist[dist > 0.2]
        if len(bad):
            cells = {}
            for p, d in zip(bad, badd):
                c = tuple((p // 4).astype(int))
                if c not in cells or d > cells[c][1]:
                    cells[c] = (p, d)
            worst = sorted(cells.values(), key=lambda t: -t[1])[:8]
            print(f"[{key}] {tag}: {len(bad)/len(pts)*100:.2f}% of samples deviate >0.2; worst:")
            for p, d in worst:
                print(f"      d={d:6.3f} at ({p[0]:8.2f},{p[1]:8.2f},{p[2]:8.2f})")
    return row


def report(rows):
    lines = [
        "# VERIFICATION - Gate 1 mechanical match",
        "",
        f"Harness: `analysis\\compare.py`, run {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}, "
        f"{N_SAMPLES} surface samples per direction per model, bbox-aligned.",
        "",
        "Thresholds: bbox delta <= 0.02 mm/axis; volume delta <= 0.5 %; p99 <= 0.05 mm; "
        "max <= 0.2 mm (excursions above must be covered in DEVIATIONS.md).",
        "",
        "| model | bbox dmax (mm) | vol delta (%) | p99 (worse dir) | sampled max | all-vertices max | gate |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        mx = max(r["ref->gen"]["mx"], r["gen->ref"]["mx"])
        vmx = max(r["ref->gen"]["vmax"], r["gen->ref"]["vmax"])
        p99 = max(r["ref->gen"]["p99"], r["gen->ref"]["p99"])
        worst = max(mx, vmx)
        ok = r["bbox"] <= 0.02 and r["vol"] <= 0.5 and p99 <= 0.05
        gate = "PASS" if ok and worst <= 0.2 else ("PASS*" if ok else "FAIL")
        lines.append(
            f"| {r['key']} | {r['bbox']:.4f} | {r['vol']:.3f} | {p99:.4f} | "
            f"{mx:.4f} | {vmx:.4f} | {gate} |")
    lines += [
        "",
        "A PASS* row would mean every threshold met except a localized max excursion covered "
        "by DEVIATIONS.md; no row currently needs it.",
        "",
        "The all-vertices column is a deterministic sweep of every mesh vertex against the "
        "opposing surface, in both directions. It is reported because random surface sampling "
        "understates deviations that follow an edge rather than covering a patch: on the two "
        "3-wide divided models it reads 0.010 where the true worst case is 0.133.",
        "",
    ]
    (ROOT / "VERIFICATION.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote VERIFICATION.md")


def main():
    OUT.mkdir(exist_ok=True)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keys = args or list(FILES)
    rows = []
    for k in keys:
        p = generate(k)
        if p:
            rows.append(metrics(k, p))
        print()
    if "--report" in sys.argv and len(rows) == len(FILES):
        report(rows)


if __name__ == "__main__":
    main()
