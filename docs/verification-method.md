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
  - [The gate's own tests](#the-gates-own-tests)
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

This list is closed: `regress.CHECKS` holds the same names, and `analysis/policy.py` holds the limits and lists. Each row states a comparison the gate makes on its renders of the references, configurations and rejected sizes the policy lists. A row claims nothing about any other size, and nothing about what the comparison implies. Adding or removing a check means changing this document, and is the owner's decision.

| Check | What is compared |
|---|---|
| Unit tests | `gate_test.py` must exit 0 before anything is rendered. A gate run started from inside the unit tests that another gate run started counts them as failed. |
| Locked generator | The generator's SHA-256 digest, taken with each CR LF pair turned into LF, must equal the digest in `baseline.json` and the digest in `VERIFICATION.md`. A relock does not make this comparison. |
| Generator unchanged | The same digest, taken again at the end of the run, must equal the one taken at the start. |
| Reference coverage | Every reference in the policy's list must have its file. In a plain run the references in the baseline must also be exactly that list. |
| Configuration coverage | In a plain run the configurations in the baseline must be exactly the policy's list of configurations. |
| Render success | Each render of a reference or a configuration, STL or 3MF, must write its file. |
| Console output | For each such render, the text OpenSCAD writes to standard error must be exactly the notes the policy expects of that configuration (none for a reference), each echoed on its own line and in order, followed by one line matching each pattern of `policy.CONSOLE_STATISTICS`, in order, with nothing before, between or after. The patterns fix every word of OpenSCAD's statistics lines and leave their numbers free. Standard output must be empty. The text is compared whole, after each CR LF pair is turned into LF. |
| Hard limits | Each reference's four measures must be within the Gate 1 limits: the bounding box and volume differences, the 99th percentile of the distances from 50,000 points sampled on each surface to the other, and the largest distance from those points and from every vertex. A measure that is not a number fails, and so does any other number of sampled points on either surface. |
| Drift | In a plain run, each reference's four measures must be no more than 0.002 mm above the baseline's, or 0.01 for the volume percentage. A measure missing from the reference's baseline entry fails. |
| Mesh soundness | Each STL's audit must show a watertight, consistently wound mesh of positive volume and one body, with every edge on exactly two faces and no facet written twice. |
| Crossings | In each STL, the deepest crossing between two triangles that share at most one vertex must be no more than 0.001 mm. |
| Shape lock | In a plain run, the SHA-256 digest of each STL's distinct vertex coordinates must equal the baseline's, and its volume must be within 0.01 mm3 of the baseline's. An STL whose baseline entry is missing, empty or not a table of values fails. |
| 3MF coincident vertices | Each 3MF export must have no two vertices at identical coordinates. 3MF (3D Manufacturing Format) is a zipped mesh format that slicers read. |
| 3MF merges | Each 3MF export, with vertices merged when they are within 0.00001 mm of each other, chains of such vertices included, and again within 0.0001 mm, must have every edge on exactly two triangles. |
| Rejected sizes | Each render with a value from the policy's list of rejected sizes must write no file, and its console output must contain the policy's error text for that value in quotation marks. |
| Relock rules | `--update-baseline` is refused together with `--scad`. It writes `baseline.json`, with the generator's digest, and `VERIFICATION.md` only when the run has no failure. Without `--accept-drift`, drift, a changed shape and a dropped reference or configuration, each measured against the entries of the baseline being replaced, are failures; a reference or configuration that baseline has no entry for is not compared. |

### What the gate does not see

- Sizes it does not render. A fault that appears only at another size passes, and so does a wrongly accepted value that is not in the list of rejected sizes.
- The Customizer text: the slider and dropdown notes, the section titles and the descriptions. The gate does not read them. The policy records the ranges the generator is meant to accept, and the gate tests those only through the rejected sizes and through configurations at both ends of each range.
- A change to an STL's faces that leaves every vertex where it was, the volume within 0.01 mm3 and the mesh sound; on a reference, also the four measures within their limits and drift.
- Triangles that overlap while lying in one plane, such as a sliver folded back against its neighbour, and neighbours that share an edge, are not tested for crossing. Nor is a pair counted when one passes through the other only within 0.0000001 mm of a corner of the pierced triangle, or only at an end of the piercing edge.
- Whether a reference file holds MultiBuild's original: the gate looks only for a file of the expected name and measures against what it holds.
- A rejected render's console output is searched for its error text, not compared whole, and its standard output is not looked at.
- Only the three sizes the policy lists are exported as 3MF.

### The gate's own tests

- `gate_test.py` runs the gate's decisions and tools on small inputs and drives `regress.run` with stand-in steps from a table of faults.
- `mutation_test.py` applies each break in its list to a copy of the gate's code and requires `gate_test.py` to fail.
- `selftest.py` runs both, then runs the gate against a known-bad version of the generator kept in `analysis/fixtures/`, and requires that run to fail with each failure line `selftest.py` lists.

This section describes what the scripts do. It is not part of what is signed off.

## Gate 2: adversarial review

Reviewers are subagents with fresh context, four per round.

- **R1** reproduces the Gate 1 metrics from scratch with its own code.
- **R2** audits feature meaning with its own sections and queries: what each part of the geometry is for, and whether the generator gets it right.
- **R3** fuzzes configurations away from the references, looking for broken meshes and implausible geometry.
- **R4** reviews what is signed off besides the geometry: the Customizer text, the shell's row in `README.md`, the headline of each `DEVIATIONS.md` entry, `VERIFICATION.md` against the committed generator, and this document's account of what the gate checks and what it does not see. It also tries to get a broken generator past the gate with real edits to a copy of the SCAD. It does not make breaks to the gate's own code: a gap found in the gate's own tests goes to a follow-up change.

R1 to R3 are briefed to disprove the match. They receive the generator, the reference files and the limits, but not the implementation notes, the deviation claims or `VERIFICATION.md`.

Every reviewer grades each finding:

- **S1, blocking.** One of three kinds. A geometry fault: a reference over a Gate 1 limit, an export at an accepted size that fails the mesh soundness or crossing check, or a feature that stops a drawer, clip or rail from fitting. A demonstrated bypass: a concrete edit to the SCAD that the gate passes although it has a defect of a kind the list above says the gate catches. Or a false statement in something that is signed off, as listed under R4.
- **S2, fix.** A wrong secondary number or wording in evidence text, an undefined term, an artifact at a new size in a class a `DEVIATIONS.md` entry already covers, a break to the gate's own code that its unit tests miss, whether or not it turns a check off, or a judgement call about a size MultiBuild does not publish, which goes to the owner as a decision.
- **S3, log.** Style, wording in `docs/lessons-learned.md` unless it is false about a tool, and a risk nobody has reproduced.

A reviewer's result stands for as long as the generator's digest, as the gate takes it, is unchanged: R1, R2 and R3 do not rerun for a commit that leaves it unchanged.

A round is clean when no reviewer reports an S1 finding. S2 findings are fixed in the next commit, and one reviewer then checks only that commit's diff. S3 findings are recorded with a reason and need no action. The pull request keeps the list of findings and what was done about each.

Review ends when two consecutive rounds are clean and a reviewer countersigns `DEVIATIONS.md` after checking every entry against its own measurements. The final file must then render cleanly with valid Customizer syntax.

## Sign-off

After the reviewers countersign, Tim reviews the generator and signs off. The pull request merges only after that.

## Per-part documents

- `REVERSE-ENGINEERING.md` records the measured construction of the originals.
- `DEVIATIONS.md` lists every known difference from the originals, with its evidence.
- `VERIFICATION.md` holds the Gate 1 measurements, tied to the generator's SHA-256 digest. The shell's gate writes it when it locks the baseline.
