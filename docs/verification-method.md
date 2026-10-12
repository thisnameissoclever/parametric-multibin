# Verification method

This document defines how every generator in this repository is shown to reproduce MultiBuild's published parts, and what has to happen before a generator is signed off. Each part follows it; the drawer was the first.

## Contents

- [Generator constraints](#generator-constraints)
- [Reference files](#reference-files)
- [Gate 1: mechanical match](#gate-1-mechanical-match)
- [Mesh soundness](#mesh-soundness)
- [Regression gate](#regression-gate)
  - [What the shell's gate checks](#what-the-shells-gate-checks)
  - [What the gate does not see](#what-the-gate-does-not-see)
  - [How the gate is proven](#how-the-gate-is-proven)
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

Each part has `analysis/regress.py` and a locked `analysis/baseline.json`. Run the gate after every change to the generator. Relock the baseline only after an intended change, and say so in the commit message.

The shell's gate is the current design, described below. The drawer's gate predates it: it checks the hard limits, the drift, and the bounding box and volume of its configurations without references. Porting the shell's gate to the drawer is on the roadmap.

### What the shell's gate checks

This list is closed. `regress.CHECKS` holds the same names, and `analysis/policy.py` holds the limits and lists this table names. Adding a check means changing this document. Each row says what the gate checks, no more: a row about renders covers the renders the gate makes of the references and configurations the policy lists. The renders of the rejected sizes have a row of their own and fall outside the Render success and Render messages rows. A `--quick` run renders only the references: it skips the Configuration coverage, Expected messages, 3MF and Rejected sizes rows, and its PASS line says the configurations were skipped.

| Check | What must hold |
|---|---|
| Unit tests | `gate_test.py` passes before anything is rendered. A run started from inside those tests counts them as failed, so they cannot start themselves again. |
| Locked generator | The generator is the file the baseline and `VERIFICATION.md` were made from, by its SHA-256 digest. Any edit to the generator's text, even to a comment, therefore needs a relock; a change of line endings alone does not, because the digest is taken with Unix line endings. A relock without `--accept-drift` shows that the edit changed no shape the gate renders, compared with the baseline it replaces. |
| Customizer | The gate scans the generator's text up to the first `{` outside comments and strings. It takes each line that starts with a name and `=` as a Customizer parameter, unless the nearest one-line block comment above it is `/* [Hidden] */` with nothing else in it. Those must be the parameters the policy lists, each with the policy's slider range or dropdown values. A parameter has a slider or dropdown only when the rest of its line is a number or a quoted string, one semicolon and a `// [...]` note, with nothing more; written any other way it fails, and so does a parameter in a section opened after the Hidden one. The rejected sizes below are derived from the same ranges, and both ends of every slider are among the configurations rendered. |
| Generator unchanged | The generator is the same file at the end of the run as at the start. |
| Reference coverage | Every reference the policy lists has its file, is measured and is in the baseline, and the baseline holds no other reference. A missing reference fails the run; it is never skipped. |
| Configuration coverage | Every configuration without a reference that the policy lists is rendered and is in the baseline, and the baseline holds no other. |
| Render success | Every render writes its file. |
| Render messages | No render, STL or 3MF, prints a console line that is neither one of OpenSCAD's normal statistics lines nor exactly an expected note. A line holding an expected note and anything more fails. |
| Expected messages | Every note the policy expects appears. |
| Hard limits | Every reference meets the Gate 1 limits, measured from the required number of sampled points. A value that is not a number fails. |
| Drift | No reference metric is worse than its locked value by more than 0.002 mm, or 0.01 % of volume. |
| Mesh soundness | Every STL is watertight, consistently wound, of positive volume and one body, with every edge shared by exactly two faces and no duplicated facets. |
| Crossings | No two triangles that share at most one vertex cross each other by more than 0.001 mm. |
| Shape lock | Every STL the gate renders, reference or not, has the same vertices, by a digest, and the same volume within 0.01 mm3 as when the baseline was locked; the two are judged separately. This catches a feature that moves, goes missing or fuses into the wrong neighbour while the mesh stays valid and the Gate 1 limits still pass. `--quick` keeps the lock on the references. |
| 3MF coincident vertices | No 3MF export writes two separate vertices at identical coordinates. 3MF (3D Manufacturing Format) is a zipped mesh format that slicers read. |
| 3MF merges | Merging a 3MF export's vertices within 0.00001 mm, and within 0.0001 mm, leaves every edge shared by exactly two triangles, as a slicer that merges vertices on import would need. |
| Rejected sizes | Each value in the policy's list stops the render with its error, looked for anywhere in the console output, and writes no file; the two are judged separately. For each of the three sizes the list has a value just off a step, a value halfway between two steps, the step below the slider's minimum and the step above its maximum; and it has one value that is not a number. |
| Relock rules | A relock is refused from `--quick` or from another SCAD file, is never written over a failure, and needs `--accept-drift` for drift, a shape change or dropped coverage against the baseline it replaces; where that baseline has no entry, or there is no baseline, there is nothing to compare. A relock records the generator's digest in the baseline and writes `VERIFICATION.md`. |

### What the gate does not see

- Sizes it does not render. The gate renders the 14 references and the configurations in the policy; a fault that appears only at another size, such as a wrongly accepted value the rejected list does not hold, passes.
- Triangles that overlap while lying in one plane, such as a sliver folded back against its neighbour, and neighbours that share an edge, are not tested for crossing.
- Only the three sizes the policy lists are exported as 3MF.
- Whether the Customizer's descriptions and section titles say true things. The Customizer check is a scan of lines, not OpenSCAD's parser. It compares only the parameters' names, the sliders' ranges and the dropdowns' values. It does not read an assignment that follows a statement on its line, or one whose `=` is on a later line than its name, and it does not skip comments or strings when it looks for assignments and block comments.

### How the gate is proven

- `gate_test.py` runs in seconds and never starts OpenSCAD, though the tools it imports need OpenSCAD's path and the reference folder configured. It compares the policy with a literal copy. It tests the hard limits, the drift tolerances, the shape lock's volume tolerance, the crossing limit, the sample count and the 3MF counts at their limits, and each 3MF merge distance at 0.999 and 1.001 of it. Where a check rests on two conditions, as the shape lock and the rejected sizes do, the tests run every combination of them. It drives every check in the list through the gate's run with stand-in renders, and checks that a clean run rendered and examined everything the policy lists. The stand-ins record the SCAD file, the output file, the parameters and the expected notes of each render, and the files measured and examined, and the tests check them. The real steps are tested separately on small inputs: the render function against a stand-in for OpenSCAD, the baseline and report files in a scratch folder, and the command line through `main`.
- `mutation_test.py` disables each check in the list in a copy, one at a time, and checks that `gate_test.py` fails; it also breaks the measuring tools and the real steps. It fails when any mutation survives.
- `selftest.py` runs both and then the gate against a known-bad version of the generator kept in `analysis/fixtures/`. That run must fail, and must report each failure `selftest.py` lists, so a check in that list that stopped working on real renders is noticed. The fixture cannot show the Unit tests, Customizer, Generator unchanged, Reference coverage, Configuration coverage, Render success and Relock rules rows; those rest on `gate_test.py`.

## Gate 2: adversarial review

Reviewers are subagents with fresh context, four per round.

- **R1** reproduces the Gate 1 metrics from scratch with its own code.
- **R2** audits feature meaning with its own sections and queries: what each part of the geometry is for, and whether the generator gets it right.
- **R3** fuzzes configurations away from the references, looking for broken meshes and implausible geometry.
- **R4** reviews what is signed off besides the geometry: the Customizer text, the shell's row in `README.md`, the headline of each `DEVIATIONS.md` entry, `VERIFICATION.md` against the committed generator, and this document's account of the gate. It also tries to get a broken generator past the gate with real edits to a copy of the SCAD.

R1 to R3 are briefed to disprove the match. They receive the generator, the reference files and the limits, but not the implementation notes, the deviation claims or `VERIFICATION.md`.

Every reviewer grades each finding:

- **S1, blocking.** One of three kinds. A geometry fault: a reference over a Gate 1 limit, an export at an accepted size that fails the mesh soundness or crossing check, or a feature that stops a drawer, clip or rail from fitting. A demonstrated bypass: a concrete edit to the SCAD that the gate passes although it has a defect of a kind the list above says the gate catches. Or a false statement in something that is signed off, as listed under R4.
- **S2, fix.** A wrong secondary number or wording in evidence text, an undefined term, an artifact at a new size in a class a `DEVIATIONS.md` entry already covers, a break to the gate's own code that its unit tests miss, whether or not it turns a check off, or a judgement call about a size MultiBuild does not publish, which goes to the owner as a decision.
- **S3, log.** Style, wording in `docs/lessons-learned.md` unless it is false about a tool, and a risk nobody has reproduced.

A round is clean when no reviewer reports an S1 finding. S2 findings are fixed in the next commit, and one reviewer then checks only that commit's diff. S3 findings are recorded with a reason and need no action. The pull request keeps the list of findings and what was done about each.

Review ends when two consecutive rounds are clean and a reviewer countersigns `DEVIATIONS.md` after checking every entry against its own measurements. The final file must then render cleanly with valid Customizer syntax.

## Sign-off

After the reviewers countersign, Tim reviews the generator and signs off. The pull request merges only after that.

## Per-part documents

- `REVERSE-ENGINEERING.md` records the measured construction of the originals.
- `DEVIATIONS.md` lists every known difference from the originals, with its evidence.
- `VERIFICATION.md` holds the Gate 1 measurements, tied to the generator's SHA-256 digest. The shell's gate writes it when it locks the baseline.
