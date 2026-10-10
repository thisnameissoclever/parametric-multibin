"""Prove the regression gate works, in three steps:

1. gate_test.py checks the gate's decisions at their limits and drives its
   whole run with stand-in renders, in about a second.
2. mutation_test.py breaks the gate one way at a time and checks that
   gate_test.py notices each break, in about a minute.
3. A full run of regress.py against the known-bad fixture must fail, and must
   report each failure listed below that the fixture is known to cause.

The fixture, fixtures/frozen_a6ff94e.scad, is the generator as of commit
a6ff94e. Against the current baseline it has, among other faults:

  render messages    every render prints a nonplanar-face notice (its thread),
                     references and soundness configurations alike
  HARD               Topless rim grooves stop at the seams: 0.4 mm on O212;
                     Simple walls lack the full rim groove: p99 0.14 mm on S111
  DRIFT              its slot mouth chamfer puts T111's worst point at 0.046 mm,
                     against 0.019 locked, and its volume difference at 0.022 %,
                     against 0.008 %
  soundness, shape   half-LU shells differ in several ways, among them channels
                     blocked over half pads and missing half-pad clip pockets
  soundness, mesh    broken pocket slits on 1 x 7 x 1
  reference mesh     triangles crossing 0.006 mm deep on the 3 LU wide
                     references, among them T313
  3MF export         its threaded holes' entry cones cross the thread at shared
                     angles, leaving separate vertices at identical coordinates;
                     its 3MF exports print the nonplanar-face notice too
  3MF merge          its seam slots' inner chamfers start in the inner grooves'
                     floor plane, so merging the 4 x 1 x 1 export's vertices
                     within 0.00001 mm leaves edges with four triangles
  expected notes     it prints no note for wall choices on a 0.5 LU side
  rejected sizes     it builds sizes the sliders cannot produce instead of
                     stopping with an error

A gate section that stopped working would drop its line from the output, so
the self-test checks each line, not only the exit status. The fixture causes
no fault that only the 0.0001 mm 3MF merge finds; gate_test.py shows that the
real run applies that distance.

Usage: python selftest.py     (about 40 minutes, almost all of it step 3)
Exits 0 when all three steps pass, 1 otherwise.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
FIXTURE = HERE / "fixtures" / "frozen_a6ff94e.scad"

# (gate section, text that must appear in the gate's failure list)
EXPECTED_FAILURES = [
    ("reference render messages", "T111: render message: PolySet has nonplanar faces"),
    ("soundness render messages", "soundness/half_w_1.5x1x1: render message: PolySet has nonplanar faces"),
    ("HARD maximum", "O212: HARD mx="),
    ("HARD p99", "S111: HARD p99="),
    ("DRIFT", "T111: DRIFT mx"),
    ("DRIFT volume", "T111: DRIFT vol"),
    ("soundness shape", "soundness/half_w_1.5x1x1: geometry changed vs baseline"),
    ("soundness mesh", "soundness/long_1x7x1: mesh not a clean single shell"),
    ("reference mesh", "T313: mesh not a clean single shell: triangles crossing"),
    ("3MF export", "soundness/half_both_2.5x1.5x1.5: 3MF has"),
    ("3MF render messages", "soundness/half_both_2.5x1.5x1.5 3MF: render message"),
    ("3MF merge", "soundness/wide_4x1x1: 3MF merged within 1e-05 mm"),
    ("expected notes", "soundness/thin_1.5x0.5x1: expected render message missing"),
    ("rejected sizes", "rejected/offstep_width_1.3: expected the render to stop"),
]


def main():
    unit = subprocess.run([sys.executable, str(HERE / "gate_test.py")], capture_output=True, text=True, cwd=HERE)
    print(unit.stdout.strip().splitlines()[-1] if unit.stdout.strip() else unit.stderr[-2000:])
    ok = unit.returncode == 0
    mut = subprocess.run([sys.executable, str(HERE / "mutation_test.py")], capture_output=True, text=True, cwd=HERE)
    print(mut.stdout.strip().splitlines()[-1] if mut.stdout.strip() else mut.stderr[-2000:])
    ok &= mut.returncode == 0
    r = subprocess.run([sys.executable, str(HERE / "regress.py"), "--scad", str(FIXTURE)],
                       capture_output=True, text=True, cwd=HERE)
    out = r.stdout + r.stderr
    log = HERE.parents[2] / ".local-build" / "out" / "shell" / "selftest.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(out, encoding="utf-8")
    if r.returncode != 1:
        print(f"gate exit status {r.returncode} against the fixture, expected 1")
        ok = False
    for section, text in EXPECTED_FAILURES:
        found = text in out
        print(f"  {'caught ' if found else 'MISSED '} {section:26} {text}")
        ok &= found
    print(f"full gate output: {log}")
    print("SELF-TEST PASS: the gate's decisions hold at their limits, its tests catch every mutation, "
          "and it caught every expected failure"
          if ok else "SELF-TEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
