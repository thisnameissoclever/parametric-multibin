"""Run the gate's own tests, in three steps:

1. gate_test.py, a few seconds.
2. mutation_test.py, a few minutes: each break in its list must make
   gate_test.py fail.
3. A run of regress.py against the known-bad fixture, which must fail and must
   report each failure listed below.

The fixture, fixtures/frozen_a6ff94e.scad, is the generator as of commit
a6ff94e. Against the current baseline it has, among other faults:

  locked generator   it is not the file the baseline was made from, nor the
                     file VERIFICATION.md is for
  console output     every render prints a nonplanar-face notice (its thread),
                     references, configurations and 3MF exports alike, and
                     the 0.5 LU shell prints no note for its wall choices
  HARD               Topless rim grooves stop at the seams: 0.4 mm on O212;
                     Simple walls lack the full rim groove: p99 0.14 mm on S111
  DRIFT              its slot mouth chamfer puts T111's worst point at 0.046 mm,
                     against 0.019 locked, and its volume difference at 0.022 %,
                     against 0.008 %
  reference shape    its references are not the meshes the baseline locked,
                     T111 among them
  soundness, shape   half-LU shells differ in several ways, among them channels
                     blocked over half pads and missing half-pad clip pockets
  soundness, mesh    broken pocket slits on 1 x 7 x 1
  reference mesh     triangles crossing 0.006 mm deep on the 3 LU wide
                     references, among them T313
  3MF export         its threaded holes' entry cones cross the thread at shared
                     angles, leaving separate vertices at identical coordinates
  3MF merge          its seam slots' inner chamfers start in the inner grooves'
                     floor plane, so merging the 4 x 1 x 1 export's vertices
                     within 0.00001 mm leaves edges with four triangles
  rejected sizes     it builds sizes the sliders cannot produce instead of
                     stopping with an error

The self-test looks for each line, not only the exit status. The fixture does
not fail the unit tests, generator unchanged, reference coverage, configuration
coverage, render success or relock rules checks, so this step shows nothing
about those; gate_test.py drives them with stand-in steps.

Usage: python selftest.py     (about an hour, almost all of it step 3)
Exits 0 when all three steps pass, 1 otherwise.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
FIXTURE = HERE / "fixtures" / "frozen_a6ff94e.scad"

# (gate section, text that must appear in the gate's failure list)
EXPECTED_FAILURES = [
    ("locked generator", "generator: the baseline was locked on another version"),
    ("locked generator, report", "generator: VERIFICATION.md is for another version"),
    ("reference console output", "T111: console output is not the expected text"),
    ("configuration console output", "soundness/half_w_1.5x1x1: console output is not the expected text"),
    ("expected notes", "soundness/thin_1.5x0.5x1: console output is not the expected text"),
    ("3MF console output", "soundness/half_both_2.5x1.5x1.5 3MF: console output is not the expected text"),
    ("HARD maximum", "O212: HARD mx="),
    ("HARD p99", "S111: HARD p99="),
    ("DRIFT", "T111: DRIFT mx"),
    ("DRIFT volume", "T111: DRIFT vol"),
    ("reference shape", "T111: geometry changed vs baseline"),
    ("soundness shape", "soundness/half_w_1.5x1x1: geometry changed vs baseline"),
    ("soundness mesh", "soundness/long_1x7x1: mesh not a clean single shell"),
    ("reference mesh", "T313: mesh not a clean single shell: triangles crossing"),
    ("3MF export", "soundness/half_both_2.5x1.5x1.5: 3MF has"),
    ("3MF merge", "soundness/wide_4x1x1: 3MF merged within 1e-05 mm"),
    ("rejected sizes", "rejected/width_between_steps: expected the render to stop"),
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
    print("SELF-TEST PASS: gate_test.py passed, mutation_test.py found no survivor, "
          "and the gate reported every listed failure of the fixture"
          if ok else "SELF-TEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
