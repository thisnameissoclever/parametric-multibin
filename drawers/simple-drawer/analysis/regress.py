"""Regression gate: prove the current SCAD still reproduces all nine originals.

Run after ANY change to the SCAD. Two layers of checking:

  HARD  - the original Gate 1 thresholds. Absolute, never allowed to break.
  DRIFT - no metric may get worse than the locked baseline by more than a
          small tolerance. Catches gradual degradation that stays under the
          hard thresholds.

A third section renders configurations that exercise parameters having no
reference model. Those are checked two ways: mesh topology (watertight, one
body, every edge shared by exactly two faces, no duplicated facets), and their
bounding box and volume against values locked in the baseline. The second check
exists because a feature fusing into the wrong neighbour leaves the topology
perfectly valid and would otherwise pass unnoticed.

Requires the packages in requirements.txt at the repository root.

Usage:
  python regress.py                    check against analysis/baseline.json
  python regress.py --update-baseline  relock the baseline to current output
  python regress.py --quick            skip the no-reference soundness sweep
  python regress.py --scad PATH        check a different SCAD (self-test the gate)
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).parent))
import compare
from compare import FILES, CFG, OUT, SCAD, OPENSCAD, generate, metrics

ROOT = Path(__file__).parent.parent
BASELINE = Path(__file__).parent / "baseline.json"

# Gate 1 thresholds, from the original completion contract.
HARD = dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2)

# A metric may not exceed its baseline by more than this. Distances are in mm;
# 0.002 is a two-hundredth of a 0.4 mm nozzle, far below any real geometry
# change, but wide enough to absorb triangulation shuffling from refactors.
DRIFT = dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002)

# Configurations with no reference model. Checked for mesh soundness only.
# Extend this as parameters are added; every new parameter needs at least one
# row here at a non-default value.
SOUNDNESS = [
    ("plain_1x1x1",      dict(width_lu=1, height_lu=1, depth_lu=1)),
    ("half_w_1.5",       dict(width_lu=1.5, height_lu=1, depth_lu=1)),
    ("half_h_1.5",       dict(width_lu=2, height_lu=1.5, depth_lu=2)),
    ("tall_4LU",         dict(width_lu=2, height_lu=4, depth_lu=2)),
    ("short_0.5LU",      dict(width_lu=2, height_lu=0.5, depth_lu=2)),
    ("grid_4x3",         dict(width_lu=3, height_lu=2, depth_lu=3,
                              width_sections=4, depth_sections=3)),
    ("low_dividers",     dict(width_lu=3, height_lu=2, depth_lu=2,
                              width_sections=3, divider_height_lu=1)),
    ("magnet_divided",   dict(width_lu=3, height_lu=2, depth_lu=2,
                              width_sections=2, magnet="true")),
    # Two rows that reproduce real defects caught during the original review
    # rounds, kept so those exact failures can never come back unnoticed:
    # a tall narrow drawer (corner-brace tangency left the mesh unclosed) and
    # an off-grid height (a millimetre-based feature gate built a label frame
    # that fused into the pull lip).
    ("tall_narrow_1x3x1", dict(width_lu=1, height_lu=3, depth_lu=1)),
    ("offgrid_h_0.75",    dict(width_lu=2, height_lu=0.75, depth_lu=2,
                               label='"large"', magnet="true")),
]


def render(name, params, subdir="soundness"):
    d = OUT / subdir
    d.mkdir(parents=True, exist_ok=True)
    stl = d / f"{name}.stl"
    args = [OPENSCAD, "-o", str(stl), str(compare.SCAD)]
    for k, v in params.items():
        args += ["-D", f"{k}={v}"]
    r = subprocess.run(args, capture_output=True, text=True, timeout=1800)
    if not stl.exists():
        return None, r.stderr[-2000:]
    return stl, None


def audit(stl):
    m = trimesh.load_mesh(stl)
    m.merge_vertices()
    _, c = np.unique(m.edges_sorted, axis=0, return_counts=True)
    tri = np.sort(m.faces, axis=1)
    _, counts = np.unique(tri, axis=0, return_counts=True)
    return dict(watertight=bool(m.is_watertight), bodies=int(m.body_count),
                bad_edges=int((c != 2).sum()), dup_faces=int((counts > 1).sum()))


def shape(stl):
    """Bounding box and volume, so a geometry change on a configuration with no
    reference model is still visible. Mesh soundness alone cannot see it: a
    feature fusing into the wrong neighbour leaves the topology perfectly valid."""
    m = trimesh.load_mesh(stl)
    return dict(extents=[round(float(v), 4) for v in m.extents],
                volume=round(float(m.volume), 3))


def collapse(row):
    """Reduce a compare.metrics() row to the worse of the two directions."""
    a, b = row["ref->gen"], row["gen->ref"]
    return dict(
        bbox=float(row["bbox"]),
        vol=float(row["vol"]),
        p99=float(max(a["p99"], b["p99"])),
        mx=float(max(a["mx"], b["mx"], a["vmax"], b["vmax"])),
    )


def main():
    update = "--update-baseline" in sys.argv
    quick = "--quick" in sys.argv
    if "--scad" in sys.argv:
        alt = Path(sys.argv[sys.argv.index("--scad") + 1]).resolve()
        if not alt.is_file():
            print(f"no such SCAD: {alt}")
            return 2
        compare.SCAD = alt
        globals()["SCAD"] = alt
        print(f"*** checking ALTERNATE SCAD: {alt.name} ***")
        print()
        if update:
            print("refusing to lock a baseline from an alternate SCAD")
            return 2
    OUT.mkdir(exist_ok=True)

    current, failures, sound_now = {}, [], {}

    # A reference STL that has gone missing must never quietly shrink the gate.
    from compare import STL_DIR
    missing = [k for k, f in FILES.items() if not (STL_DIR / f).is_file()]
    present = [k for k in FILES if k not in missing]
    if missing:
        print("!" * 78)
        print(f"MISSING REFERENCE FILES ({len(missing)} of {len(FILES)}) - the gate is "
              f"running at reduced coverage.")
        for k in missing:
            print(f"  {k}: {FILES[k]}")
        print("Restore these and re-lock the baseline to regain full coverage.")
        print("!" * 78)
        print()

    print("=" * 78)
    print(f"REFERENCE MATCH  ({len(present)} of {len(FILES)} originals, "
          f"all new parameters at their defaults)")
    print("=" * 78)
    for key in present:
        p = generate(key)
        if p is None:
            failures.append(f"{key}: render failed")
            continue
        m = collapse(metrics(key, p))
        s = audit(p)
        m.update(s)
        current[key] = m
        for field, limit in HARD.items():
            if m[field] > limit:
                failures.append(f"{key}: HARD {field}={m[field]:.4f} > {limit}")
        if not (s["watertight"] and s["bodies"] == 1
                and s["bad_edges"] == 0 and s["dup_faces"] == 0):
            failures.append(f"{key}: mesh not a clean single shell: {s}")
        print()

    if not update and not BASELINE.exists():
        print("no baseline; run with --update-baseline first")
        return 2

    base_raw = ({} if update
                else json.loads(BASELINE.read_text(encoding="utf-8")))
    base = base_raw.get("models", base_raw)
    for k in base_raw.get("missing_at_lock", []):
        if k in current:
            failures.append(
                f"{k}: reference has reappeared since the baseline was locked; "
                f"re-run with --update-baseline to bring it under the drift gate")

    if update:
        print("(relocking: drift comparison skipped)")
        print()
    else:
        print("=" * 78)
        print("DRIFT vs BASELINE")
        print("=" * 78)
        print(f"{'model':8} {'bbox':>18} {'vol %':>18} {'p99':>18} {'max':>18}")
        for key in present:
            if key not in current:
                continue
            if key not in base:
                failures.append(f"{key}: absent from baseline")
                continue
            cells = []
            for field in ("bbox", "vol", "p99", "mx"):
                now, was = current[key][field], base[key][field]
                delta = now - was
                flag = " !" if delta > DRIFT[field] else ""
                if flag:
                    failures.append(
                        f"{key}: DRIFT {field} {was:.4f} -> {now:.4f} "
                        f"(+{delta:.4f} > {DRIFT[field]})")
                cells.append(f"{now:.4f}({delta:+.4f}){flag:>2}")
            print(f"{key:8} " + " ".join(f"{c:>18}" for c in cells))

    if not quick:
        print()
        print("=" * 78)
        print("SOUNDNESS  (configurations with no reference; topology + golden geometry)")
        print("=" * 78)
        golden = base_raw.get("soundness", {})
        for name, params in SOUNDNESS:
            stl, err = render(name, params)
            if stl is None:
                failures.append(f"soundness/{name}: render failed")
                print(f"  {name:18} RENDER FAILED")
                print(err)
                continue
            s = audit(stl)
            g = shape(stl)
            sound_now[name] = dict(s, **g)
            ok = (s["watertight"] and s["bodies"] == 1
                  and s["bad_edges"] == 0 and s["dup_faces"] == 0)
            note = ""
            if name in golden:
                was = golden[name]
                de = max(abs(a - b) for a, b in zip(g["extents"], was["extents"]))
                dv = abs(g["volume"] - was["volume"])
                if de > 0.001 or dv > 0.5:
                    note = f"  GEOMETRY CHANGED (bbox {de:.4f} mm, vol {dv:.3f} mm3)"
                    failures.append(
                        f"soundness/{name}: geometry moved vs baseline "
                        f"(bbox delta {de:.4f} mm, volume delta {dv:.3f} mm3); "
                        f"if intended, re-lock with --update-baseline")
            else:
                note = "  (new, not yet in baseline)"
            print(f"  {name:18} {'ok' if ok else 'BROKEN'}  "
                  f"bbox={g['extents']} vol={g['volume']}{note}")
            if not ok:
                failures.append(f"soundness/{name}: {s}")

    if update:
        payload = dict(models=current, missing_at_lock=missing,
                       soundness=sound_now)
        BASELINE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print()
        print(f"baseline relocked: {len(current)} reference model(s), "
              f"{len(sound_now)} soundness config(s) -> {BASELINE}")
        if missing:
            print(f"NOTE: {len(missing)} reference(s) absent at lock time: "
                  f"{', '.join(missing)}")
        if quick:
            print("NOTE: --quick was used, so no soundness values were locked.")
        return 1 if failures else 0

    print()
    print("=" * 78)
    if failures:
        print(f"FAIL - {len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    scope = (f"all {len(present)} available originals"
             if not missing else
             f"{len(present)} of {len(FILES)} originals "
             f"({len(missing)} reference file(s) missing)")
    print(f"PASS - {scope} still match, and every soundness configuration "
          f"exports a clean single shell.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
