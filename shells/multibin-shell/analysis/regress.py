"""Regression gate for the shell generator. It renders the generator for every
reference shell, every configuration and every rejected size the policy lists,
and compares the results with the references, with fixed limits and with a
locked baseline. Run it after ANY change to the SCAD.

CHECKS below is the closed list of what the gate compares; docs/verification-method.md
has one row for each. The limits and lists are in policy.py.

Requires the packages in requirements.txt at the repository root.

Usage:
  python regress.py                    check against analysis/baseline.json
  python regress.py --update-baseline  relock the baseline and rewrite VERIFICATION.md (refused over
                                       any failure, and, unless --accept-drift, over any drift,
                                       shape change or dropped coverage against the baseline it
                                       replaces)
  python regress.py --scad PATH        check a different SCAD (selftest.py uses this)
"""

import json
import os
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
UNIT_TESTS = HERE / "gate_test.py"
# set in the environment of the unit tests while the gate runs them
NESTED = "MULTIBIN_SHELL_GATE_UNIT_TESTS"
# what the baseline keeps of a reference render's audit, besides its metrics
AUDIT_KEPT = ("watertight", "winding", "bodies", "bad_edges", "dup_faces", "crossing_depth",
              "digest", "volume", "extents")

CHECKS = {
    "unit tests": "gate_test.py exits 0 before anything is rendered",
    "locked generator": "in a plain run, the generator's digest equals the one in the baseline and the one in "
                        "VERIFICATION.md",
    "generator unchanged": "the generator's digest at the end of the run equals its digest at the start",
    "reference coverage": "every reference in policy.REFERENCES has its file, and in a plain run the references "
                          "in the baseline are exactly that list",
    "configuration coverage": "in a plain run, the configurations in the baseline are exactly policy.SOUNDNESS",
    "render success": "every render of a reference or a configuration writes its file",
    "console output": "each such render's standard error is exactly its expected notes followed by "
                      "policy.CONSOLE_STATISTICS, and its standard output is empty",
    "hard limits": "each reference's four measures are within policy.LIMITS, with policy.N_SAMPLES points "
                   "sampled in each direction",
    "drift": "in a plain run, each reference's four measures are no more than policy.DRIFT above the baseline's",
    "mesh soundness": "each STL's audit: watertight, consistently wound, positive volume, one body, every "
                      "edge on two faces, no duplicated facet",
    "crossings": "each STL's deepest crossing between two triangles that share at most one vertex is within "
                 "policy.CROSSING_LIMIT",
    "shape lock": "in a plain run, each STL's vertex digest equals the baseline's and its volume is within "
                  "policy.SOUND_VOL of the baseline's",
    "3MF coincident vertices": "each 3MF export has no two vertices at identical coordinates",
    "3MF merges": "each 3MF export, with vertices merged within each of policy.MERGE_TOLS, has every edge "
                  "on exactly two triangles",
    "rejected sizes": "each render with a value in policy.REJECTED writes no file, and its console output "
                      "contains the value's error text in quotation marks",
    "relock rules": "a relock is refused together with --scad, writes nothing over a failure, and needs "
                    "--accept-drift for drift, a shape change or dropped coverage against the old baseline",
}


# ------------------------------------------------------------------ decisions

def hard_failures(key, m):
    """A reference metric over its Gate 1 limit, or not a number."""
    return [f"{key}: HARD {field}={m[field]:.4f} > {limit}" for field, limit in LIMITS.items()
            if not m[field] <= limit]


def sample_failures(key, row):
    """A reference measured from another number of surface points, in either
    direction, than the method requires."""
    n = row.get("samples")
    wanted = [policy.N_SAMPLES, policy.N_SAMPLES]
    return [] if n == wanted else [f"{key}: HARD measured from {n} sampled points, not {wanted}"]


def entries(base, kind):
    """A baseline's entries of one kind ("models" or "soundness"), by name. An
    entry that is not a table of values, such as a JSON null, counts as an
    empty table, which the comparisons then fail."""
    return {name: entry if isinstance(entry, dict) else {} for name, entry in base.get(kind, {}).items()}


def stopped_with(console, error):
    """Whether a console text holds this error text in quotation marks, as
    OpenSCAD prints the message of a failed assertion."""
    return f'"{error}"' in console


def drift_failures(key, now, was):
    """A reference metric worse than its locked value by more than the drift
    tolerance, or with no locked value to compare with."""
    out = []
    for field, tol in DRIFT.items():
        if field not in was:
            out.append(f"{key}: DRIFT {field}: no locked value in the baseline")
            continue
        if not now[field] - was[field] <= tol:
            out.append(f"{key}: DRIFT {field} {was[field]:.4f} -> {now[field]:.4f}")
    return out


def console_failures(label, console, stdout, notes):
    """A render whose console output is not exactly the expected text: each
    note echoed on its own line, in order, then the statistics lines of
    policy.CONSOLE_STATISTICS, every line ended by a line feed, with nothing
    before, between or after; and nothing on standard output. The whole text is
    matched in one piece."""
    lines = [re.escape(f'ECHO: "{note}"') for note in notes] + list(policy.CONSOLE_STATISTICS)
    out = []
    if not re.fullmatch("".join(line + "\n" for line in lines), console):
        out.append(f"{label}: console output is not the expected text: {first_difference(console, lines)}")
    if stdout != "":
        out.append(f"{label}: standard output is not empty: {stdout[:120]!r}")
    return out


def first_difference(console, lines):
    """Where a console text first departs from the expected lines, in words.
    This only describes a failure console_failures has already decided."""
    got = console.split("\n")
    for i, line in enumerate(lines):
        if i >= len(got):
            return f"line {i + 1} is missing"
        if not re.fullmatch(line, got[i]):
            return f"line {i + 1} is {got[i][:160]!r}"
    rest = got[len(lines):]
    if not rest:
        return f"line {len(lines)} does not end with a line feed"
    return f"after line {len(lines)} comes {chr(10).join(rest)[:160]!r}"


def soundness_failures(label, a):
    """An unsound mesh, with what is wrong with it."""
    return [] if clean(a) else [f"{label}: mesh not a clean single shell: {'; '.join(unsound_reasons(a))}"]


def lock_failures(label, a, was):
    """A render that is not in the baseline, or whose shape changed since the
    baseline was locked (was is None when relocking). The vertex digest and
    the volume are judged separately: either one changing is a change."""
    if was is None:
        return []
    if was == "absent" or "digest" not in was:
        return [f"{label}: absent from baseline; relock to cover it"]
    dv = a["volume"] - was["volume"]
    changed = []
    if a["digest"] != was["digest"]:
        changed.append("vertices")
    if abs(dv) > policy.SOUND_VOL:
        changed.append("volume")
    if changed:
        de = max(abs(x - y) for x, y in zip(a["extents"], was["extents"]))
        return [f"{label}: geometry changed vs baseline ({' and '.join(changed)}; bbox {de:.4f} mm, "
                f"volume {dv:+.3f} mm3)"]
    return []


def threemf_failures(name, groups, merged):
    """A 3MF export with coincident vertices, or with an edge off two triangles after a merge."""
    out = []
    if groups:
        out.append(f"soundness/{name}: 3MF has {groups} group(s) of separate vertices at identical coordinates")
    for tol, edges in merged.items():
        if edges:
            out.append(f"soundness/{name}: 3MF merged within {tol:g} mm leaves {edges} edge(s) "
                       f"not shared by exactly two triangles")
    return out


def rejection_failures(name, path, stopped, error):
    """A value in policy.REJECTED that the generator did not refuse. Writing a
    file and not printing the error are judged separately: either one is a
    failure."""
    out = []
    if path is not None:
        out.append(f"rejected/{name}: expected the render to stop, and it wrote a file")
    if not stopped:
        out.append(f"rejected/{name}: expected the render to stop with: {error}")
    return out


def locked_generator_failures(digest, locked, reported):
    """The baseline or VERIFICATION.md made from another version of the generator."""
    out = []
    if locked != digest:
        out.append(f"generator: the baseline was locked on another version of this file (SHA-256 {locked}); relock")
    if reported != digest:
        out.append(f"generator: VERIFICATION.md is for another version of this file (SHA-256 {reported}); "
                   "a relock rewrites it")
    return out


def coverage_failures(missing, base, update):
    """References and configurations that differ between the policy, the files and the baseline."""
    out = [f"{k}: reference file missing: {fname(k)}" for k in missing]
    if update:
        return out
    models = entries(base, "models")
    out += [f"{k}: in the baseline but not in policy.REFERENCES" for k in models if k not in REFERENCES]
    for k in REFERENCES:
        if k in missing:
            continue            # already reported as a missing file
        if k not in models:
            out.append(f"{k}: absent from baseline; relock to cover it")
    names = [n for n, _ in SOUNDNESS]
    out += [f"soundness/{n}: in the baseline but no longer checked" for n in entries(base, "soundness")
            if n not in names]
    return out


def relock_changes(current, sound_now, old):
    """What a relock would accept: reference drift, shape changes, and references
    or configurations dropped, against the baseline being replaced."""
    models, sound = entries(old, "models"), entries(old, "soundness")
    out = [f"{k}: locked reference no longer measured" for k in models if k not in current]
    out += [f"soundness/{n}: locked configuration no longer checked" for n in sound if n not in sound_now]
    for key, m in current.items():
        if key in models:
            out += drift_failures(key, m, models[key])
            out += lock_failures(key, m, models[key])
    for name, a in sound_now.items():
        if name in sound:
            out += lock_failures(f"soundness/{name}", a, sound[name])
    return out


# ------------------------------------------------------------------ the report

def report_digest(path=REPORT):
    """The generator digest a VERIFICATION.md names, or None."""
    found = re.search(r"SHA-256 ([0-9A-F]{64})", path.read_text(encoding="utf-8")) if path.is_file() else None
    return found.group(1) if found else None


def report_text(rows, started, finished, digest, renderer):
    """VERIFICATION.md for a relock. rows is one compare.measure row per
    reference, with its key and render seconds."""
    lines = [
        "# VERIFICATION - shell Gate 1 mechanical match",
        "",
        "Written by `analysis/regress.py --update-baseline` when it locked `analysis/baseline.json`, in a run "
        f"from {started} to {finished} UTC. `docs/verification-method.md` lists what that run compares.",
        "",
        f"File verified: `{compare.SCAD.name}`, SHA-256 {digest}, computed with CR LF line endings turned into "
        f"LF. `git show <commit>:\"shells/multibin-shell/{compare.SCAD.name}\" | sha256sum` prints the same digest "
        "in lower case when git holds the file with LF line endings.",
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
        "vertex of either mesh to the other. The two sampled columns vary a little from one run to the next.",
        "",
        f"Limits: bounding box <= {LIMITS['bbox']} mm per axis, volume <= {LIMITS['vol']} %, p99 <= "
        f"{LIMITS['p99']} mm, and both maxima <= {LIMITS['mx']} mm.",
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
        """Whether gate_test.py passes. A run started from inside the unit tests
        counts as failing, so the tests can never start themselves again."""
        if os.environ.get(NESTED):
            return False
        r = subprocess.run([sys.executable, str(UNIT_TESTS)], capture_output=True, text=True, cwd=HERE,
                           env=dict(os.environ, **{NESTED: "1"}))
        return r.returncode == 0

    def now(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    def digest(self, scad):
        return compare.scad_digest(scad)

    def report_digest(self):
        return report_digest(REPORT)

    def missing_refs(self):
        return [k for k in REFERENCES if not (refs.STL_DIR / fname(k)).is_file()]

    def render(self, scad, name, params):
        return compare.render(compare.OPENSCAD_COMMAND, scad, params, compare.out_for(scad) / name)

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


def run(steps, scad, update=False, accept=False, alternate=False, log=print):
    """One gate run. Returns (exit status, failures); writes the baseline and
    VERIFICATION.md only when relocking with no failures."""
    if update and alternate:
        log("refusing to lock a baseline from an alternate SCAD")
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
    failures = coverage_failures(missing, base, update)
    if not update:
        failures += locked_generator_failures(digest, base.get("scad_digest"), steps.report_digest())
    rows, current, sound_now = [], {}, {}
    models, golden = entries(base, "models"), entries(base, "soundness")

    log("=" * 78)
    log(f"REFERENCE MATCH ({len(present)} of {len(REFERENCES)} references)")
    log("=" * 78)
    for key in present:
        r = steps.render(scad, f"{key}.stl", compare.params(key))
        failures += console_failures(key, r["console"], r["stdout"], ())
        if r["path"] is None:
            failures.append(f"{key}: render failed")
            log(r["console"][-3000:])
            continue
        row = steps.measure(key, r["path"])
        m, a = compare.summary(row), steps.audit(r["path"])
        rows.append(dict(row, key=key, seconds=r["seconds"]))
        current[key] = dict(m, render_s=round(r["seconds"], 1), **{k: a[k] for k in AUDIT_KEPT})
        failures += hard_failures(key, m) + sample_failures(key, row) + soundness_failures(key, a)
        # a key the baseline lacks is reported by coverage_failures; an entry
        # that is there but empty or incomplete fails here
        if key in models:
            was = models[key]
            failures += drift_failures(key, m, was)
            failures += lock_failures(key, a, was)
            log(f"{key:6} " + "  ".join(f"{f}={m[f]:.4f}({m[f] - was.get(f, float('nan')):+.4f})" for f in DRIFT))

    log("=" * 78)
    log("CONFIGURATIONS WITHOUT A REFERENCE (mesh audit, and the locked vertex digest and volume)")
    log("=" * 78)
    for name, params in SOUNDNESS:
        notes = EXPECTED_MESSAGES.get(name, ())
        r = steps.render(scad, f"soundness/{name}.stl", params)
        failures += console_failures(f"soundness/{name}", r["console"], r["stdout"], notes)
        if r["path"] is None:
            failures.append(f"soundness/{name}: render failed")
            log(f"  {name:24} RENDER FAILED")
            log(r["console"][-3000:])
            continue
        a = steps.audit(r["path"])
        sound_now[name] = a
        found = soundness_failures(f"soundness/{name}", a)
        found += lock_failures(f"soundness/{name}", a, None if update else golden.get(name, "absent"))
        failures += found
        state = "ok" if not found else "CHANGED" if clean(a) else "BROKEN"
        log(f"  {name:24} {state:7} bbox={a['extents']} vol={a['volume']}")
        if name in THREEMF_CHECK:
            r = steps.render(scad, f"soundness/{name}.3mf", params)
            failures += console_failures(f"soundness/{name} 3MF", r["console"], r["stdout"], notes)
            if r["path"] is None:
                failures.append(f"soundness/{name}: 3MF render failed")
                continue
            groups, merged = steps.coincident_3mf(r["path"]), steps.merge_faults(r["path"])
            failures += threemf_failures(name, groups, merged)
            log(f"  {name:24} 3MF     coincident vertex groups: {groups}; edges broken by a merge: {merged}")
    for name, params, error in REJECTED:
        r = steps.render(scad, f"soundness/{name}.stl", params)
        found = rejection_failures(name, r["path"], stopped_with(r["console"], error), error)
        failures += found
        log(f"  {name:24} {'NOT REJECTED' if found else 'rejected'}")

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
            f"{len(sound_now)} configuration(s)")
        return 0, failures

    log("=" * 78)
    if failures:
        log(f"FAIL - {len(failures)} problem(s):")
        for f in failures:
            log(f"  - {f}")
        return 1, failures
    log(f"PASS - no failure in {len(REFERENCES)} references, {len(SOUNDNESS)} configurations and "
        f"{len(REJECTED)} rejected sizes.")
    return 0, failures


def options(argv):
    """What the command line asks of run()."""
    alternate = "--scad" in argv
    scad = Path(argv[argv.index("--scad") + 1]).resolve() if alternate else compare.SCAD
    return dict(scad=scad, update="--update-baseline" in argv, accept="--accept-drift" in argv, alternate=alternate)


def main(argv=None, steps=None):
    asked = options(sys.argv[1:] if argv is None else argv)
    if asked["alternate"]:
        print(f"*** checking ALTERNATE SCAD: {asked['scad'].name} ***")
    code, _ = run(steps or Steps(), **asked)
    return code


if __name__ == "__main__":
    sys.exit(main())
