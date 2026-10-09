"""Prove the regression gate works, in two steps:

1. gate_test.py checks every decision of the gate at its limits, in seconds.
2. A full run of regress.py against the known-bad fixture must fail, and each
   section of the gate must report a failure the fixture is known to cause.

The fixture, fixtures/frozen_a6ff94e.scad, is the generator as of commit
a6ff94e. Against the current baseline it has, among other faults:

  render messages    every render prints a nonplanar-face notice (its thread),
                     references and soundness configurations alike
  HARD               Topless rim grooves stop at the seams: 0.4 mm on O212;
                     Simple walls lack the full rim groove: p99 0.14 mm on S111
  DRIFT              its slot mouth chamfer puts T111's worst point at 0.046 mm,
                     against 0.019 locked
  soundness, shape   half-LU shells differ in several ways, among them channels
                     blocked over half pads and missing half-pad clip pockets
  soundness, mesh    broken pocket slits on 1 x 7 x 1

A gate section that stopped working would drop its line from the output, so
the self-test checks each line, not only the exit status.

Usage: python selftest.py     (about 40 minutes, almost all of it step 2)
Exits 0 when both steps pass, 1 otherwise.
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
    ("soundness shape", "soundness/half_w_1.5x1x1: geometry changed vs baseline"),
    ("soundness mesh", "soundness/long_1x7x1: mesh not a clean single shell"),
]


def main():
    unit = subprocess.run([sys.executable, str(HERE / "gate_test.py")], capture_output=True, text=True, cwd=HERE)
    print(unit.stdout.strip().splitlines()[-1] if unit.stdout.strip() else unit.stderr[-2000:])
    ok = unit.returncode == 0
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
    print("SELF-TEST PASS: the gate's decisions hold at their limits and it caught every expected failure"
          if ok else "SELF-TEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
