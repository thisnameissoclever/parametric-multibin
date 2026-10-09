"""Regression gate for the shell generator: prove it still reproduces every
reference shell, and that configurations without a reference still export
clean, unchanged geometry.

Run after ANY change to the SCAD. Three layers of checking:

  HARD       the Gate 1 limits in docs/verification-method.md.
  DRIFT      no reference metric may get worse than the locked baseline by more
             than a small tolerance.
  SOUNDNESS  configurations with no reference: mesh soundness (see
             compare.audit), and a digest of their vertices and their volume
             against the baseline, so any change to their shape fails until it
             is relocked.

Every reference in refs.EXPECTED and every configuration in the baseline must
be checked on every full run; a missing reference file or a dropped
configuration is a failure, never a skip. Any render message other than an
expected one is a failure, and so is an expected one that does not appear. The
decisions are the *_failures functions below, which gate_test.py tests at their
limits.

Requires the packages in requirements.txt at the repository root.

Usage:
  python regress.py                    check against analysis/baseline.json
  python regress.py --update-baseline  relock the baseline (refused over any failure, and
                                       over any drift or shape change unless --accept-drift)
  python regress.py --quick            skip the soundness section (not with --update-baseline)
  python regress.py --scad PATH        check a different SCAD (selftest.py uses this)
"""

import json
import subprocess
import sys
from pathlib import Path

import compare
from compare import EXPORT_FORMAT, LIMITS, OPENSCAD, audit, clean, generate, metrics, out_for, render_problems, summary
from export_check import coincident_3mf
from refs import EXPECTED, STL_DIR, fname

BASELINE = Path(__file__).parent / "baseline.json"
HARD = LIMITS
DRIFT = dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002)
# repeat renders give the same vertices and the same volume to 0.001 mm3
SOUND_VOL = 0.01

W = '"{}"'
SOUNDNESS = [
    ("half_w_1.5x1x1",     dict(width_lu=1.5, height_lu=1, depth_lu=1)),
    # typed off the half-LU step: rounds up to 1.5 x 1.5 x 1
    ("offstep_1.3x1.1x0.8", dict(width_lu=1.3, height_lu=1.1, depth_lu=0.8)),
    ("half_h_2x1.5x2",     dict(width_lu=2, height_lu=1.5, depth_lu=2)),
    ("half_both_2.5x1.5x1.5", dict(width_lu=2.5, height_lu=1.5, depth_lu=1.5)),
    ("thin_1.5x0.5x1",     dict(width_lu=1.5, height_lu=0.5, depth_lu=1)),
    ("deep_1x1x4",         dict(width_lu=1, height_lu=1, depth_lu=4)),
    ("wide_4x1x1",         dict(width_lu=4, height_lu=1, depth_lu=1)),
    # pads far from the origin: some positions once exported broken pocket slits
    ("long_1x7x1",         dict(width_lu=1, height_lu=7, depth_lu=1)),
    ("wide_12x1x1",        dict(width_lu=12, height_lu=1, depth_lu=1)),
    ("long_mixed_2.5x7.5x1.5", dict(width_lu=2.5, height_lu=7.5, depth_lu=1.5,
                                front_wall=W.format("topped"), back_wall=W.format("topped"),
                                left_wall=W.format("topless"), right_wall=W.format("simple"))),
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

# configurations also exported as 3MF, which keeps separate vertices apart by
# index: none may write two separate vertices at identical coordinates
THREEMF_CHECK = ["thin_1.5x0.5x1", "half_both_2.5x1.5x1.5"]

# console texts a configuration must print, and may print without failing
EXPECTED_MESSAGES = {
    "offstep_1.3x1.1x0.8": ["NOTE: width_lu = 1.3 is not on the half-LU grid, so it is rounded up; using 1.5.",
                            "NOTE: height_lu = 1.1 is not on the half-LU grid, so it is rounded up; using 1.5.",
                            "NOTE: depth_lu = 0.8 is below the minimum; using 1."],
    "thin_1.5x0.5x1": ["NOTE: left_wall = topped has no effect: the side is shorter than 1 LU, so it has no rail channel.",
                       "NOTE: right_wall = topped has no effect: the side is shorter than 1 LU, so it has no rail channel."],
}


# ------------------------------------------------------------------ decisions

def hard_failures(key, m):
    """A reference metric over its Gate 1 limit."""
    return [f"{key}: HARD {field}={m[field]:.4f} > {limit}" for field, limit in HARD.items() if m[field] > limit]


def drift_failures(key, now, was):
    """A reference metric worse than its locked value by more than the drift tolerance."""
    return [f"{key}: DRIFT {field} {was[field]:.4f} -> {now[field]:.4f}"
            for field, tol in DRIFT.items() if now[field] - was[field] > tol]


def message_failures(label, problems, expected, seen):
    """Render messages that should not be there, and expected ones that did not appear."""
    return ([f"{label}: render message: {line}" for line in problems]
            + [f"{label}: expected render message missing: {e}" for e in expected if e not in seen])


def sound_failures(name, a, was):
    """A configuration without a reference that is unsound, not in the baseline,
    or changed since the baseline was locked (was is None when relocking)."""
    out = [] if clean(a) else [f"soundness/{name}: mesh not a clean single shell: {a}"]
    if was is None:
        return out
    if was == "absent":
        return out + [f"soundness/{name}: absent from baseline; relock to cover it"]
    dv = a["volume"] - was["volume"]
    if a["digest"] != was["digest"] or abs(dv) > SOUND_VOL:
        de = max(abs(x - y) for x, y in zip(a["extents"], was["extents"]))
        out.append(f"soundness/{name}: geometry changed vs baseline (bbox {de:.4f} mm, volume {dv:+.3f} mm3)")
    return out


def relock_changes(current, sound_now, old):
    """What a relock would accept: reference drift and configuration shape
    changes against the baseline being replaced."""
    out = []
    for key, m in current.items():
        if key in old.get("models", {}):
            out += drift_failures(key, m, old["models"][key])
    for name, a in sound_now.items():
        if name in old.get("soundness", {}):
            out += [f for f in sound_failures(name, a, old["soundness"][name]) if "geometry changed" in f]
    return out


def coverage_failures(missing, base, update, quick, sound_names):
    """References or configurations that a run would otherwise silently skip."""
    out = [f"{k}: reference file missing: {fname(k)}" for k in missing]
    if update:
        return out
    models = base.get("models", {})
    out += [f"{k}: in the baseline but not in refs.EXPECTED" for k in models if k not in EXPECTED]
    out += [f"{k}: absent from baseline; relock to cover it" for k in EXPECTED if k not in missing and k not in models]
    if not quick:
        out += [f"soundness/{n}: in the baseline but no longer checked"
                for n in base.get("soundness", {}) if n not in sound_names]
    return out


# ------------------------------------------------------------------ running

def render(name, params, scad, expected=(), fmt="stl"):
    """Render a configuration; returns (path or None, error text, problems, expected texts seen)."""
    d = out_for(scad) / "soundness"
    d.mkdir(parents=True, exist_ok=True)
    stl = d / f"{name}.{fmt}"
    if stl.exists():
        stl.unlink()
    args = [OPENSCAD, "-o", str(stl), *(EXPORT_FORMAT if fmt == "stl" else []), str(scad)]
    for k, v in params.items():
        args += ["-D", f"{k}={v}"]
    r = subprocess.run(args, capture_output=True, text=True, timeout=3600)
    problems = render_problems(r.stderr, expected)
    seen = [e for e in expected if e in r.stderr]
    return (stl if stl.exists() else None), r.stderr[-2000:], problems, seen


def main():
    update = "--update-baseline" in sys.argv
    accept = "--accept-drift" in sys.argv
    quick = "--quick" in sys.argv
    scad = compare.SCAD
    if "--scad" in sys.argv:
        scad = Path(sys.argv[sys.argv.index("--scad") + 1]).resolve()
        if update:
            print("refusing to lock a baseline from an alternate SCAD")
            return 2
        print(f"*** checking ALTERNATE SCAD: {scad.name} ***")
    if update and quick:
        print("refusing to lock a baseline without the soundness section")
        return 2
    if not update and not BASELINE.exists():
        print("no baseline; run with --update-baseline first")
        return 2
    base = {} if update else json.loads(BASELINE.read_text(encoding="utf-8"))
    missing = [k for k in EXPECTED if not (STL_DIR / fname(k)).is_file()]
    present = [k for k in EXPECTED if k not in missing]
    failures = coverage_failures(missing, base, update, quick, [n for n, _ in SOUNDNESS])
    current, sound_now = {}, {}

    print("=" * 78)
    print(f"REFERENCE MATCH ({len(present)} of {len(EXPECTED)} references)")
    print("=" * 78)
    for key in present:
        p, secs, problems = generate(key, scad)
        failures += message_failures(key, problems, (), ())
        if p is None:
            failures.append(f"{key}: render failed")
            continue
        m = summary(metrics(key, p, 0))
        a = audit(p)
        m.update(render_s=round(secs, 1),
                 **{k: a[k] for k in ("watertight", "winding", "bodies", "bad_edges", "dup_faces", "crossing_depth")})
        current[key] = m
        failures += hard_failures(key, m)
        if not clean(a):
            failures.append(f"{key}: mesh not a clean single shell: {a}")
        was = base.get("models", {}).get(key)
        if was:
            failures += drift_failures(key, m, was)
            print(f"{key:6} " + "  ".join(f"{f}={m[f]:.4f}({m[f] - was[f]:+.4f})" for f in DRIFT))

    if not quick:
        print("=" * 78)
        print("SOUNDNESS (no reference: mesh soundness and the locked geometry digest)")
        print("=" * 78)
        golden = base.get("soundness", {})
        for name, params in SOUNDNESS:
            expected = EXPECTED_MESSAGES.get(name, [])
            stl, err, problems, seen = render(name, params, scad, expected)
            failures += message_failures(f"soundness/{name}", problems, expected, seen)
            if stl is None:
                failures.append(f"soundness/{name}: render failed")
                print(f"  {name:24} RENDER FAILED\n{err}")
                continue
            a = audit(stl)
            sound_now[name] = a
            found = sound_failures(name, a, None if update else golden.get(name, "absent"))
            failures += found
            state = "ok" if not found else "CHANGED" if clean(a) else "BROKEN"
            print(f"  {name:24} {state:7} bbox={a['extents']} vol={a['volume']}")
            if name in THREEMF_CHECK:
                tmf, err, problems, seen = render(name, params, scad, expected, fmt="3mf")
                failures += message_failures(f"soundness/{name} 3MF", problems, expected, seen)
                groups = coincident_3mf(tmf) if tmf else None
                if groups is None:
                    failures.append(f"soundness/{name}: 3MF render failed")
                elif groups:
                    failures.append(f"soundness/{name}: 3MF has {groups} group(s) of separate vertices at identical coordinates")
                print(f"  {name:24} 3MF     coincident vertex groups: {groups}")

    if update:
        # a relock must not quietly accept a regression: list what it would
        # change, and require --accept-drift once the change is known to be intended
        old = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
        changes = relock_changes(current, sound_now, old)
        if changes and not accept:
            failures += changes + ["relock would accept the changes above; rerun with --accept-drift if they are intended"]
        elif changes:
            print(f"accepting {len(changes)} change(s) against the old baseline:")
            for f in changes:
                print(f"  - {f}")
        # a baseline locked over a failure would hide it from every later run
        if failures:
            print(f"NOT RELOCKED - {len(failures)} problem(s):")
            for f in failures:
                print(f"  - {f}")
            return 1
        BASELINE.write_text(json.dumps(dict(models=current, soundness=sound_now), indent=2), encoding="utf-8")
        print(f"baseline relocked: {len(current)} reference(s), {len(sound_now)} soundness config(s)")
        return 0

    print("=" * 78)
    if failures:
        print(f"FAIL - {len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASS - all {len(EXPECTED)} references match"
          + (" (soundness section skipped)" if quick
             else ", and every soundness configuration is sound and unchanged") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
