"""Check, in about a second and without rendering, that baseline.json and
VERIFICATION.md were made from the generator as it is now. regress.py makes the
same check at the start of every plain run.

Usage: python records_check.py     (exits 1 when either names another version)
"""

import sys

import compare
import regress


def main():
    steps = regress.Steps()
    base = steps.load_baseline() or {}
    failures = regress.locked_generator_failures(steps.digest(compare.SCAD), base.get("scad_digest"),
                                                 steps.report_digest())
    for line in failures:
        print(line)
    if not failures:
        print("baseline.json and VERIFICATION.md both name the generator as it is now")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
