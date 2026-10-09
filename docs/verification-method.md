# Verification method

This document defines how every generator in this repository is shown to reproduce MultiBuild's published parts, and what has to happen before a generator is signed off. Each part follows it; the drawer was the first.

## Contents

- [Generator constraints](#generator-constraints)
- [Reference files](#reference-files)
- [Gate 1: mechanical match](#gate-1-mechanical-match)
- [Mesh soundness](#mesh-soundness)
- [Regression gate](#regression-gate)
- [Gate 2: adversarial review](#gate-2-adversarial-review)
- [Sign-off](#sign-off)
- [Per-part documents](#per-part-documents)

## Generator constraints

A generator is one `.scad` file that pastes into MakerWorld's Parametric Model Maker unchanged. It must render in OpenSCAD 2021.01, must not use `import()`, `include` or `use`, and must not depend on any other file. Every user-facing parameter carries a Customizer annotation (the `// [min:step:max]` or `// [a, b, c]` comment that turns a variable into a slider or dropdown). The file is plain ASCII.

## Reference files

The references are MultiBuild's original STL files, downloaded from [multibuild.io](https://multibuild.io). Their license forbids redistribution, so they are never committed. Each machine lists its reference folders in `local-paths.json` or in the `MULTIBIN_REFS_<PART>` environment variables, as described in `tools/mbpaths.py`.

Reference configurations use MultiBuild's own naming, width x height x depth in LU, where one LU (layout unit) is 50 mm.

## Gate 1: mechanical match

For every reference configuration, the harness renders the generator with matching parameters, aligns the two meshes by their bounding-box minimum corners, and measures:

| Measure | Limit |
|---|---|
| Bounding-box difference, per axis | 0.02 mm |
| Volume difference | 0.5 % |
| 99th-percentile surface distance, worse of both directions, at least 50,000 sampled points per side | 0.05 mm |
| Maximum surface distance, from sampling and from a sweep of every vertex in both directions | 0.2 mm |

A localized excursion past a limit is either fixed or entered in the part's `DEVIATIONS.md`, with section or plane evidence that the originals themselves are inconsistent at that spot.

The vertex sweep exists because random area-weighted sampling misses deviations shaped like an edge rather than a patch. On the drawer, sampling reported 0.010 mm where the true worst case was 0.133 mm.

## Mesh soundness

Every export must be watertight and a single body, with every edge shared by exactly two faces and no duplicated facets. This applies to the reference configurations and to configurations that have no reference at all, because most defects found during the drawer work appeared only at sizes MultiBuild does not publish.

## Regression gate

Each part has `analysis/regress.py` and a locked `analysis/baseline.json`. One run checks three things:

- **Hard limits:** the Gate 1 limits, on every reference that is present.
- **Drift:** no metric may get worse than the baseline by more than 0.002 mm, or 0.01 % of volume.
- **Soundness:** a list of configurations without references, checked for mesh soundness and against locked bounding-box and volume values. The volume check catches a feature fused into the wrong neighbour, which leaves the mesh topologically valid.

A missing reference file is reported on every run, never skipped silently. In the shell's gate, a reference that was present when the baseline was locked fails the run if it goes missing. Run the gate after every change. Relock the baseline only after an intended geometry change, and say so in the commit message.

The gate is proven by running it against a known-bad version of the generator kept in `analysis/fixtures/`. That run must fail, and each section of the gate must report the fixture defect it is meant to catch, so that a section that stopped working is noticed; the shell's `analysis/selftest.py` checks this.

## Gate 2: adversarial review

Reviewers are subagents with fresh context, three per round, briefed to disprove the match. They receive the generator, the reference files and the harness thresholds, but not the implementation notes, the deviation claims or `VERIFICATION.md`.

- **R1** reproduces the Gate 1 metrics from scratch with its own code.
- **R2** audits feature meaning with its own sections and queries: what each part of the geometry is for, and whether the generator gets it right.
- **R3** fuzzes configurations away from the references, looking for broken meshes and implausible geometry.

Every finding is fixed or documented. Review ends when two consecutive rounds return no undocumented findings and a reviewer countersigns `DEVIATIONS.md` after checking every entry against its own measurements. The final file must then render cleanly with valid Customizer syntax.

## Sign-off

After the reviewers countersign, Tim reviews the generator and signs off. The pull request merges only after that.

## Per-part documents

- `REVERSE-ENGINEERING.md` records the measured construction of the originals.
- `DEVIATIONS.md` lists every known difference from the originals, with its evidence.
- `VERIFICATION.md` is the dated harness output, tied to the generator's SHA-256 digest.
