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

## Random sampling hides edge-shaped deviations

**What happened:** on the two 3 LU wide divided drawers, 50,000 random surface samples reported a worst deviation of 0.010 mm. The real worst case was 0.133 mm, along a thin strip.

**Cause:** samples are spread by area, and a deviation along an edge has almost no area, so few samples land on it.

**Rule:** report the maximum from a sweep of every vertex, in both directions, alongside the sampled statistics.

**Check:** the comparison harness prints an all-vertices maximum for each direction.

## A valid mesh can still be the wrong shape

**What happened:** at an off-grid height of 0.75 LU, an early drawer built a label frame that fused into the pull lip. The mesh was watertight, single-bodied and had clean edges, so the soundness checks passed.

**Cause:** topology checks only prove the solid is closed, not that it has the intended shape.

**Rule:** for configurations without a reference, lock their bounding box and volume in the regression baseline, and treat any change as a failure until it is shown to be intended.

**Check:** the soundness section of `regress.py` prints the bounding box and volume for each configuration and flags any change.

## A gate that has never failed is unproven

**What happened:** the first self-test of the drawer regression gate passed against a known-bad version. It had been run with `--quick`, which skips the soundness section, the only section that could see that version's defects.

**Cause:** the defects lived in configurations with no reference, and the test skipped exactly those.

**Rule:** prove each gate by running it, in full, against a known-bad fixture, and confirm it fails for the expected reasons.

**Check:** `analysis/fixtures/` holds the known-bad version; `regress.py --scad <fixture>` must exit with status 1.

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

**Rule:** start parallel runs from one command that ends with `wait`, and before relaunching, list the running `openscad.exe` and `python.exe` processes to find survivors.

**Check:** `Get-CimInstance Win32_Process -Filter "Name='openscad.exe'"` lists one process per expected run, each with a different output file.
