"""Prove gate_test.py has teeth: break the gate one way at a time, in a copy
under .local-build/out/shell/mutation_tree, and check gate_test.py fails for
each break.

The list follows regress.CHECKS, the closed list of what the gate checks: every
check has at least one mutation that disables it, and this script fails if one
has none. The entries marked "tools" break the measuring tools, the render
function and the real steps the checks rely on. The script first runs
gate_test.py on an unmutated copy and stops if that fails, since a failing
start would count every mutation as caught. A mutation whose text is no longer
in the code counts as a failure too, so this list must be kept in step with the
gate's code.

Usage: python mutation_test.py     (a few minutes; exits 1 on any survivor)
"""
import shutil
import subprocess
import sys
from pathlib import Path

import regress

SRC = Path(__file__).resolve().parent
REPO = SRC.parents[2]
TREE = REPO / ".local-build" / "out" / "shell" / "mutation_tree"
ANA = TREE / "shells" / "multibin-shell" / "analysis"

# (check in regress.CHECKS, or "tools"; what the mutation does; file; text; replacement)
MUTATIONS = [
    ("unit tests", "the run starts although gate_test.py fails", "regress.py",
     "    if not steps.unit_tests():", "    if False:"),
    ("locked generator", "a baseline locked on another generator passes", "regress.py",
     "    if locked != digest:", "    if False:"),
    ("locked generator", "a VERIFICATION.md for another generator passes", "regress.py",
     "    if reported != digest:", "    if False:"),
    ("generator unchanged", "a generator edited during the run passes", "regress.py",
     "    if steps.digest(scad) != digest:", "    if False:"),
    ("reference coverage", "a missing reference file passes", "regress.py",
     '    out = [f"{k}: reference file missing: {fname(k)}" for k in missing]', "    out = []"),
    ("reference coverage", "a baseline reference outside the policy passes", "regress.py",
     "for k in models if k not in REFERENCES]", "for k in models if False]"),
    ("reference coverage", "a reference absent from the baseline passes", "regress.py",
     "if k not in missing and k not in models]", "if False]"),
    ("reference coverage", "the run measures only the first reference", "regress.py",
     "    for key in present:", "    for key in present[:1]:"),
    ("configuration coverage", "a configuration absent from the baseline passes", "regress.py",
     'golden.get(name, "absent")', "golden.get(name)"),
    ("configuration coverage", "a baseline configuration outside the policy passes", "regress.py",
     'for n in base.get("soundness", {}) if n not in names]', 'for n in base.get("soundness", {}) if False]'),
    ("configuration coverage", "the run renders only the first three configurations", "regress.py",
     "        for name, params in SOUNDNESS:", "        for name, params in SOUNDNESS[:3]:"),
    ("render success", "a failed reference render passes", "regress.py",
     'failures.append(f"{key}: render failed")', "pass"),
    ("render success", "a failed configuration render passes", "regress.py",
     'failures.append(f"soundness/{name}: render failed")', "pass"),
    ("render success", "a failed 3MF render passes", "regress.py",
     'failures.append(f"soundness/{name}: 3MF render failed")', "pass"),
    ("render messages", "no render message is reported", "regress.py",
     '    unwanted = [f"{label}: render message: {line}" for line in problems]', "    unwanted = []"),
    ("render messages", "reference render messages are dropped", "regress.py",
     'failures += message_failures(key, r["problems"], (), r["seen"])', "pass"),
    ("render messages", "3MF render messages are dropped", "regress.py",
     'failures += message_failures(f"soundness/{name} 3MF", r["problems"], expected, r["seen"])',
     'failures += message_failures(f"soundness/{name} 3MF", [], expected, r["seen"])'),
    ("expected messages", "a missing expected note passes", "regress.py",
     '    absent = [f"{label}: expected render message missing: {e}" for e in expected if e not in seen]',
     "    absent = []"),
    ("hard limits", "the run ignores the hard limits", "regress.py",
     "failures += hard_failures(key, m) + sample_failures(key, row) + soundness_failures(key, a)",
     "failures += sample_failures(key, row) + soundness_failures(key, a)"),
    ("hard limits", "a metric that is not a number passes the limits", "regress.py",
     "            if not m[field] <= limit]", "            if m[field] > limit]"),
    ("hard limits", "the run ignores the sample count", "regress.py",
     "failures += hard_failures(key, m) + sample_failures(key, row) + soundness_failures(key, a)",
     "failures += hard_failures(key, m) + soundness_failures(key, a)"),
    ("drift", "the run ignores drift", "regress.py", "            failures += drift_failures(key, m, was)", "            pass"),
    ("drift", "a metric that is not a number passes the drift check", "regress.py",
     "if not now[field] - was[field] <= tol]", "if now[field] - was[field] > tol]"),
    ("mesh soundness", "an unsound mesh passes", "regress.py",
     "    return [] if clean(a) else [", "    return [] if True else ["),
    ("mesh soundness", "the run ignores an unsound reference", "regress.py",
     "failures += hard_failures(key, m) + sample_failures(key, row) + soundness_failures(key, a)",
     "failures += hard_failures(key, m) + sample_failures(key, row)"),
    ("mesh soundness", "clean ignores watertightness", "compare.py", 'return (a["watertight"] and', "return (True and"),
    ("mesh soundness", "clean ignores winding", "compare.py", 'a["winding"] and a["volume"] > 0', 'a["volume"] > 0'),
    ("mesh soundness", "clean ignores bad edges and duplicated facets", "compare.py",
     '            and a["bad_edges"] == 0 and a["dup_faces"] == 0\n', ""),
    ("crossings", "clean ignores crossings", "compare.py",
     '\n            and a["crossing_depth"] <= policy.CROSSING_LIMIT)', ")"),
    ("crossings", "the crossing test finds nothing", "export_check.py",
     "    return ok & (u > -tol)", "    return ok & False & (u > -tol)"),
    ("shape lock", "a changed shape passes", "regress.py",
     '    if a["digest"] != was["digest"] or abs(dv) > policy.SOUND_VOL:', "    if False:"),
    ("shape lock", "the lock ignores the vertex digest", "regress.py", 'a["digest"] != was["digest"] or ', ""),
    ("shape lock", "the lock ignores the volume", "regress.py", " or abs(dv) > policy.SOUND_VOL", ""),
    ("3MF coincident vertices", "coincident 3MF vertices pass", "regress.py", "    if groups:", "    if False:"),
    ("3MF coincident vertices", "the coincidence count is always zero", "export_check.py",
     "    return sum(1 for n in Counter(tuple(float(c) + 0.0 for c in v) for v in coords).values() if n > 1)",
     "    return 0"),
    ("3MF merges", "edges broken by a merge pass", "regress.py", "        if edges:", "        if False:"),
    ("3MF merges", "the merge count is always zero", "export_check.py",
     "    return int((count != 2).sum())", "    return 0"),
    ("3MF merges", "the real merge step uses only the first distance", "regress.py",
     "return {tol: merge_faults(path, tol) for tol in policy.MERGE_TOLS}",
     "return {tol: merge_faults(path, tol) for tol in policy.MERGE_TOLS[:1]}"),
    ("3MF merges", "the run checks only the first 3MF configuration", "regress.py",
     "            if name in THREEMF_CHECK:", "            if name in THREEMF_CHECK[:1]:"),
    ("rejected sizes", "a size that is not rejected passes", "regress.py",
     "            if not rejected:", "            if False:"),
    ("rejected sizes", "a rejected size may write a file", "regress.py",
     'rejected = r["path"] is None and error in r["seen"]', 'rejected = error in r["seen"]'),
    ("rejected sizes", "any failed render counts as a rejection", "regress.py",
     'rejected = r["path"] is None and error in r["seen"]', 'rejected = r["path"] is None'),
    ("rejected sizes", "the run checks only the first rejected size", "regress.py",
     "        for name, params, error in REJECTED:", "        for name, params, error in REJECTED[:1]:"),
    ("relock rules", "a relock accepts changes without --accept-drift", "regress.py",
     "        if changes and not accept:", "        if False:"),
    ("relock rules", "a relock writes over failures", "regress.py",
     '        if failures:\n            log(f"NOT RELOCKED', '        if False:\n            log(f"NOT RELOCKED'),
    ("relock rules", "a relock is allowed without the configurations", "regress.py",
     "    if update and quick:", "    if False:"),
    ("relock rules", "a relock is allowed from another SCAD", "regress.py",
     "    if update and alternate:", "    if False:"),
    ("relock rules", "a relock records no generator digest", "regress.py", ", scad_digest=digest))", "))"),
    ("relock rules", "a relock writes no report", "regress.py",
     "steps.write_report(report_text(rows, started, steps.now(), digest, steps.renderer()))", "pass"),
    ("relock rules", "a relock ignores a dropped reference", "regress.py",
     'for k in old.get("models", {}) if k not in current]', 'for k in old.get("models", {}) if False]'),
    ("relock rules", "a relock ignores a dropped configuration", "regress.py", "            if n not in sound_now]",
     "            if False]"),

    ("tools", "the limits are loosened tenfold", "policy.py",
     "LIMITS = dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2)", "LIMITS = dict(bbox=0.2, vol=5.0, p99=0.5, mx=2.0)"),
    ("tools", "the drift tolerance is loosened", "policy.py",
     "DRIFT = dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002)", "DRIFT = dict(bbox=0.02, vol=0.1, p99=0.02, mx=0.02)"),
    ("tools", "fewer samples are required", "policy.py", "N_SAMPLES = 50000", "N_SAMPLES = 500"),
    ("tools", "the shape lock's volume tolerance is loosened", "policy.py", "SOUND_VOL = 0.01", "SOUND_VOL = 1000"),
    ("tools", "the crossing corner exclusion is widened", "policy.py", "CORNER_TOL = 1e-7", "CORNER_TOL = 0.05"),
    ("tools", "renders are exported as ASCII STL", "policy.py",
     'EXPORT_FORMAT = ("--export-format", "binstl")', 'EXPORT_FORMAT = ("--export-format", "asciistl")'),
    ("tools", "a merge distance is dropped", "policy.py", "MERGE_TOLS = (1e-5, 1e-4)", "MERGE_TOLS = (1e-4,)"),
    ("tools", "a 3MF configuration is dropped", "policy.py",
     'THREEMF_CHECK = ("thin_1.5x0.5x1", "half_both_2.5x1.5x1.5", "wide_4x1x1")',
     'THREEMF_CHECK = ("thin_1.5x0.5x1", "half_both_2.5x1.5x1.5")'),
    ("tools", "a rejected size is dropped", "policy.py",
     '    ("zero_height", dict(height_lu=0), "height_lu must be a multiple of 0.5 from 0.5 to 12, not 0"),\n', ""),
    ("tools", "a rejection accepts any error text", "policy.py",
     '"depth_lu must be a multiple of 0.5 from 1 to 12, not 12.5"', '"ERROR"'),
    ("tools", "an expected note is dropped", "policy.py",
     '        "NOTE: right_wall = topped has no effect: the side is shorter than 1 LU, so it has no rail channel."),',
     "    ),"),

    ("tools", "the render keeps a file from an earlier run", "compare.py",
     "    if out.exists():\n        out.unlink()", "    if False:\n        out.unlink()"),
    ("tools", "the render does not ask for binary STL", "compare.py",
     ' *(policy.EXPORT_FORMAT if out.suffix.lower() == ".stl" else ()),', ""),
    ("tools", "the render reports no messages", "compare.py",
     "problems=render_problems(r.stderr, expected)", "problems=[]"),
    ("tools", "the render counts every expected text as seen", "compare.py",
     "seen=[e for e in expected if e in r.stderr]", "seen=list(expected)"),
    ("tools", "the render returns a path it never wrote", "compare.py",
     "path=out if out.exists() else None", "path=out"),
    ("tools", "the render drops the parameters", "compare.py", '        args += ["-D", f"{k}={v}"]', "        pass"),
    ("tools", "expected texts hide every message", "compare.py",
     "return [ln for ln in lines if not NORMAL_RENDER_LINE.match(ln) and not any(e in ln for e in expected)]",
     "return [ln for ln in lines if not NORMAL_RENDER_LINE.match(ln)] if not expected else []"),
    ("tools", "a render that is not simple is allowed", "compare.py", r"|^Simple:\s+yes$", r"|^Simple:.*$"),
    ("tools", "the summary drops the vertex sweep", "compare.py",
     'np.max([a["mx"], b["mx"], a["vmax"], b["vmax"]])', 'np.max([a["mx"], b["mx"]])'),
    ("tools", "the summary takes p99 from one direction", "compare.py", 'np.max([a["p99"], b["p99"]])', 'a["p99"]'),
    ("tools", "the summary drops a value that is not a number", "compare.py",
     'mx=float(np.max([a["mx"], b["mx"], a["vmax"], b["vmax"]])))',
     'mx=float(max(a["mx"], b["mx"], a["vmax"], b["vmax"])))'),
    ("tools", "measure ignores volume", "compare.py",
     "vol=float(abs(gen.volume - ref.volume) / ref.volume * 100))", "vol=0.0)"),
    ("tools", "measure's p99 is the median", "compare.py",
     "q = np.quantile(dist, [0.95, 0.99])", "q = np.quantile(dist, [0.95, 0.5])"),
    ("tools", "measure's vertex sweep is zeroed", "compare.py", "vmax=float(vdist.max()))", "vmax=0.0)"),
    ("tools", "measure draws fewer samples than the policy", "compare.py",
     "n_samples = policy.N_SAMPLES if n_samples is None else n_samples",
     "n_samples = 500 if n_samples is None else n_samples"),
    ("tools", "metrics compares the render with itself", "compare.py",
     "    ref = trimesh.load_mesh(refs.STL_DIR / fname(key))", "    ref = trimesh.load_mesh(gen_path)"),
    ("tools", "the audit counts only edges with too many faces", "compare.py",
     "bad_edges=int((per_edge != 2).sum())", "bad_edges=int((per_edge > 2).sum())"),
    ("tools", "the audit counts no duplicated facets", "compare.py",
     "dup_faces=int((per_face > 1).sum())", "dup_faces=0"),
    ("tools", "the digest covers part of the vertices", "compare.py",
     "return hashlib.sha256(np.ascontiguousarray(vs).tobytes()).hexdigest()",
     "return hashlib.sha256(np.ascontiguousarray(vs[:3]).tobytes()).hexdigest()"),
    ("tools", "the generator digest keeps Windows line endings", "compare.py",
     '.read_bytes().replace(b"\\r\\n", b"\\n")', ".read_bytes()"),
    ("tools", "crossings count only strict interior hits", "export_check.py",
     "(u > -tol) & (w > -tol) & (u + w < 1 + tol)", "(u > tol) & (w > tol) & (u + w < 1 - tol)"),
    ("tools", "zero-area triangles skip the crossing depth", "export_check.py",
     "d = [x for x in (depth(ta, tb), depth(tb, ta)) if x is not None]",
     "d = [depth(ta, tb)] if depth(ta, tb) is not None else []"),
    ("tools", "the 3MF reader accepts an empty mesh", "export_check.py",
     "    if not coords or not tri:", "    if False:"),
    ("tools", "the 3MF reader finds no vertices", "export_check.py",
     "    if not coords or not tri:\n        raise", "    coords = []\n    if False:\n        raise"),
    ("tools", "the 3MF check compares coordinates as text", "export_check.py",
     "Counter(tuple(float(c) + 0.0 for c in v) for v in coords)", "Counter(coords)"),
    ("tools", "the merge merges nothing", "export_check.py",
     "cKDTree(v).query_pairs(tol)", "cKDTree(v).query_pairs(0.0)"),
    ("tools", "the real measure step drops volume and bounding box", "regress.py",
     "        return compare.metrics(key, path, 0)", "        return dict(compare.metrics(key, path, 0), vol=0.0, bbox=0.0)"),
    ("tools", "the real audit step drops the crossing depth", "regress.py",
     "    def audit(self, path):\n        return compare.audit(path)",
     "    def audit(self, path):\n        return dict(compare.audit(path), crossing_depth=0.0)"),
    ("tools", "the real coverage step finds no missing reference", "regress.py",
     "return [k for k in REFERENCES if not (refs.STL_DIR / fname(k)).is_file()]", "return []"),
    ("tools", "the real render step writes to the wrong folder", "regress.py",
     "compare.out_for(scad) / name", "compare.OUT / name"),
    ("tools", "the report's digest is never read", "regress.py",
     "    return found.group(1) if found else None", "    return None"),
    ("tools", "the report leaves out the digest", "regress.py",
     "SHA-256 {digest}, computed with Unix", "SHA-256 (not recorded), computed with Unix"),
]


def fresh_copy():
    if TREE.exists():
        shutil.rmtree(TREE)
    shutil.copytree(REPO / "tools", TREE / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    if (REPO / "local-paths.json").exists():
        shutil.copy(REPO / "local-paths.json", TREE / "local-paths.json")
    shutil.copytree(SRC, ANA, ignore=shutil.ignore_patterns("frozen_*.scad", "__pycache__", "baseline.json"))


def main():
    unlisted = sorted(set(regress.CHECKS) - {m[0] for m in MUTATIONS})
    unknown = sorted({m[0] for m in MUTATIONS} - set(regress.CHECKS) - {"tools"})
    if unlisted or unknown:
        print(f"checks with no mutation: {unlisted}; mutations for no known check: {unknown}")
        return 1
    # a gate_test.py that already fails would count every mutation as caught
    fresh_copy()
    if subprocess.run([sys.executable, "gate_test.py"], cwd=ANA, capture_output=True, text=True).returncode != 0:
        print("gate_test.py fails without any mutation; fix it before testing mutations")
        shutil.rmtree(TREE, ignore_errors=True)
        return 1
    survivors = []
    for check, name, fname, old, new in MUTATIONS:
        fresh_copy()
        path = ANA / fname
        s = path.read_text(encoding="utf-8")
        if s.count(old) != 1:
            print(f"  NOT APPLIED  [{check}] {name} (text found {s.count(old)} times)")
            survivors.append(name)
            continue
        path.write_text(s.replace(old, new), encoding="utf-8")
        r = subprocess.run([sys.executable, "gate_test.py"], cwd=ANA, capture_output=True, text=True)
        caught = r.returncode != 0
        print(f"  {'caught  ' if caught else 'SURVIVED'} [{check}] {name}")
        if not caught:
            survivors.append(name)
    shutil.rmtree(TREE, ignore_errors=True)
    print(f"{len(MUTATIONS) - len(survivors)} of {len(MUTATIONS)} mutations caught, "
          f"covering all {len(regress.CHECKS)} checks")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
