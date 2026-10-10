"""Prove gate_test.py has teeth: break the gate one way at a time, in a copy
under .local-build/out/shell/mutation_tree, and check gate_test.py fails for
each break. It first runs gate_test.py on an unmutated copy and stops if that
fails, since a failing start would count every mutation as caught. A surviving
mutation is a gap in the unit tests. A mutation whose text is no longer in the
code counts as a failure too, so this list must be kept in step with the
gate's code.

Usage: python mutation_test.py     (about a minute; exits 1 on any survivor)
"""
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
REPO = SRC.parents[2]
TREE = REPO / ".local-build" / "out" / "shell" / "mutation_tree"
ANA = TREE / "shells" / "multibin-shell" / "analysis"

MUTATIONS = [
    ("limits loosened tenfold", "compare.py",
     "LIMITS = dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2)", "LIMITS = dict(bbox=0.2, vol=5.0, p99=0.5, mx=2.0)"),
    ("gate ignores soundness and messages", "compare.py",
     'and sound[r["key"]] and not problems[r["key"]]', ''),
    ("summary drops the vertex sweep", "compare.py",
     'np.max([a["mx"], b["mx"], a["vmax"], b["vmax"]])', 'np.max([a["mx"], b["mx"]])'),
    ("summary p99 from one direction", "compare.py", 'np.max([a["p99"], b["p99"]])', 'a["p99"]'),
    ("clean ignores watertight", "compare.py", 'return (a["watertight"] and', 'return (True and'),
    ("clean ignores winding", "compare.py", 'a["winding"] and a["volume"] > 0', 'a["volume"] > 0'),
    ("clean ignores bad edges and duplicates", "compare.py",
     'and a["bad_edges"] == 0 and a["dup_faces"] == 0', ''),
    ("clean ignores crossings", "compare.py", 'and a["crossing_depth"] <= CROSSING_LIMIT)', ')'),
    ("digest of part of the vertices", "compare.py",
     'return hashlib.sha256(np.ascontiguousarray(vs).tobytes()).hexdigest()',
     'return hashlib.sha256(np.ascontiguousarray(vs[:3]).tobytes()).hexdigest()'),
    ("vertex sweep zeroed", "compare.py", 'vmax=float(vdist.max()))', 'vmax=0.0)'),
    ("crossing test always false", "export_check.py",
     "    return ok & (u > -tol)", "    return ok & False & (u > -tol)"),
    ("crossings back to strict interior", "export_check.py",
     "(u > -tol) & (w > -tol) & (u + w < 1 + tol)", "(u > tol) & (w > tol) & (u + w < 1 - tol)"),
    ("relock ignores reference drift", "regress.py",
     'out += drift_failures(key, m, old["models"][key])', "pass"),
    ("relock ignores shape changes", "regress.py",
     'out += [f for f in sound_failures(name, a, old["soundness"][name]) if "geometry changed" in f]', "pass"),
    ("soundness ignores volume", "regress.py", 'or abs(dv) > SOUND_VOL', ''),
    ("soundness ignores the digest", "regress.py", 'a["digest"] != was["digest"] or ', ''),
    ("coverage checks nothing", "regress.py",
     '    out = [f"{k}: reference file missing: {fname(k)}" for k in missing]\n    if update:',
     '    return []\n    out = []\n    if update:'),
    ("messages never reported", "compare.py",
     "    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]",
     "    return []\n    lines = []"),
    ("drift tolerance loosened", "regress.py",
     "DRIFT = dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002)", "DRIFT = dict(bbox=0.02, vol=0.1, p99=0.02, mx=0.02)"),
    ("hard check off by one field", "regress.py",
     "if not m[field] <= limit]", 'if field != "p99" and not m[field] <= limit]'),
    ("3MF check counts nothing", "export_check.py",
     "    return sum(1 for n in Counter(tuple(float(c) + 0.0 for c in v) for v in coords).values() if n > 1)",
     "    return 0"),
    ("3MF check compares text", "export_check.py",
     "Counter(tuple(float(c) + 0.0 for c in v) for v in coords)", "Counter(coords)"),
    ("run drops coverage", "regress.py",
     "failures = coverage_failures(missing, base, update, quick, [n for n, _ in SOUNDNESS])", "failures = []"),
    ("run ignores an unsound reference", "regress.py", "failures.append(unsound(key, a))", "pass"),
    ("run ignores reference render messages", "regress.py",
     "failures += message_failures(key, problems, (), ())", "pass"),
    ("run ignores HARD", "regress.py", "failures += hard_failures(key, m)", "pass"),
    ("run ignores drift", "regress.py", "failures += drift_failures(key, m, was)", "pass"),
    ("run skips expected notes", "regress.py",
     'failures += message_failures(f"soundness/{name}", problems, expected, seen)',
     'failures += message_failures(f"soundness/{name}", problems, (), ())'),
    ("run ignores soundness failures", "regress.py", "            failures += found", "            pass"),
    ("run ignores 3MF coincidences", "regress.py", "elif groups:", "elif False:"),
    ("run accepts unrejected sizes", "regress.py", "if stl is not None or error not in err:", "if False:"),
    ("relock skips the refusal", "regress.py", "if changes and not accept:", "if False:"),
    ("relock writes over failures", "regress.py",
     'log(f"NOT RELOCKED - {len(failures)} problem(s):")', 'log(f"NOT RELOCKED - {len(failures)} problem(s):"); failures = []'),
    ("run ignores a failed reference render", "regress.py", 'failures.append(f"{key}: render failed")', "pass"),
    ("run ignores a failed soundness render", "regress.py",
     'failures.append(f"soundness/{name}: render failed")', "pass"),
    ("run ignores a failed 3MF render", "regress.py",
     'failures.append(f"soundness/{name}: 3MF render failed")', "pass"),
    ("rejection accepts a written file", "regress.py",
     "if stl is not None or error not in err:", "if error not in err:"),
    ("3MF check drops a size", "regress.py",
     'THREEMF_CHECK = ["thin_1.5x0.5x1", "half_both_2.5x1.5x1.5", "wide_4x1x1"]',
     'THREEMF_CHECK = ["thin_1.5x0.5x1", "half_both_2.5x1.5x1.5"]'),
    ("merge check counts nothing", "export_check.py",
     "    return int((count != 2).sum())", "    return 0"),
    ("merge check merges nothing", "export_check.py",
     "cKDTree(v).query_pairs(tol)", "cKDTree(v).query_pairs(0.0)"),
    ("merge check drops a distance", "export_check.py", "MERGE_TOLS = (1e-5, 1e-4)", "MERGE_TOLS = (1e-4,)"),
    ("run ignores merge faults", "regress.py", "                    if edges:", "                    if False:"),
    ("measure ignores volume", "compare.py",
     "vol=float(abs(gen.volume - ref.volume) / ref.volume * 100))", "vol=0.0)"),
    ("measure p99 is the median", "compare.py",
     "q = np.quantile(dist, [0.95, 0.99])", "q = np.quantile(dist, [0.95, 0.5])"),
    ("HARD passes NaN", "regress.py", "if not m[field] <= limit]", "if m[field] > limit]"),
    ("DRIFT passes NaN", "regress.py",
     "if not now[field] - was[field] <= tol]", "if now[field] - was[field] > tol]"),
    ("summary drops NaN", "compare.py",
     'mx=float(np.max([a["mx"], b["mx"], a["vmax"], b["vmax"]])))',
     'mx=float(max(a["mx"], b["mx"], a["vmax"], b["vmax"])))'),
    ("relock ignores dropped configurations", "regress.py", "if n not in sound_now]", "if False]"),
    ("flat triangles skip the depth", "export_check.py",
     "d = [x for x in (depth(ta, tb), depth(tb, ta)) if x is not None]",
     "d = [depth(ta, tb)] if depth(ta, tb) is not None else []"),
    ("a render that is not simple is allowed", "compare.py", r'|^Simple:\s+yes$', r'|^Simple:.*$'),
    ("expected texts hide every message", "compare.py",
     "return [ln for ln in lines if not NORMAL_RENDER_LINE.match(ln) and not any(e in ln for e in expected)]",
     "return [ln for ln in lines if not NORMAL_RENDER_LINE.match(ln)] if not expected else []"),
    ("real run checks only the first merge distance", "regress.py",
     "return {tol: merge_faults(path, tol) for tol in MERGE_TOLS}",
     "return {tol: merge_faults(path, tol) for tol in MERGE_TOLS[:1]}"),
    ("real render reports every expected text as seen", "regress.py",
     "[e for e in expected if e in stderr]", "list(expected)"),
    ("real render returns a path never written", "regress.py",
     "return ((out if out.exists() else None)", "return ((out)"),
    ("real audit skips the crossing check", "regress.py",
     "    def audit(self, path):\n        return audit(path)",
     "    def audit(self, path):\n        return dict(audit(path), crossing_depth=0.0)"),
    ("3MF reader finds no mesh", "export_check.py",
    "    if not coords or not tri:\n        raise", "    coords = []\n    if False:\n        raise"),
    ("3MF reader accepts an empty mesh", "export_check.py", "    if not coords or not tri:", "    if False:"),
    ("real measure drops volume and bounding box", "regress.py",
     "        return summary(metrics(key, path, 0))", "        return dict(summary(metrics(key, path, 0)), vol=0.0, bbox=0.0)"),
    ("metrics compares the render with itself", "compare.py",
     "    ref = trimesh.load_mesh(STL_DIR / fname(key))", "    ref = trimesh.load_mesh(gen_path)"),
    ("real coverage finds no missing reference", "regress.py",
     "return [k for k in EXPECTED if not (STL_DIR / fname(k)).is_file()]", "return []"),
    ("run ignores 3MF render messages", "regress.py",
     'failures += message_failures(f"soundness/{name} 3MF", problems, expected, seen)',
     'failures += message_failures(f"soundness/{name} 3MF", [], expected, seen)'),
    ("run ignores a generator changed mid-run", "regress.py", "    if steps.digest(scad) != digest:", "    if False:"),
    ("relock records no digest", "regress.py", ", scad_digest=digest))", "))"),
    ("report ignores a generator changed mid-run", "compare.py",
     "    if digest_end != digest_start:", "    if False:"),
    ("digest keeps Windows line endings", "compare.py",
     '.read_bytes().replace(b"\\r\\n", b"\\n")', ".read_bytes()"),
    ("rejection checks only that no file was written", "regress.py",
     "if stl is not None or error not in err:", "if stl is not None:"),
    ("relock ignores a dropped reference", "regress.py",
     'out = [f"{k}: locked reference no longer measured" for k in old.get("models", {}) if k not in current]',
     "out = []"),
    ("one rejected size dropped", "regress.py",
     '    ("zero_height", dict(height_lu=0), "height_lu must be a multiple of 0.5 from 0.5 to 12, not 0"),\n', ""),
    ("failure omits the crossing", "compare.py",
     """out.append(f"triangles crossing {a['crossing_depth']:.2g} mm deep")""", "pass"),
    ("missing expected message ignored", "regress.py",
     '[f"{label}: expected render message missing: {e}" for e in expected if e not in seen]', '[]'),
]


def fresh_copy():
    if TREE.exists():
        shutil.rmtree(TREE)
    shutil.copytree(REPO / "tools", TREE / "tools")
    if (REPO / "local-paths.json").exists():
        shutil.copy(REPO / "local-paths.json", TREE / "local-paths.json")
    shutil.copytree(SRC, ANA, ignore=shutil.ignore_patterns("fixtures", "__pycache__", "baseline.json"))


def main():
    # a gate_test.py that already fails would count every mutation as caught
    fresh_copy()
    if subprocess.run([sys.executable, "gate_test.py"], cwd=ANA, capture_output=True, text=True).returncode != 0:
        print("gate_test.py fails without any mutation; fix it before testing mutations")
        shutil.rmtree(TREE, ignore_errors=True)
        return 1
    survivors = []
    for name, fname, old, new in MUTATIONS:
        fresh_copy()
        path = ANA / fname
        s = path.read_text(encoding="utf-8")
        if s.count(old) != 1:
            print(f"  NOT APPLIED  {name} (pattern found {s.count(old)} times)")
            survivors.append(name)
            continue
        path.write_text(s.replace(old, new), encoding="utf-8")
        r = subprocess.run([sys.executable, "gate_test.py"], cwd=ANA, capture_output=True, text=True)
        caught = r.returncode != 0
        print(f"  {'caught  ' if caught else 'SURVIVED'} {name}")
        if not caught:
            survivors.append(name)
    shutil.rmtree(TREE, ignore_errors=True)
    print(f"{len(MUTATIONS) - len(survivors)} of {len(MUTATIONS)} mutations caught")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
