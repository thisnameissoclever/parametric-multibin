"""Prove the regression gate works: run it in full against the known-bad
fixture and check that every section of the gate reports the failure it must.

The fixture, fixtures/frozen_a6ff94e.scad, is the generator as of commit
a6ff94e. Against today's baseline it has, among other faults:

  render messages    every render prints a nonplanar-face notice (its thread)
  HARD               Topless rim grooves stop at the seams: 0.4 mm on O212;
                     Simple walls lack the full rim groove: p99 0.14 mm on S111
  DRIFT              slot mouth chamfer 0.047 mm on T111, against 0.019 locked
  soundness, shape   rail channels blocked over half pads: volume of 1.5x1x1
  soundness, mesh    broken pocket slits on 1 x 7 x 1

A gate section that stopped working would drop its line from the output, so
the self-test checks each line, not only the exit status.

Usage: python selftest.py     (a full run; about 30 minutes)
Exits 0 when the gate failed in every expected way, 1 otherwise.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
FIXTURE = HERE / "fixtures" / "frozen_a6ff94e.scad"

# (gate section, text that must appear in the gate's failure list)
EXPECTED_FAILURES = [
    ("render messages", "T111: render message: PolySet has nonplanar faces"),
    ("HARD maximum", "O212: HARD mx="),
    ("HARD p99", "S111: HARD p99="),
    ("DRIFT", "T111: DRIFT mx"),
    ("soundness shape", "soundness/half_w_1.5x1x1: geometry moved vs baseline"),
    ("soundness mesh", "soundness/long_1x7x1: mesh not a clean single shell"),
]


def main():
    r = subprocess.run([sys.executable, str(HERE / "regress.py"), "--scad", str(FIXTURE)],
                       capture_output=True, text=True, cwd=HERE)
    out = r.stdout + r.stderr
    log = HERE.parents[2] / ".local-build" / "out" / "shell" / "selftest.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(out, encoding="utf-8")
    ok = True
    if r.returncode != 1:
        print(f"gate exit status {r.returncode}, expected 1")
        ok = False
    for section, text in EXPECTED_FAILURES:
        found = text in out
        print(f"  {'caught ' if found else 'MISSED '} {section:16} {text}")
        ok &= found
    print(f"full gate output: {log}")
    print("SELF-TEST PASS: the gate caught every expected failure" if ok
          else "SELF-TEST FAIL: the gate missed an expected failure")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
