"""Regression gate for the shell generator: prove it still reproduces every
available reference shell, and that configurations without a reference still
export clean, unchanged geometry.

Run after ANY change to the SCAD. Three layers of checking:

  HARD       the Gate 1 limits in docs/verification-method.md.
  DRIFT      no metric may get worse than the locked baseline by more than a
             small tolerance.
  SOUNDNESS  configurations with no reference: mesh topology (watertight, one
             body, every edge shared by exactly two faces, no duplicated
             facets) and bounding box and volume against the baseline.

Requires the packages in requirements.txt at the repository root.

Usage:
  python regress.py                    check against analysis/baseline.json
  python regress.py --update-baseline  relock the baseline to current output
  python regress.py --quick            skip the soundness section
  python regress.py --scad PATH        check a different SCAD (self-test the gate)
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

import compare
from compare import OPENSCAD, generate, metrics, out_for
from refs import STL_DIR, SIZES, WALLS, fname

BASELINE = Path(__file__).parent / "baseline.json"
HARD = dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2)
DRIFT = dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002)

# Every reference shell this gate expects; missing files are reported, never
# skipped silently.
EXPECTED = ["T111", "T212", "T313", "T3135", "T323", "T1215",
            "O111", "O212", "O323", "O1215",
            "S111", "S212", "S323", "S1215"]

W = '"{}"'
SOUNDNESS = [
    ("half_w_1.5x1x1",     dict(width_lu=1.5, height_lu=1, depth_lu=1)),
    ("half_h_2x1.5x2",     dict(width_lu=2, height_lu=1.5, depth_lu=2)),
    ("half_both_2.5x1.5x1.5", dict(width_lu=2.5, height_lu=1.5, depth_lu=1.5)),
    ("thin_1.5x0.5x1",     dict(width_lu=1.5, height_lu=0.5, depth_lu=1)),
    ("deep_1x1x4",         dict(width_lu=1, height_lu=1, depth_lu=4)),
    ("wide_4x1x1",         dict(width_lu=4, height_lu=1, depth_lu=1)),
    ("mixed_walls_2x2x1",  dict(width_lu=2, height_lu=2, depth_lu=1,
                                front_wall=W.format("topped"), back_wall=W.format("topless"),
                                left_wall=W.format("simple"), right_wall=W.format("topped"))),
    ("simple_2x1x2",       dict(width_lu=2, height_lu=1, depth_lu=2,
                                front_wall=W.format("simple"), back_wall=W.format("simple"),
                                left_wall=W.format("simple"), right_wall=W.format("simple"))),
    # rim grooves crossing seams beside a half cell, under a partial top band
    ("topless_half_2.5x1.5x1.5", dict(width_lu=2.5, height_lu=1.5, depth_lu=1.5,
                                front_wall=W.format("topless"), back_wall=W.format("topless"),
                                left_wall=W.format("topless"), right_wall=W.format("topless"))),
    # the short partial-band seam groove of simple walls beside a half cell
    ("simple_half_1.5x2x2.5", dict(width_lu=1.5, height_lu=2, depth_lu=2.5,
                                front_wall=W.format("simple"), back_wall=W.format("simple"),
                                left_wall=W.format("simple"), right_wall=W.format("simple"))),
]


def render(name, params, scad):
    d = out_for(scad) / "soundness"
    d.mkdir(parents=True, exist_ok=True)
    stl = d / f"{name}.stl"
    if stl.exists():
        stl.unlink()
    args = [OPENSCAD, "-o", str(stl), str(scad)]
    for k, v in params.items():
        args += ["-D", f"{k}={v}"]
    r = subprocess.run(args, capture_output=True, text=True, timeout=3600)
    return (stl, None) if stl.exists() else (None, r.stderr[-2000:])


def audit(stl):
    m = trimesh.load_mesh(stl)
    m.merge_vertices()
    _, c = np.unique(m.edges_sorted, axis=0, return_counts=True)
    _, counts = np.unique(np.sort(m.faces, axis=1), axis=0, return_counts=True)
    return dict(watertight=bool(m.is_watertight), bodies=int(m.body_count),
                bad_edges=int((c != 2).sum()), dup_faces=int((counts > 1).sum()),
                extents=[round(float(v), 4) for v in m.extents], volume=round(float(m.volume), 3))


def clean(a):
    return a["watertight"] and a["bodies"] == 1 and a["bad_edges"] == 0 and a["dup_faces"] == 0


def collapse(row):
    a, b = row["ref->gen"], row["gen->ref"]
    return dict(bbox=float(row["bbox"]), vol=float(row["vol"]),
                p99=float(max(a["p99"], b["p99"])),
                mx=float(max(a["mx"], b["mx"], a["vmax"], b["vmax"])))


def main():
    update = "--update-baseline" in sys.argv
    quick = "--quick" in sys.argv
    scad = compare.SCAD
    if "--scad" in sys.argv:
        scad = Path(sys.argv[sys.argv.index("--scad") + 1]).resolve()
        if update:
            print("refusing to lock a baseline from an alternate SCAD")
            return 2
        print(f"*** checking ALTERNATE SCAD: {scad.name} ***")
    current, failures, sound_now = {}, [], {}

    missing = [k for k in EXPECTED if not (STL_DIR / fname(k)).is_file()]
    present = [k for k in EXPECTED if k not in missing]
    if missing:
        print("!" * 78)
        print(f"MISSING REFERENCE FILES ({len(missing)} of {len(EXPECTED)}): the gate runs at reduced coverage.")
        for k in missing:
            print(f"  {k}: {fname(k)}")
        print("!" * 78)

    print("=" * 78)
    print(f"REFERENCE MATCH ({len(present)} of {len(EXPECTED)} references)")
    print("=" * 78)
    for key in present:
        p, secs = generate(key, scad)
        if p is None:
            failures.append(f"{key}: render failed")
            continue
        m = collapse(metrics(key, p, 0))
        a = audit(p)
        m.update(dict(render_s=round(secs, 1), **{k: a[k] for k in ("watertight", "bodies", "bad_edges", "dup_faces")}))
        current[key] = m
        for field, limit in HARD.items():
            if m[field] > limit:
                failures.append(f"{key}: HARD {field}={m[field]:.4f} > {limit}")
        if not clean(a):
            failures.append(f"{key}: mesh not a clean single shell: {a}")

    base_raw = {} if update or not BASELINE.exists() else json.loads(BASELINE.read_text(encoding="utf-8"))
    if not update and not BASELINE.exists():
        print("no baseline; run with --update-baseline first")
        return 2
    base = base_raw.get("models", {})
    for k in base_raw.get("missing_at_lock", []):
        if k in current:
            failures.append(f"{k}: reference has appeared since the baseline was locked; relock to cover it")
    if not update:
        print("=" * 78)
        print("DRIFT vs BASELINE")
        print("=" * 78)
        for key in present:
            if key not in current:
                continue
            if key not in base:
                failures.append(f"{key}: absent from baseline")
                continue
            cells = []
            for field in ("bbox", "vol", "p99", "mx"):
                now, was = current[key][field], base[key][field]
                if now - was > DRIFT[field]:
                    failures.append(f"{key}: DRIFT {field} {was:.4f} -> {now:.4f}")
                cells.append(f"{field}={now:.4f}({now - was:+.4f})")
            print(f"{key:6} " + "  ".join(cells))

    if not quick:
        print("=" * 78)
        print("SOUNDNESS (no reference; topology + locked bounding box and volume)")
        print("=" * 78)
        golden = base_raw.get("soundness", {})
        for name, params in SOUNDNESS:
            stl, err = render(name, params, scad)
            if stl is None:
                failures.append(f"soundness/{name}: render failed")
                print(f"  {name:24} RENDER FAILED\n{err}")
                continue
            a = audit(stl)
            sound_now[name] = a
            note = ""
            if name in golden:
                was = golden[name]
                de = max(abs(x - y) for x, y in zip(a["extents"], was["extents"]))
                dv = abs(a["volume"] - was["volume"])
                if de > 0.001 or dv > 0.5:
                    note = f"  GEOMETRY CHANGED (bbox {de:.4f}, vol {dv:.3f})"
                    failures.append(f"soundness/{name}: geometry moved vs baseline (bbox {de:.4f} mm, volume {dv:.3f} mm3)")
            elif not update:
                note = "  (not in baseline)"
            print(f"  {name:24} {'ok' if clean(a) else 'BROKEN'} bbox={a['extents']} vol={a['volume']}{note}")
            if not clean(a):
                failures.append(f"soundness/{name}: {a}")

    if update:
        BASELINE.write_text(json.dumps(dict(models=current, missing_at_lock=missing, soundness=sound_now),
                                       indent=2), encoding="utf-8")
        print(f"baseline relocked: {len(current)} reference(s), {len(sound_now)} soundness config(s)")
        return 1 if failures else 0

    print("=" * 78)
    if failures:
        print(f"FAIL - {len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASS - {len(present)} of {len(EXPECTED)} references match"
          + (f" ({len(missing)} missing)" if missing else "")
          + ("" if quick else ", and every soundness configuration is clean and unchanged") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
