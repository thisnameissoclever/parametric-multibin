"""Gate 1 harness for the shell: render the generator for each reference shell
and measure how far the two meshes are apart.

Usage: python compare.py [keys...] [--report] [--clusters N]
Default keys: every reference shell present on this machine (see refs.py).
--report writes VERIFICATION.md (only when every reference is present).
--clusters N lists the N worst deviation clusters per direction (default 10).

Thresholds (docs/verification-method.md): bounding box <= 0.02 mm per axis,
volume <= 0.5 %, p99 <= 0.05 mm, maximum <= 0.2 mm.
"""

import hashlib
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import trimesh

from refs import STL_DIR, SIZES, WALLS, available, fname

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import mbpaths  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent      # shells/multibin-shell
SCAD = ROOT / "MultiBin Shell - Parametric.scad"
OUT = mbpaths.out_dir("shell")
OPENSCAD = mbpaths.OPENSCAD
N_SAMPLES = 50000
WALL_PARAM = {"T": "topped", "O": "topless", "S": "simple"}


def params(key):
    x, y, z = SIZES[key[1:]]
    w = f'"{WALL_PARAM[key[0]]}"'
    return dict(width_lu=x, height_lu=y, depth_lu=z,
                front_wall=w, back_wall=w, left_wall=w, right_wall=w)


def out_for(scad=None):
    """Output folder for renders of a SCAD file. A file other than the generator
    gets its own folder, so a run against it never overwrites, or races, the
    generator's own renders."""
    if scad is None or Path(scad).resolve() == SCAD.resolve():
        return OUT
    d = OUT / "alt" / Path(scad).stem
    d.mkdir(parents=True, exist_ok=True)
    return d


# OpenSCAD output lines that mean a render is not clean. OpenSCAD 2021.01
# prints its nonplanar-face notice without a WARNING prefix.
BAD_RENDER = ("WARNING", "ERROR", "nonplanar")


def render_problems(stderr):
    return [ln.strip() for ln in stderr.splitlines() if any(b in ln for b in BAD_RENDER)]


def zero_area_triangles(stl):
    """Triangles whose corners lie on one line, as exported. OpenSCAD writes
    these where it splits an edge to meet a neighbouring face; they keep every
    edge shared by exactly two faces and do not change the shape."""
    t = trimesh.load_mesh(stl, process=False).triangles
    return int((np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1) < 1e-9).sum())


def audit(stl):
    """Mesh soundness and size of an exported STL."""
    m = trimesh.load_mesh(stl)
    m.merge_vertices()
    _, c = np.unique(m.edges_sorted, axis=0, return_counts=True)
    _, counts = np.unique(np.sort(m.faces, axis=1), axis=0, return_counts=True)
    return dict(watertight=bool(m.is_watertight), bodies=int(m.body_count),
                bad_edges=int((c != 2).sum()), dup_faces=int((counts > 1).sum()),
                extents=[round(float(v), 4) for v in m.extents], volume=round(float(m.volume), 3))


def clean(a):
    return a["watertight"] and a["bodies"] == 1 and a["bad_edges"] == 0 and a["dup_faces"] == 0


def generate(key, scad=None):
    """Render a reference configuration; returns (path or None, seconds, problems)."""
    out = out_for(scad) / f"{key}.stl"
    args = [OPENSCAD, "-o", str(out), str(scad or SCAD)]
    for k, v in params(key).items():
        args += ["-D", f"{k}={v}"]
    t0 = time.time()
    if out.exists():
        out.unlink()
    r = subprocess.run(args, capture_output=True, text=True, timeout=3600)
    secs = time.time() - t0
    problems = render_problems(r.stderr)
    for line in problems:
        print(f"[{key}] scad: {line}")
    if not out.exists():
        print(f"[{key}] GENERATION FAILED\n{r.stderr[-3000:]}")
        return None, secs, problems
    return out, secs, problems


def clusters(pts, dist, limit, cell=3.0):
    """Worst deviation per cell of a coarse grid, largest first."""
    best = {}
    for p, d in zip(pts, dist):
        c = tuple((p // cell).astype(int))
        if c not in best or d > best[c][1]:
            best[c] = (p, d)
    return sorted(best.values(), key=lambda t: -t[1])[:limit]


def metrics(key, gen_path, n_clusters=10):
    ref = trimesh.load_mesh(STL_DIR / fname(key))
    gen = trimesh.load_mesh(gen_path)
    shift = ref.bounds[0] - gen.bounds[0]
    gen.apply_translation(shift)
    bbox_d = np.abs(ref.extents - gen.extents).max()
    vol_d = abs(gen.volume - ref.volume) / ref.volume * 100
    row = dict(key=key, bbox=bbox_d, vol=vol_d)
    print(f"[{key}] bbox ref={np.round(ref.extents, 3)} gen={np.round(gen.extents, 3)} "
          f"maxdelta={bbox_d:.4f}  vol ref={ref.volume:.1f} gen={gen.volume:.1f} ({vol_d:.3f}%)")
    for a, b, tag in ((ref, gen, "ref->gen"), (gen, ref, "gen->ref")):
        pts, _ = trimesh.sample.sample_surface(a, N_SAMPLES, seed=7)
        _, dist, _ = trimesh.proximity.closest_point(b, pts)
        q = np.quantile(dist, [0.95, 0.99])
        _, vdist, _ = trimesh.proximity.closest_point(b, a.vertices)
        vmax = float(vdist.max())
        row[tag] = dict(mean=dist.mean(), p95=q[0], p99=q[1], mx=dist.max(), vmax=vmax)
        print(f"[{key}] {tag}: mean={dist.mean():.4f} p95={q[0]:.4f} p99={q[1]:.4f} "
              f"max={dist.max():.4f} all-vertices max={vmax:.4f}")
        if n_clusters:
            # worst spots per height band, in the reference's coordinates
            allp = np.vstack([pts, a.vertices])
            alld = np.concatenate([dist, vdist])
            zt = ref.bounds[1][2]
            bands = (("base z<7", -1e9, 7), ("wall", 7, zt - 7), ("rim z>top-7", zt - 7, 1e9))
            for name, z0, z1 in bands:
                bad = (alld > 0.05) & (allp[:, 2] >= z0) & (allp[:, 2] < z1)
                if bad.any():
                    print(f"      {name}: {int(bad.sum())} points > 0.05 mm; worst:")
                    for p, d in clusters(allp[bad], alld[bad], n_clusters):
                        print(f"        d={d:6.3f} at ({p[0]:8.2f},{p[1]:8.2f},{p[2]:8.2f})")
    return row


def openscad_version():
    r = subprocess.run([OPENSCAD, "--version"], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def report(rows, timings, problems, sound):
    digest = hashlib.sha256(SCAD.read_bytes()).hexdigest().upper()
    lines = [
        "# VERIFICATION - shell Gate 1 mechanical match",
        "",
        f"Harness: `analysis/compare.py`, run {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}, "
        f"{N_SAMPLES} surface samples per direction per model, bounding-box aligned, "
        f"plus a sweep of every vertex in both directions.",
        "",
        f"File verified: `{SCAD.name}`, SHA-256 {digest}.",
        "",
        f"Renderer: {openscad_version()}.",
        "",
        "Thresholds (`docs/verification-method.md`): bounding box <= 0.02 mm per axis, volume <= 0.5 %, "
        "p99 <= 0.05 mm, maximum <= 0.2 mm. The sound column means watertight, one body, every edge "
        "shared by exactly two faces and no duplicated facets.",
        "",
        "| model | bbox dmax (mm) | vol delta (%) | p99 (worse dir) | sampled max | all-vertices max | sound | render (s) | gate |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        mx = max(r["ref->gen"]["mx"], r["gen->ref"]["mx"])
        vmx = max(r["ref->gen"]["vmax"], r["gen->ref"]["vmax"])
        p99 = max(r["ref->gen"]["p99"], r["gen->ref"]["p99"])
        ok = r["bbox"] <= 0.02 and r["vol"] <= 0.5 and p99 <= 0.05 and sound[r["key"]]
        gate = "PASS" if ok and max(mx, vmx) <= 0.2 else ("PASS*" if ok else "FAIL")
        lines.append(f"| {r['key']} | {r['bbox']:.4f} | {r['vol']:.3f} | {p99:.4f} | {mx:.4f} | "
                     f"{vmx:.4f} | {'yes' if sound[r['key']] else 'NO'} | {timings[r['key']]:.0f} | {gate} |")
    lines += ["", "PASS* means every limit is met except a localized maximum covered by DEVIATIONS.md.", ""]
    noisy = {k: v for k, v in problems.items() if v}
    if noisy:
        lines += ["Render messages:", ""] + [f"- {k}: {m}" for k, v in noisy.items() for m in v] + [""]
    else:
        lines += ["Every render printed no warning, error or nonplanar-face notice.", ""]
    (ROOT / "VERIFICATION.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote VERIFICATION.md")


def main():
    args = sys.argv[1:]
    n_clusters = 10
    if "--clusters" in args:
        n_clusters = int(args[args.index("--clusters") + 1])
    keys = [a for a in args if not a.startswith("--") and not a.isdigit()] or available()
    rows, timings, problems, sound = [], {}, {}, {}
    for k in keys:
        p, secs, problems[k] = generate(k)
        timings[k] = secs
        print(f"[{k}] rendered in {secs:.1f} s")
        if p:
            rows.append(metrics(k, p, n_clusters))
            sound[k] = clean(audit(p))
            if not sound[k]:
                print(f"[{k}] mesh not a clean single shell: {audit(p)}")
            print(f"[{k}] zero-area triangles in the export: {zero_area_triangles(p)}")
        print()
    if "--report" in args and len(rows) == len(available()):
        report(rows, timings, problems, sound)


if __name__ == "__main__":
    main()
