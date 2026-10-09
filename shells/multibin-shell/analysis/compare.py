"""Gate 1 harness for the shell: render the generator for each reference shell
and measure how far the two meshes are apart.

Usage: python compare.py [keys...] [--report] [--clusters N]
Default keys: every reference in refs.EXPECTED; a missing reference file is a
failure.
--report writes VERIFICATION.md; it refuses unless every reference in
refs.EXPECTED is present and no keys are given.
--clusters N lists the N worst deviation clusters per direction (default 10).
Exits 1 when any reference is missing or fails the gate column of the report.

Thresholds (docs/verification-method.md): bounding box <= 0.02 mm per axis,
volume <= 0.5 %, p99 <= 0.05 mm, maximum <= 0.2 mm.
"""

import hashlib
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import trimesh

from export_check import crossings, load_exact, zero_area_count
from refs import EXPECTED, STL_DIR, SIZES, WALLS, available, fname

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import mbpaths  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent      # shells/multibin-shell
SCAD = ROOT / "MultiBin Shell - Parametric.scad"
OUT = mbpaths.out_dir("shell")
OPENSCAD = mbpaths.OPENSCAD
N_SAMPLES = 50000
# the Gate 1 limits (docs/verification-method.md); regress.py uses these too
LIMITS = dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2)
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


# The lines OpenSCAD 2021.01 prints for every clean render: cache and timing
# statistics and the summary of the result. Any other line, such as a WARNING,
# an ERROR, a DEPRECATED notice, an ECHO or the nonplanar-face notice (which
# has no WARNING prefix), is a render message.
NORMAL_RENDER_LINE = re.compile(
    r"^(Geometries in cache|Geometry cache size in bytes|CGAL Polyhedrons in cache|CGAL cache size in bytes"
    r"|Total rendering time|Top level object is a 3D object|Vertices|Halfedges|Edges|Halffacets|Facets):"
    # one solid: OpenSCAD reports it as simple, with two volumes (outside and inside)
    r"|^Simple:\s+yes$|^Volumes:\s+2$")


def render_problems(stderr, expected=()):
    """Render messages in OpenSCAD's console output, except lines containing one
    of the expected texts."""
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    return [ln for ln in lines if not NORMAL_RENDER_LINE.match(ln) and not any(e in ln for e in expected)]


# Renders are exported as binary STL, which keeps 32-bit coordinates: about
# 0.00007 mm at 600 mm, the largest shell. OpenSCAD's default ASCII STL keeps
# six significant digits, 0.001 mm beyond 100 mm, and that rounding alone
# pushed vertices up to 0.0003 mm through neighbouring faces on 12 LU shells.
EXPORT_FORMAT = ["--export-format", "binstl"]

# deepest crossing between two triangles that a sound render may have: binary
# STL rounding stays under 0.0001 mm, and overlapping solids cross far deeper
CROSSING_LIMIT = 1e-3


def zero_area_triangles(stl):
    """Triangles whose corners lie on one line, as exported (see export_check)."""
    return zero_area_count(*load_exact(stl))


def geometry_digest(v):
    """SHA-256 of the mesh's vertex coordinates as written, sorted. Repeat
    renders of one generator write the same vertices, but OpenSCAD 2021.01
    splits some flat faces into triangles differently from run to run, so the
    digest leaves out how faces are split; audit's volume and soundness checks
    cover the faces themselves."""
    vs = np.unique(np.asarray(v, dtype="<f8"), axis=0)
    return hashlib.sha256(np.ascontiguousarray(vs).tobytes()).hexdigest()


def audit(stl):
    """Mesh soundness, size and geometry digest of an exported STL. Bodies are
    counted through shared edges, so two solids touching at one vertex are two."""
    v, f = load_exact(stl)
    m = trimesh.Trimesh(v, f, process=False)
    _, c = np.unique(np.sort(m.edges, axis=1), axis=0, return_counts=True)
    _, counts = np.unique(np.sort(f, axis=1), axis=0, return_counts=True)
    bodies = len(trimesh.graph.connected_components(m.face_adjacency, nodes=np.arange(len(f)), min_len=1))
    _, deepest = crossings(v, f)
    return dict(watertight=bool(m.is_watertight), winding=bool(m.is_winding_consistent), bodies=int(bodies),
                bad_edges=int((c != 2).sum()), dup_faces=int((counts > 1).sum()),
                crossing_depth=float(deepest),
                extents=[round(float(x), 4) for x in m.extents], volume=round(float(m.volume), 3),
                digest=geometry_digest(v))


def clean(a):
    """Watertight, consistently wound with positive volume, one body, every edge
    shared by exactly two faces, no duplicated facets, no deep crossings."""
    return (a["watertight"] and a["winding"] and a["volume"] > 0 and a["bodies"] == 1
            and a["bad_edges"] == 0 and a["dup_faces"] == 0 and a["crossing_depth"] <= CROSSING_LIMIT)


def generate(key, scad=None):
    """Render a reference configuration; returns (path or None, seconds, problems)."""
    out = out_for(scad) / f"{key}.stl"
    args = [OPENSCAD, "-o", str(out), *EXPORT_FORMAT, str(scad or SCAD)]
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


def measure(ref, gen, n_samples=N_SAMPLES):
    """Gate 1 measures between two meshes, gen moved so the bounding-box minimum
    corners coincide. Returns (row, spots): row has bbox, vol and, per direction,
    the sampled mean, p95, p99 and max and the all-vertices max (vmax); spots
    has each direction's points and distances, for locating the worst ones."""
    gen = gen.copy()
    gen.apply_translation(ref.bounds[0] - gen.bounds[0])
    row = dict(bbox=float(np.abs(ref.extents - gen.extents).max()),
               vol=float(abs(gen.volume - ref.volume) / ref.volume * 100))
    spots = {}
    for a, b, tag in ((ref, gen, "ref->gen"), (gen, ref, "gen->ref")):
        pts, _ = trimesh.sample.sample_surface(a, n_samples, seed=7)
        _, dist, _ = trimesh.proximity.closest_point(b, pts)
        _, vdist, _ = trimesh.proximity.closest_point(b, a.vertices)
        q = np.quantile(dist, [0.95, 0.99])
        row[tag] = dict(mean=float(dist.mean()), p95=float(q[0]), p99=float(q[1]), mx=float(dist.max()),
                        vmax=float(vdist.max()))
        spots[tag] = (np.vstack([pts, a.vertices]), np.concatenate([dist, vdist]))
    return row, spots


def summary(row):
    """The four gated numbers: bbox, vol, p99 in the worse direction, and the
    largest distance from samples or vertices in either direction."""
    a, b = row["ref->gen"], row["gen->ref"]
    # numpy's max carries a NaN through, so a failed measurement fails the limits
    return dict(bbox=float(row["bbox"]), vol=float(row["vol"]), p99=float(np.max([a["p99"], b["p99"]])),
                mx=float(np.max([a["mx"], b["mx"], a["vmax"], b["vmax"]])))


def metrics(key, gen_path, n_clusters=10):
    ref = trimesh.load_mesh(STL_DIR / fname(key))
    gen = trimesh.load_mesh(gen_path)
    row, spots = measure(ref, gen)
    row["key"] = key
    print(f"[{key}] bbox ref={np.round(ref.extents, 3)} gen={np.round(gen.extents, 3)} "
          f"maxdelta={row['bbox']:.4f}  vol ref={ref.volume:.1f} gen={gen.volume:.1f} ({row['vol']:.3f}%)")
    for tag in ("ref->gen", "gen->ref"):
        r = row[tag]
        print(f"[{key}] {tag}: mean={r['mean']:.4f} p95={r['p95']:.4f} p99={r['p99']:.4f} "
              f"max={r['mx']:.4f} all-vertices max={r['vmax']:.4f}")
        if n_clusters:
            # worst spots per height band, in the reference's coordinates
            allp, alld = spots[tag]
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


def scad_digest():
    """SHA-256 of the generator with LF line endings, as git stores it, so the
    digest matches `git show <commit>:<path> | sha256sum` on any machine."""
    return hashlib.sha256(SCAD.read_bytes().replace(b"\r\n", b"\n")).hexdigest().upper()


def gate(r, problems, sound):
    """PASS only when every limit is met, the mesh is sound and the render
    printed nothing beyond OpenSCAD's normal statistics."""
    s = summary(r)
    ok = all(s[k] <= LIMITS[k] for k in LIMITS) and sound[r["key"]] and not problems[r["key"]]   # NaN fails
    return "PASS" if ok else "FAIL"


def report(rows, timings, problems, sound):
    digest = scad_digest()
    lines = [
        "# VERIFICATION - shell Gate 1 mechanical match",
        "",
        f"Harness: `analysis/compare.py`, run {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}, "
        f"{N_SAMPLES} surface samples per direction per model, bounding-box aligned, "
        f"plus a sweep of every vertex in both directions.",
        "",
        f"File verified: `{SCAD.name}`, SHA-256 {digest}, computed with LF line endings as git "
        f"stores the file (`git show <commit>:\"shells/multibin-shell/{SCAD.name}\" | sha256sum`).",
        "",
        f"Renderer: {openscad_version()}.",
        "",
        "Columns: bbox dmax is the largest difference between the two bounding boxes on any axis; vol delta "
        "is the volume difference as a percentage of the reference's; p99 is the 99th percentile of the "
        "distances from sampled surface points to the other mesh, in whichever direction (reference to "
        "render, or render to reference) is worse; sampled max is the largest of those distances; and "
        "all-vertices max is the largest distance from any vertex of either mesh to the other.",
        "",
        f"Thresholds (`docs/verification-method.md`): bounding box <= {LIMITS['bbox']} mm per axis, volume <= "
        f"{LIMITS['vol']} %, p99 <= {LIMITS['p99']} mm, maximum <= {LIMITS['mx']} mm. The sound column means "
        "watertight and consistently wound with positive volume, one body (counted through shared edges), every "
        "edge shared by exactly two faces, no duplicated facets, and no two triangles that share at most one "
        f"vertex crossing by more than {CROSSING_LIMIT:g} mm. The gate column is PASS only when every limit is "
        "met, the mesh is sound and the render printed nothing beyond OpenSCAD's normal statistics.",
        "",
        "A feature smaller than the 0.2 mm maximum, such as a 0.2 mm opening chamfer or a 0.1 mm slit, could be "
        "missing without failing these limits; the regression gate (`analysis/regress.py`) holds every reference "
        "to its locked worst point within 0.002 mm, which catches that.",
        "",
        "The sampled columns can differ in the fourth decimal between runs, because OpenSCAD does not "
        "write its triangles in a fixed order; the bounding box, volume and all-vertices columns repeat.",
        "",
        "| model | bbox dmax (mm) | vol delta (%) | p99 (worse dir) | sampled max | all-vertices max | sound | render (s) | gate |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        mx = max(r["ref->gen"]["mx"], r["gen->ref"]["mx"])
        vmx = max(r["ref->gen"]["vmax"], r["gen->ref"]["vmax"])
        p99 = max(r["ref->gen"]["p99"], r["gen->ref"]["p99"])
        lines.append(f"| {r['key']} | {r['bbox']:.4f} | {r['vol']:.3f} | {p99:.4f} | {mx:.4f} | "
                     f"{vmx:.4f} | {'yes' if sound[r['key']] else 'NO'} | {timings[r['key']]:.0f} | "
                     f"{gate(r, problems, sound)} |")
    lines += [""]
    noisy = {k: v for k, v in problems.items() if v}
    if noisy:
        lines += ["Render messages:", ""] + [f"- {k}: {m}" for k, v in noisy.items() for m in v] + [""]
    else:
        lines += ["Every render printed nothing beyond OpenSCAD's normal statistics.", ""]
    (ROOT / "VERIFICATION.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote VERIFICATION.md")


def main():
    args = sys.argv[1:]
    n_clusters = 10
    if "--clusters" in args:
        n_clusters = int(args[args.index("--clusters") + 1])
    named = [a for a in args if not a.startswith("--") and not a.isdigit()]
    if "--report" in args:
        missing = [k for k in EXPECTED if k not in available()]
        if named or missing:
            print("refusing --report: it needs every reference in refs.EXPECTED and no named keys; "
                  f"missing: {missing or 'none'}")
            return 2
    keys = named or EXPECTED
    missing = [k for k in keys if not (STL_DIR / fname(k)).is_file()]
    for k in missing:
        print(f"[{k}] MISSING reference file: {fname(k)}")
    keys = [k for k in keys if k not in missing]
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
    if "--report" in args:
        if missing or len(rows) != len(EXPECTED):
            print("not writing VERIFICATION.md: a reference is missing or failed to render")
            return 1
        report(rows, timings, problems, sound)
    failed = missing + [k for k in keys if k not in sound] + [r["key"] for r in rows if gate(r, problems, sound) != "PASS"]
    if failed:
        print(f"FAIL: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
