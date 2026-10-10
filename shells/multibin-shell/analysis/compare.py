"""Measuring tools for the shell's gate, and a diagnostic command.

Usage: python compare.py [keys...] [--clusters N]
Renders the generator for the named reference shells (default: every reference
in policy.REFERENCES) into .local-build/out/shell/KEY.stl and prints how far
each render is from its reference, the N worst deviation clusters per
direction (default 10) and the mesh audit.

This command is a diagnostic: it decides nothing and always exits 0. The gate
is regress.py, which uses the functions below and writes VERIFICATION.md.
"""

import hashlib
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import trimesh

import policy
import refs
from export_check import crossings, load_exact, zero_area_count
from refs import SIZES, fname

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import mbpaths  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent      # shells/multibin-shell
SCAD = ROOT / "MultiBin Shell - Parametric.scad"
OUT = mbpaths.out_dir("shell")
OPENSCAD = mbpaths.OPENSCAD
# the command every render starts with; gate_test.py points it at a stand-in
OPENSCAD_COMMAND = [OPENSCAD]
WALL_PARAM = {"T": "topped", "O": "topless", "S": "simple"}


def params(key):
    """Generator parameters for a reference key."""
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


# ------------------------------------------------------------------ rendering

# The lines OpenSCAD 2021.01 prints for every clean render: cache and timing
# statistics and the summary of the result. Any other line, such as a WARNING,
# an ERROR, a DEPRECATED notice, an ECHO or the nonplanar-face notice (which
# has no WARNING prefix), is a render message.
NORMAL_RENDER_LINE = re.compile(
    r"^(Geometries in cache|Geometry cache size in bytes|CGAL Polyhedrons in cache|CGAL cache size in bytes"
    r"|Total rendering time|Top level object is a 3D object|Vertices|Halfedges|Edges|Halffacets|Facets):"
    # one solid: OpenSCAD reports it as simple, with two volumes (outside and inside)
    r"|^Simple:\s+yes$|^Volumes:\s+2$")


def render_problems(console, expected=()):
    """Render messages in OpenSCAD's console output, except lines containing one
    of the expected texts."""
    lines = [ln.strip() for ln in console.splitlines() if ln.strip()]
    return [ln for ln in lines if not NORMAL_RENDER_LINE.match(ln) and not any(e in ln for e in expected)]


def render(command, scad, params, out, expected=()):
    """Run OpenSCAD once and report what it did. Every render of the gate and
    of this command goes through here.

    command is the OpenSCAD command as a list of arguments. Any earlier file at
    out is deleted first, so a render that writes nothing can never be read
    from an older file. An STL is written in binary (policy.EXPORT_FORMAT).
    Returns a dict: path (None when no file was written), seconds, console
    (the end of the console output), problems (render messages other than the
    expected texts) and seen (the expected texts that appeared)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    args = [*command, "-o", str(out), *(policy.EXPORT_FORMAT if out.suffix.lower() == ".stl" else ()), str(scad)]
    for k, v in params.items():
        args += ["-D", f"{k}={v}"]
    t0 = time.time()
    r = subprocess.run(args, capture_output=True, text=True, timeout=3600)
    return dict(path=out if out.exists() else None, seconds=time.time() - t0, console=r.stderr[-3000:],
                problems=render_problems(r.stderr, expected), seen=[e for e in expected if e in r.stderr])


def openscad_version():
    r = subprocess.run([OPENSCAD, "--version"], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def scad_digest(path=None):
    """SHA-256 of the generator (or of the SCAD file at path) with Unix line
    endings, as git stores it, so the digest matches
    `git show <commit>:<path> | sha256sum` on any machine."""
    return hashlib.sha256(Path(path or SCAD).read_bytes().replace(b"\r\n", b"\n")).hexdigest().upper()


# ------------------------------------------------------------------ mesh audit

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
    _, per_edge = np.unique(np.sort(m.edges, axis=1), axis=0, return_counts=True)
    _, per_face = np.unique(np.sort(f, axis=1), axis=0, return_counts=True)
    bodies = len(trimesh.graph.connected_components(m.face_adjacency, nodes=np.arange(len(f)), min_len=1))
    _, deepest = crossings(v, f)
    return dict(watertight=bool(m.is_watertight), winding=bool(m.is_winding_consistent), bodies=int(bodies),
                bad_edges=int((per_edge != 2).sum()), dup_faces=int((per_face > 1).sum()),
                crossing_depth=float(deepest),
                extents=[round(float(x), 4) for x in m.extents], volume=round(float(m.volume), 3),
                digest=geometry_digest(v))


def clean(a):
    """Watertight, consistently wound with positive volume, one body, every edge
    shared by exactly two faces, no duplicated facets, no deep crossings."""
    return (a["watertight"] and a["winding"] and a["volume"] > 0 and a["bodies"] == 1
            and a["bad_edges"] == 0 and a["dup_faces"] == 0
            and a["crossing_depth"] <= policy.CROSSING_LIMIT)


def unsound_reasons(a):
    """Each property clean() requires that the audit a fails, in words."""
    out = []
    if not a["watertight"]:
        out.append("not watertight")
    if not a["winding"]:
        out.append("inconsistent winding")
    if not a["volume"] > 0:
        out.append(f"volume {a['volume']} not positive")
    if a["bodies"] != 1:
        out.append(f"{a['bodies']} bodies")
    if a["bad_edges"]:
        out.append(f"{a['bad_edges']} edges not shared by exactly two faces")
    if a["dup_faces"]:
        out.append(f"{a['dup_faces']} duplicated facets")
    if not a["crossing_depth"] <= policy.CROSSING_LIMIT:
        out.append(f"triangles crossing {a['crossing_depth']:.2g} mm deep")
    return out


# ------------------------------------------------------------------ measuring

def clusters(pts, dist, limit, cell=3.0):
    """Worst deviation per cell of a coarse grid, largest first."""
    best = {}
    for p, d in zip(pts, dist):
        c = tuple((p // cell).astype(int))
        if c not in best or d > best[c][1]:
            best[c] = (p, d)
    return sorted(best.values(), key=lambda t: -t[1])[:limit]


def measure(ref, gen, n_samples=None):
    """Gate 1 measures between two meshes, gen moved so the bounding-box minimum
    corners coincide. Returns (row, spots): row has bbox, vol, samples (the
    number of surface points sampled per direction, policy.N_SAMPLES unless
    given) and, per direction, the sampled mean, p95, p99 and max and the
    all-vertices max (vmax); spots has each direction's points and distances,
    for locating the worst ones."""
    n_samples = policy.N_SAMPLES if n_samples is None else n_samples
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
        row["samples"] = int(len(pts))
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
    """Measure a render against its reference and print the result; returns the row."""
    ref = trimesh.load_mesh(refs.STL_DIR / fname(key))
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


def main():
    args = sys.argv[1:]
    n_clusters = 10
    if "--clusters" in args:
        n_clusters = int(args[args.index("--clusters") + 1])
    keys = [a for a in args if not a.startswith("--") and not a.isdigit()] or list(policy.REFERENCES)
    for k in keys:
        if not (refs.STL_DIR / fname(k)).is_file():
            print(f"[{k}] MISSING reference file: {fname(k)}\n")
            continue
        r = render(OPENSCAD_COMMAND, SCAD, params(k), OUT / f"{k}.stl")
        print(f"[{k}] rendered in {r['seconds']:.1f} s")
        for line in r["problems"]:
            print(f"[{k}] render message: {line}")
        if r["path"] is None:
            print(f"[{k}] RENDER FAILED\n{r['console']}\n")
            continue
        metrics(k, r["path"], n_clusters)
        a = audit(r["path"])
        print(f"[{k}] mesh: {'sound' if clean(a) else '; '.join(unsound_reasons(a))}; "
              f"zero-area triangles in the export: {zero_area_triangles(r['path'])}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
