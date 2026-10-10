"""Regression gate for the shell generator: prove it still reproduces every
reference shell, and that configurations without a reference still export
clean, unchanged geometry. Run it after ANY change to the SCAD.

CHECKS below is the closed list of what the gate checks; docs/verification-method.md
explains each. gate_test.py has a test of every check through run(), and
mutation_test.py disables each check in turn to show that test notices. The
numbers and lists the checks use are in policy.py.

Requires the packages in requirements.txt at the repository root.

Usage:
  python regress.py                    check against analysis/baseline.json
  python regress.py --update-baseline  relock the baseline and rewrite VERIFICATION.md (refused over
                                       any failure, and over any drift, shape change or dropped
                                       coverage unless --accept-drift)
  python regress.py --quick            skip the configurations without a reference (not with
                                       --update-baseline)
  python regress.py --scad PATH        check a different SCAD (selftest.py uses this)
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import compare
import policy
import refs
from compare import clean, unsound_reasons
from export_check import coincident_3mf, merge_faults
from policy import DRIFT, EXPECTED_MESSAGES, LIMITS, REFERENCES, REJECTED, SOUNDNESS, THREEMF_CHECK
from refs import fname

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "baseline.json"
REPORT = compare.ROOT / "VERIFICATION.md"
AUDIT_FLAGS = ("watertight", "winding", "bodies", "bad_edges", "dup_faces", "crossing_depth")

CHECKS = {
    "unit tests": "gate_test.py passes before anything is rendered",
    "locked generator": "the generator is the file the baseline and VERIFICATION.md were made from",
    "generator unchanged": "the generator is the same file at the end of the run as at the start",
    "reference coverage": "every reference in policy.REFERENCES is present, measured and in the baseline, "
                          "and the baseline holds no other",
    "configuration coverage": "every configuration in policy.SOUNDNESS is rendered and in the baseline, "
                              "and the baseline holds no other",
    "render success": "every render writes its file",
    "render messages": "no render, STL or 3MF, prints anything beyond OpenSCAD's normal statistics and "
                       "the expected notes",
    "expected messages": "every note in policy.EXPECTED_MESSAGES appears",
    "hard limits": "every reference meets the Gate 1 limits, measured from policy.N_SAMPLES points per "
                   "direction; a value that is not a number fails",
    "drift": "no reference metric is worse than its locked value by more than policy.DRIFT",
    "mesh soundness": "every STL is watertight, consistently wound, of positive volume and one body, with "
                      "every edge shared by exactly two faces and no duplicated facets",
    "crossings": "no two triangles that share at most one vertex cross deeper than policy.CROSSING_LIMIT",
    "shape lock": "each configuration's vertex digest and volume match the baseline",
    "3MF coincident vertices": "no 3MF export writes two separate vertices at identical coordinates",
    "3MF merges": "merging a 3MF export's vertices within each of policy.MERGE_TOLS leaves every edge "
                  "shared by exactly two triangles",
    "rejected sizes": "each size in policy.REJECTED stops the render with its error and writes no file",
    "relock rules": "a relock is refused from --quick or another SCAD, is never written over a failure, "
                    "and needs --accept-drift for drift, a shape change or dropped coverage",
}


# ------------------------------------------------------------------ decisions

def hard_failures(key, m):
    """A reference metric over its Gate 1 limit, or not a number."""
    return [f"{key}: HARD {field}={m[field]:.4f} > {limit}" for field, limit in LIMITS.items()
            if not m[field] <= limit]


def sample_failures(key, row):
    """A reference measured from another number of surface points than the method requires."""
    n = row.get("samples")
    return [] if n == policy.N_SAMPLES else [f"{key}: HARD measured from {n} samples, not {policy.N_SAMPLES}"]


def drift_failures(key, now, was):
    """A reference metric worse than its locked value by more than the drift tolerance."""
    return [f"{key}: DRIFT {field} {was[field]:.4f} -> {now[field]:.4f}"
            for field, tol in DRIFT.items() if not now[field] - was[field] <= tol]


def message_failures(label, problems, expected, seen):
    """Render messages that should not be there, and expected ones that did not appear."""
    unwanted = [f"{label}: render message: {line}" for line in problems]
    absent = [f"{label}: expected render message missing: {e}" for e in expected if e not in seen]
    return unwanted + absent


def soundness_failures(label, a):
    """An unsound mesh, with what is wrong with it."""
    return [] if clean(a) else [f"{label}: mesh not a clean single shell: {'; '.join(unsound_reasons(a))}"]


def lock_failures(name, a, was):
    """A configuration without a reference that is not in the baseline, or whose
    shape changed since the baseline was locked (was is None when relocking)."""
    if was is None:
        return []
    if was == "absent":
        return [f"soundness/{name}: absent from baseline; relock to cover it"]
    dv = a["volume"] - was["volume"]
    if a["digest"] != was["digest"] or abs(dv) > policy.SOUND_VOL:
        de = max(abs(x - y) for x, y in zip(a["extents"], was["extents"]))
        return [f"soundness/{name}: geometry changed vs baseline (bbox {de:.4f} mm, volume {dv:+.3f} mm3)"]
    return []


def threemf_failures(name, groups, merged):
    """Faults in a 3MF export that a program merging vertices by position would fold."""
    out = []
    if groups:
        out.append(f"soundness/{name}: 3MF has {groups} group(s) of separate vertices at identical coordinates")
    for tol, edges in merged.items():
        if edges:
            out.append(f"soundness/{name}: 3MF merged within {tol:g} mm leaves {edges} edge(s) "
                       f"not shared by exactly two triangles")
    return out


def locked_generator_failures(digest, locked, reported):
    """The baseline or VERIFICATION.md made from another version of the generator."""
    out = []
    if locked != digest:
        out.append(f"generator: the baseline was locked on another version of this file (SHA-256 {locked}); "
                   "relock, which also proves nothing drifted")
    if reported != digest:
        out.append(f"generator: VERIFICATION.md is for another version of this file (SHA-256 {reported}); "
                   "a relock rewrites it")
    return out


def coverage_failures(missing, base, update, quick):
    """References or configurations that a run would otherwise silently skip."""
    out = [f"{k}: reference file missing: {fname(k)}" for k in missing]
    if update:
        return out
    models = base.get("models", {})
    out += [f"{k}: in the baseline but not in policy.REFERENCES" for k in models if k not in REFERENCES]
    out += [f"{k}: absent from baseline; relock to cover it" for k in REFERENCES
            if k not in missing and k not in models]
    if not quick:
        names = [n for n, _ in SOUNDNESS]
        out += [f"soundness/{n}: in the baseline but no longer checked"
                for n in base.get("soundness", {}) if n not in names]
    return out


def relock_changes(current, sound_now, old):
    """What a relock would accept: reference drift, configuration shape changes,
    and references or configurations dropped, against the baseline being replaced."""
    out = [f"{k}: locked reference no longer measured" for k in old.get("models", {}) if k not in current]
    out += [f"soundness/{n}: locked configuration no longer checked" for n in old.get("soundness", {})
            if n not in sound_now]
    for key, m in current.items():
        if key in old.get("models", {}):
            out += drift_failures(key, m, old["models"][key])
    for name, a in sound_now.items():
        if name in old.get("soundness", {}):
            out += lock_failures(name, a, old["soundness"][name])
    return out


# ------------------------------------------------------------------ the report

def report_digest(path=REPORT):
    """The generator digest a VERIFICATION.md names, or None."""
    found = re.search(r"SHA-256 ([0-9A-F]{64})", path.read_text(encoding="utf-8")) if path.is_file() else None
    return found.group(1) if found else None


def report_text(rows, started, finished, digest, renderer):
    """VERIFICATION.md for a relock that passed every check. rows is one
    compare.measure row per reference, with its key and render seconds."""
    lines = [
        "# VERIFICATION - shell Gate 1 mechanical match",
        "",
        "Written by `analysis/regress.py --update-baseline` when it locked `analysis/baseline.json`, in a run "
        f"from {started} to {finished} UTC. The gate writes this file only when every check listed in "
        "`docs/verification-method.md` passes: every reference below meets every limit, every render is a sound "
        "mesh, and no render prints anything beyond OpenSCAD's normal statistics and the expected notes.",
        "",
        f"File verified: `{compare.SCAD.name}`, SHA-256 {digest}, computed with Unix (LF) line endings, as git "
        f"stores the file (`git show <commit>:\"shells/multibin-shell/{compare.SCAD.name}\" | sha256sum`). A plain "
        "`regress.py` run fails if the generator is any other file.",
        "",
        f"Renderer: {renderer}.",
        "",
        "Method: each render is moved so that the two bounding-box minimum corners coincide. Then "
        f"{policy.N_SAMPLES} points sampled on each surface are measured against the other mesh, and every vertex "
        "of each mesh is measured against the other.",
        "",
        "Columns: bbox dmax is the largest difference between the two bounding boxes on any axis; vol delta "
        "is the volume difference as a percentage of the reference's; p99 is the 99th percentile of the "
        "sampled distances, in whichever direction (reference to render, or render to reference) is worse; "
        "sampled max is the largest sampled distance; and all-vertices max is the largest distance from any "
        "vertex of either mesh to the other.",
        "",
        f"Limits: bounding box <= {LIMITS['bbox']} mm per axis, volume <= {LIMITS['vol']} %, p99 <= "
        f"{LIMITS['p99']} mm, and both maxima <= {LIMITS['mx']} mm.",
        "",
        "The sampled columns can differ between runs, p99 in the fourth decimal and the sampled maximum in the "
        "third, because OpenSCAD does not write its triangles in a fixed order, so the sample points differ; the "
        "bounding box, volume and all-vertices columns repeat.",
        "",
        "| model | bbox dmax (mm) | vol delta (%) | p99 (worse dir) | sampled max | all-vertices max | render (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        a, b = r["ref->gen"], r["gen->ref"]
        lines.append(f"| {r['key']} | {r['bbox']:.4f} | {r['vol']:.3f} | {max(a['p99'], b['p99']):.4f} | "
                     f"{max(a['mx'], b['mx']):.4f} | {max(a['vmax'], b['vmax']):.4f} | {r['seconds']:.0f} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ running

class Steps:
    """The gate's contact with the outside world: OpenSCAD, the mesh tools and
    the files it reads and writes. gate_test.py drives run() with stand-ins in
    their place, and tests these real ones separately on small inputs."""

    def unit_tests(self):
        r = subprocess.run([sys.executable, str(HERE / "gate_test.py")], capture_output=True, text=True, cwd=HERE)
        return r.returncode == 0

    def now(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    def digest(self, scad):
        return compare.scad_digest(scad)

    def report_digest(self):
        return report_digest(REPORT)

    def missing_refs(self):
        return [k for k in REFERENCES if not (refs.STL_DIR / fname(k)).is_file()]

    def render(self, scad, name, params, expected):
        return compare.render(compare.OPENSCAD_COMMAND, scad, params, compare.out_for(scad) / name, expected)

    def measure(self, key, path):
        return compare.metrics(key, path, 0)

    def audit(self, path):
        return compare.audit(path)

    def coincident_3mf(self, path):
        return coincident_3mf(path)

    def merge_faults(self, path):
        return {tol: merge_faults(path, tol) for tol in policy.MERGE_TOLS}

    def renderer(self):
        return compare.openscad_version()

    def load_baseline(self):
        return json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else None

    def write_baseline(self, data):
        BASELINE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def write_report(self, text):
        REPORT.write_text(text, encoding="utf-8")


def run(steps, scad, update=False, accept=False, quick=False, alternate=False, log=print):
    """One gate run. Returns (exit status, failures); writes the baseline and
    VERIFICATION.md only when relocking with no failures."""
    if update and alternate:
        log("refusing to lock a baseline from an alternate SCAD")
        return 2, []
    if update and quick:
        log("refusing to lock a baseline without the configurations that have no reference")
        return 2, []
    if not steps.unit_tests():
        log("gate_test.py fails: the gate's decisions cannot be trusted until it passes")
        return 2, []
    old = steps.load_baseline()
    if not update and old is None:
        log("no baseline; run with --update-baseline first")
        return 2, []
    base = {} if update else old
    started = steps.now()
    digest = steps.digest(scad)
    log(f"generator {scad}, SHA-256 {digest}")
    missing = steps.missing_refs()
    present = [k for k in REFERENCES if k not in missing]
    failures = coverage_failures(missing, base, update, quick)
    if not update:
        failures += locked_generator_failures(digest, base.get("scad_digest"), steps.report_digest())
    rows, current, sound_now = [], {}, {}

    log("=" * 78)
    log(f"REFERENCE MATCH ({len(present)} of {len(REFERENCES)} references)")
    log("=" * 78)
    for key in present:
        r = steps.render(scad, f"{key}.stl", compare.params(key), ())
        failures += message_failures(key, r["problems"], (), r["seen"])
        if r["path"] is None:
            failures.append(f"{key}: render failed")
            continue
        row = steps.measure(key, r["path"])
        m, a = compare.summary(row), steps.audit(r["path"])
        rows.append(dict(row, key=key, seconds=r["seconds"]))
        current[key] = dict(m, render_s=round(r["seconds"], 1), **{k: a[k] for k in AUDIT_FLAGS})
        failures += hard_failures(key, m) + sample_failures(key, row) + soundness_failures(key, a)
        was = base.get("models", {}).get(key)
        if was:
            failures += drift_failures(key, m, was)
            log(f"{key:6} " + "  ".join(f"{f}={m[f]:.4f}({m[f] - was[f]:+.4f})" for f in DRIFT))

    if not quick:
        log("=" * 78)
        log("SOUNDNESS (no reference: mesh soundness, and the locked vertex digest and volume)")
        log("=" * 78)
        golden = base.get("soundness", {})
        for name, params in SOUNDNESS:
            expected = EXPECTED_MESSAGES.get(name, ())
            r = steps.render(scad, f"soundness/{name}.stl", params, expected)
            failures += message_failures(f"soundness/{name}", r["problems"], expected, r["seen"])
            if r["path"] is None:
                failures.append(f"soundness/{name}: render failed")
                log(f"  {name:24} RENDER FAILED")
                log(r["console"])
                continue
            a = steps.audit(r["path"])
            sound_now[name] = a
            found = soundness_failures(f"soundness/{name}", a)
            found += lock_failures(name, a, None if update else golden.get(name, "absent"))
            failures += found
            state = "ok" if not found else "CHANGED" if clean(a) else "BROKEN"
            log(f"  {name:24} {state:7} bbox={a['extents']} vol={a['volume']}")
            if name in THREEMF_CHECK:
                r = steps.render(scad, f"soundness/{name}.3mf", params, expected)
                failures += message_failures(f"soundness/{name} 3MF", r["problems"], expected, r["seen"])
                if r["path"] is None:
                    failures.append(f"soundness/{name}: 3MF render failed")
                    continue
                groups, merged = steps.coincident_3mf(r["path"]), steps.merge_faults(r["path"])
                failures += threemf_failures(name, groups, merged)
                log(f"  {name:24} 3MF     coincident vertex groups: {groups}; edges broken by a merge: {merged}")
        for name, params, error in REJECTED:
            r = steps.render(scad, f"soundness/{name}.stl", params, (error,))
            rejected = r["path"] is None and error in r["seen"]
            if not rejected:
                failures.append(f"rejected/{name}: expected the render to stop with: {error}")
            log(f"  {name:24} {'rejected' if rejected else 'NOT REJECTED'}")

    # every render reads the file afresh, so an edit during the run would mix two versions
    if steps.digest(scad) != digest:
        failures.append("generator: the file changed during the run; run the gate again")

    if update:
        # a relock must not quietly accept a regression: list what it would
        # change, and require --accept-drift once the change is known to be intended
        changes = relock_changes(current, sound_now, old or {})
        if changes and not accept:
            failures += changes + ["relock would accept the changes above; rerun with --accept-drift if they are intended"]
        elif changes:
            log(f"accepting {len(changes)} change(s) against the old baseline:")
            for f in changes:
                log(f"  - {f}")
        # a baseline locked over a failure would hide it from every later run
        if failures:
            log(f"NOT RELOCKED - {len(failures)} problem(s):")
            for f in failures:
                log(f"  - {f}")
            return 1, failures
        steps.write_baseline(dict(models=current, soundness=sound_now, scad_digest=digest))
        steps.write_report(report_text(rows, started, steps.now(), digest, steps.renderer()))
        log(f"baseline relocked and VERIFICATION.md written: {len(current)} reference(s), "
            f"{len(sound_now)} soundness config(s)")
        return 0, failures

    log("=" * 78)
    if failures:
        log(f"FAIL - {len(failures)} problem(s):")
        for f in failures:
            log(f"  - {f}")
        return 1, failures
    log(f"PASS - all {len(REFERENCES)} references match"
        + (" (configurations without a reference skipped)" if quick
           else ", and every soundness configuration is sound and unchanged") + ".")
    return 0, failures


def main():
    scad, alternate = compare.SCAD, "--scad" in sys.argv
    if alternate:
        scad = Path(sys.argv[sys.argv.index("--scad") + 1]).resolve()
        print(f"*** checking ALTERNATE SCAD: {scad.name} ***")
    code, _ = run(Steps(), scad, update="--update-baseline" in sys.argv, accept="--accept-drift" in sys.argv,
                  quick="--quick" in sys.argv, alternate=alternate)
    return code


if __name__ == "__main__":
    sys.exit(main())
