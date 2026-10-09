"""Prove gate_test.py has teeth: break the gate one way at a time, in a copy
under .local-build/out/shell/mutation_tree, and check gate_test.py fails for
each break. A surviving mutation is a gap in the unit tests. A mutation whose
text is no longer in the code counts as a failure too, so this list must be
kept in step with the gate's code.

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
     'mx=max(a["mx"], b["mx"], a["vmax"], b["vmax"]))', 'mx=max(a["mx"], b["mx"]))'),
    ("summary p99 from one direction", "compare.py", 'p99=max(a["p99"], b["p99"])', 'p99=a["p99"]'),
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
    ("relock accepts everything", "regress.py",
     '    """What a relock would accept: reference drift and configuration shape\n    changes against the baseline being replaced."""\n    out = []',
     '    """What a relock would accept: reference drift and configuration shape\n    changes against the baseline being replaced."""\n    return []\n    out = []'),
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
     'for field, limit in HARD.items() if m[field] > limit]', 'for field, limit in HARD.items() if field != "p99" and m[field] > limit]'),
    ("3MF check counts nothing", "export_check.py",
     "    return sum(1 for n in Counter(coords).values() if n > 1)", "    return 0"),
    ("missing expected message ignored", "regress.py",
     '[f"{label}: expected render message missing: {e}" for e in expected if e not in seen]', '[]'),
]


def main():
    survivors = []
    for name, fname, old, new in MUTATIONS:
        if TREE.exists():
            shutil.rmtree(TREE)
        shutil.copytree(REPO / "tools", TREE / "tools")
        if (REPO / "local-paths.json").exists():
            shutil.copy(REPO / "local-paths.json", TREE / "local-paths.json")
        shutil.copytree(SRC, ANA, ignore=shutil.ignore_patterns("fixtures", "__pycache__", "baseline.json"))
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
