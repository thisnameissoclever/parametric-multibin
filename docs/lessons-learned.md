# Lessons learned

Mistakes and near misses from building the generators, each with its cause, the rule that prevents it, and how to check the rule is being followed. Read this before starting work on a part.

## Contents

- [Random sampling hides edge-shaped deviations](#random-sampling-hides-edge-shaped-deviations)
- [A valid mesh can still be the wrong shape](#a-valid-mesh-can-still-be-the-wrong-shape)
- [A gate that has never failed is unproven](#a-gate-that-has-never-failed-is-unproven)
- [Evidence scripts can lie](#evidence-scripts-can-lie)
- [Faces that only touch break the export](#faces-that-only-touch-break-the-export)
- [Gate features on layout units, not millimetres](#gate-features-on-layout-units-not-millimetres)
- [Size helper geometry from the model](#size-helper-geometry-from-the-model)
- [Measure the original before changing a deliberate deviation](#measure-the-original-before-changing-a-deliberate-deviation)
- [Parallel runs need a parent that waits](#parallel-runs-need-a-parent-that-waits)
- [Check render messages by content, not by prefix](#check-render-messages-by-content-not-by-prefix)
- [Apply a cut where its feature is defined](#apply-a-cut-where-its-feature-is-defined)
- [Overlap a loft by exactly its end slab](#overlap-a-loft-by-exactly-its-end-slab)
- [Test a gate's limits, not only its failures](#test-a-gates-limits-not-only-its-failures)
- [Measure geometry at full export precision](#measure-geometry-at-full-export-precision)

## Random sampling hides edge-shaped deviations

**What happened:** on the two 3 LU wide divided drawers, 50,000 random surface samples reported a worst deviation of 0.010 mm. The real worst case was 0.133 mm, along a thin strip.

**Cause:** samples are spread by area, and a deviation along an edge has almost no area, so few samples land on it.

**Rule:** report the maximum from a sweep of every vertex, in both directions, alongside the sampled statistics.

**Check:** the comparison harness prints an all-vertices maximum for each direction.

## A valid mesh can still be the wrong shape

**What happened:** at an off-grid height of 0.75 LU, an early drawer built a label frame that fused into the pull lip. The mesh was watertight, single-bodied and had clean edges, so the soundness checks passed.

**Cause:** topology checks only prove the solid is closed, not that it has the intended shape.

**Rule:** for configurations without a reference, lock their bounding box and volume in the regression baseline, and treat any change as a failure until it is shown to be intended.

**Check:** the soundness section of `regress.py` prints the bounding box and volume for each configuration. The drawer's gate flags a change beyond 0.001 mm on the bounding box or 0.5 mm3 of volume; the shell's flags any change to an exact digest of the triangles, which also catches a feature that moves without changing the volume.

## A gate that has never failed is unproven

**What happened:** the first self-test of the drawer regression gate passed against a known-bad version. It had been run with `--quick`, which skips the soundness section, the only section that could see that version's defects.

**Cause:** the defects lived in configurations with no reference, and the test skipped exactly those.

**Rule:** prove each gate by running it, in full, against a known-bad fixture, and confirm it fails for the expected reasons.

**Check:** `analysis/fixtures/` holds the known-bad version; `regress.py --scad <fixture>` must exit with status 1. For the shell, `selftest.py` also checks that each section of the gate reports the failure the fixture should cause.

## Evidence scripts can lie

**What happened:** a probe script tested `len(sys.argv) > 8` where it needed `>= 8`, so it ignored the requested box and reported that no samples fell inside it. That false reading went into `DEVIATIONS.md` and was caught by a reviewer.

**Cause:** the script accepted a partial argument list silently.

**Rule:** probe scripts reject incomplete arguments with an error. Re-run every evidence command, exactly as written, before citing its output.

**Check:** reviewers re-run the evidence commands in `DEVIATIONS.md` from the stated working directory.

## Faces that only touch break the export

**What happened:** a corner brace whose face met the wall top exactly produced duplicated facets and edges shared by four faces. The defect appeared only at some depth and height combinations, including 1x3x1.

**Cause:** OpenSCAD's geometry kernel, CGAL, handles coincident faces and tangent contact poorly in boolean operations.

**Rule:** where two solids join, overlap them by a fraction of a millimetre on a shared plane instead of letting them meet face to face. Sweep many sizes, not only the reference sizes.

**Check:** `analysis/manifold_grid.py` and the soundness list in `regress.py`.

## Gate features on layout units, not millimetres

**What happened:** feature switches written as millimetre thresholds, such as "label only if the outer height is at least 30 mm", let off-grid heights between 0.74 and 1.0 LU build a label frame that collided with the lip.

**Cause:** the designer's real rule was "at least 1 LU tall", and the millimetre threshold only matched it at on-grid heights.

**Rule:** express feature conditions in the unit the original design uses.

**Check:** the soundness list includes an off-grid height.

## Size helper geometry from the model

**What happened:** a half-space cutter built from a fixed 600 mm cube silently truncated the corner chamfer on drawers taller than about 430 mm.

**Cause:** the helper's size was a guess, not derived from the model.

**Rule:** size cutters and other helper solids from the model's own dimensions.

**Check:** the soundness list includes a tall configuration.

## Measure the original before changing a deliberate deviation

**What happened:** a change meant to make a fillet cut stop at the divider faces raised the sampled worst deviation from 0.010 mm to 0.133 mm in both directions, and was reverted.

**Cause:** the original's cut actually stops at a different boundary; the change was made from an assumption about intent rather than from a measurement.

**Rule:** before changing geometry that `DEVIATIONS.md` explains, measure the original at that spot.

**Check:** each deviation entry carries the command that measures it.

## Parallel runs need a parent that waits

**What happened:** three comparison runs were started as background subshells from a Git Bash command that then exited. The tool reported the command as finished, the logs were still empty, and a second launch started duplicate runs that truncated the first runs' logs and raced them for the same output files.

**Cause:** on Windows, Git Bash subshells started with `&` keep running after their parent exits, so the parent's exit says nothing about the runs it started.

**Rule:** start parallel runs from one command that ends with `wait`, and before relaunching, list the running `openscad.exe` and `python.exe` processes to find survivors. To stop one run, match its own `python.exe` command line: the parent `bash.exe` carries the text of every run it started, so matching on that text also stops runs that should continue.

**Check:** `Get-CimInstance Win32_Process -Filter "Name='openscad.exe'"` lists one process per expected run, each with a different output file.

## Check render messages by content, not by prefix

**What happened:** every shell render printed `PolySet has nonplanar faces. Attempting alternate construction`, from the twisted faces of the thread polyhedron. The comparison harness only reported lines containing `WARNING` or `ERROR`, so the notice went unseen until a reviewer found it.

**Cause:** OpenSCAD 2021.01 prints that notice without a `WARNING` prefix.

**Rule:** list the render messages that mean a render is not clean by their content, and fail the regression gate on any of them.

**Check:** `render_problems()` in the shell's `analysis/compare.py` matches `nonplanar` as well as `WARNING` and `ERROR`, and `regress.py` fails on any match.

## Apply a cut where its feature is defined

**What happened:** on shells whose width or front-to-back size ends in a half LU, the rail channel stopped short of the base wherever it ran over a half-size pad. A Topped Rail channel was then closed at both ends, so no rail could slide in. The meshes were sound and every reference passed, because no reference has a half-LU pad under a channel.

**Cause:** the channel's cut through the pad's foot was made inside the whole-pad builder, so the separate half-pad builder never made it.

**Rule:** make a cut that belongs to a wall feature once, from that feature's own placement, across everything it passes through, rather than inside one of several builders for the parts it crosses.

**Check:** the shell's `pads()` subtracts `channels_low()` from all pads together, and the soundness list in `regress.py` includes half-LU shells with rail channels.

## Overlap a loft by exactly its end slab

**What happened:** after an unrelated change, the 3 x 2 x 3 Topless shell exported with an edge shared by four triangles, enclosing a void 0.009 mm thick inside one pad's central pocket. Separately, a reviewer found broken pocket slits on shells 7 LU or more front to back.

**Cause:** the pocket was built as a prism, a loft made as the hull of two 0.001 mm slabs, and another prism that overlapped the loft by 0.01 mm. Over that overlap the loft was still narrower than the prism, which left a ledge 0.01 mm wide. In the second case, slit ends lay exactly on the pocket's sides. OpenSCAD's internal result was valid in both cases, but its export closed these near-coincident features into voids at some positions and not others.

**Rule:** a solid that continues a loft overlaps it by exactly the loft's end slab, so the overlapping sections are identical; and a cut that would end exactly on another cut's face stops a small, stated distance short of it.

**Check:** the shell generator's `slab` constant sets every thin hull slab and every overlap with a loft, and the soundness list in `regress.py` includes 1 x 7 x 1 and 12 x 1 x 1 shells, which exported broken slits before the change.

## Test a gate's limits, not only its failures

**What happened:** the shell's gate passed a version whose half-pad clip pockets had moved 1 mm, because its checks on sizes without a reference compared only bounding box and volume. Its self-test could not have noticed a loosened tolerance either: the known-bad fixture's faults were hundreds of times over every limit.

**Cause:** the gate was proven only end to end, against one fixture with large faults, and its locked values were proxies for the shape rather than the shape.

**Rule:** keep each gate decision in a small function and test it at its limit, just under and just over; and for configurations without a reference, lock an exact digest of the geometry rather than a few measures of it.

**Check:** the shell's `analysis/gate_test.py` runs in about a second and fails if any limit moves or any decision changes; `selftest.py` runs it before the end-to-end run against the fixture.

## Measure geometry at full export precision

**What happened:** a new check for triangles crossing each other failed on long shells, with crossings 0.0028 mm deep. The geometry was sound: OpenSCAD 2021.01's default ASCII STL keeps six significant digits, so beyond 100 mm from the origin its coordinates are rounded to 0.001 mm, and that rounding pushed vertices through neighbouring faces.

**Cause:** the harness measured the export format's rounding as if it were the generator's geometry.

**Rule:** render for measurement with `--export-format binstl`, which keeps 32-bit coordinates, and set geometric limits above that format's rounding at the largest size the generator makes.

**Check:** `EXPORT_FORMAT` in the shell's `analysis/compare.py` is used by every render in the harness, and `gate_test.py` checks it.
