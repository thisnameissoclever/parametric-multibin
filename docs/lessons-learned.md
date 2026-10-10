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
- [Prove a lock is repeatable before relying on it](#prove-a-lock-is-repeatable-before-relying-on-it)
- [Make meeting faces coincide exactly or not at all](#make-meeting-faces-coincide-exactly-or-not-at-all)
- [Read the whole diff of a scripted edit](#read-the-whole-diff-of-a-scripted-edit)
- [Test the real steps, not only their stand-ins](#test-the-real-steps-not-only-their-stand-ins)
- [Look past the largest difference](#look-past-the-largest-difference)
- [A mutation test needs passing tests to start from](#a-mutation-test-needs-passing-tests-to-start-from)

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

**Rule:** start parallel runs from one command that ends with `wait`, and before relaunching, list the running `openscad.exe` and `python.exe` processes to find survivors. To stop one run, match its own `python.exe` command line: the parent `bash.exe` carries the text of every run it started, so matching on that text also stops runs that should continue. Never run two jobs side by side that write the same output files, such as `compare.py` and `regress.py` on the same generator; chain them instead.

**Check:** `Get-CimInstance Win32_Process -Filter "Name='openscad.exe'"` lists one process per expected run, each with a different output file.

## Check render messages by content, not by prefix

**What happened:** every shell render printed `PolySet has nonplanar faces. Attempting alternate construction`, from the twisted faces of the thread polyhedron. The comparison harness only reported lines containing `WARNING` or `ERROR`, so the notice went unseen until a reviewer found it.

**Cause:** OpenSCAD 2021.01 prints that notice without a `WARNING` prefix.

**Rule:** treat every console line except the renderer's normal statistics as a render message, and fail the regression gate on any message that a configuration does not declare as expected.

**Check:** `render_problems()` in the shell's `analysis/compare.py` allows only OpenSCAD 2021.01's statistics lines, and `gate_test.py` checks that a nonplanar notice, a WARNING, an ECHO and an unknown line all count as messages.

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

**What happened:** the shell's gate passed a version whose half-pad clip pockets had moved 1 mm, because its checks on sizes without a reference compared only bounding box and volume. Its self-test could not have noticed a loosened tolerance either: the known-bad fixture's faults were two to fourteen times over the limits they tripped, so a tolerance loosened that far would still have passed.

**Cause:** the gate was proven only end to end, against one fixture with large faults, and its locked values were proxies for the shape rather than the shape.

**Rule:** keep each gate decision in a small function and test it at its limit, just under and just over; and for configurations without a reference, lock an exact digest of the geometry rather than a few measures of it.

**Check:** the shell's `analysis/gate_test.py` runs in about a second and tests each decision at its limit and the gate's whole run with stand-in renders; `analysis/mutation_test.py` breaks the gate one way at a time to show those tests notice, and `selftest.py` runs both before the end-to-end run against the fixture.

## Measure geometry at full export precision

**What happened:** a new check for triangles crossing each other failed on long shells from the generator of the time, with crossings 0.0028 mm deep. The geometry was sound: OpenSCAD 2021.01's default ASCII STL keeps six significant digits, so beyond 100 mm from the origin its coordinates are rounded to 0.001 mm, and that rounding pushed vertices through neighbouring faces.

**Cause:** the harness measured the export format's rounding as if it were the generator's geometry.

**Rule:** render for measurement with `--export-format binstl`, which keeps 32-bit coordinates, and set geometric limits above that format's rounding at the largest size the generator makes.

**Check:** `EXPORT_FORMAT` in the shell's `analysis/compare.py`; `gate_test.py` checks its value.

## Prove a lock is repeatable before relying on it

**What happened:** the shell's gate locked a digest of each test shape's triangles, after one check that two renders of one size matched. A reviewer then found that the gate failed the unchanged generator: for other sizes, OpenSCAD 2021.01 splits some flat faces into triangles differently from run to run, while writing the same vertices and the same volume.

**Cause:** repeatability was assumed from one example instead of measured across the configurations the lock covers.

**Rule:** before locking a value, render several configurations more than once and confirm the value repeats; lock only what repeats, here the sorted vertices and the volume.

**Check:** `gate_test.py` checks that the digest ignores how a face is split into triangles and changes when any one vertex moves 0.0001 mm.

## Make meeting faces coincide exactly or not at all

**What happened:** reviewers found two faults in the shell's 3MF export, which stores each vertex once. It wrote separate vertices at identical coordinates: about eleven pairs at every threaded hole, and one at an outer corner of half-LU shells. And where the top seam slots cross the inner rim groove it wrote zero-width fins, pairs of vertices a rounding step apart, which merging vertices within 0.00001 mm folds into edges shared by four triangles. A program that merges vertices by position on import would fold the mesh at either. The STL export hid both, because its rounding merged the points.

**Cause:** faces that should meet were built a hair apart. The holes' entry cones, threads and core cylinders were faceted at the same 32 angles, so their edges crossed at nearly the same points; and a half pad's corner face, built around the pad's own centre and then moved, missed the floor's corner face by rounding. The seam slot's inner chamfer started in the plane of the grooves' floor, 2.6 mm into the 3 mm wall, but the slot is placed from the outer face and the groove from the inner face, so the two planes differed by rounding.

**Rule:** where two faces should meet, build them from the same numbers in the same frame so they coincide exactly, as when the cone ends on the core's own polygon and a half pad is built in place. Where they should not meet, or are placed from different frames, keep them apart by well over the 0.0001 mm a merge on import may span, as the seam slot's chamfer now starts 0.002 mm past the groove floor.

**Check:** `regress.py` exports three sizes as 3MF and fails on any separate vertices at identical coordinates, and on any edge left shared by other than two triangles once vertices within 0.00001 or 0.0001 mm are merged; `export_check.py` reports both for any 3MF file.

## Read the whole diff of a scripted edit

**What happened:** a trial that turned the shell's threaded-hole entry cone by a quarter of a facet used a search-and-replace that also turned the core cylinder below it. The trial was undone for the cone only. The core stayed turned for two review rounds, so the cone and core no longer shared their ring of points, as the comment beside them said they did, and every hole had 8 small flat ledges where the two met.

**Cause:** the replacement pattern matched two lines, and the trial was undone by editing the one line in mind instead of restoring the file.

**Rule:** after a scripted edit, read the whole diff before running anything on it, and undo a trial by restoring the file from version control.

**Check:** `git diff` before each gate run lists every changed line; after a trial is undone, `git diff` shows nothing left of it.

## Test the real steps, not only their stand-ins

**What happened:** the shell gate's unit tests drive its whole run with stand-in steps in place of OpenSCAD and the mesh checks. A reviewer changed the real steps so that the mesh audit skipped the crossing check, the 3MF merge used one distance of its two, and every expected render message counted as seen; every unit test still passed.

**Cause:** a stand-in replaces exactly the code it stands for, so no test that runs through the stand-in can see that code.

**Rule:** for every stand-in, also test the real step it replaces on a small input that needs no slow tool, and move the logic out of slow steps into functions that can be tested that way.

**Check:** `gate_test.py`'s `test_real_steps` and its tests of `regress.render_result`, which interprets OpenSCAD's output; `mutation_test.py`.

## Look past the largest difference

**What happened:** a reviewer found the rail channel's bulges 0.021 mm short at each end on every reference, and the side clip pockets' heads faceted 0.011 mm off. Neither stood out in the gate's numbers: both were under the limits and were locked into the baseline as they were, and the threaded holes' faceting, 0.019 mm, sets every maximum. The bulges showed only in the 99th percentile distance and the volume difference, both of which fell on every reference with rail channels once they were fixed.

**Cause:** the bulge's measured half length, 3.521 mm, had been rounded to 3.5. It is 8.5 tan 22.5 degrees, the half side of a regular octagon 17 mm across its flats.

**Rule:** once the largest difference is explained, measure again without it and explain the next ones; and when a measurement lies close to a round number, look for the construction that gives it exactly.

**Check:** `worst_points.py KEY STL N --away-from-holes` lists the worst points with the threaded holes left out, and `--below D` lists those under a known larger difference; `DEVIATIONS.md` explains every point above 0.01 mm that they show on the references.

## A mutation test needs passing tests to start from

**What happened:** a new unit test of the shell gate failed because its tolerance was too tight, and the mutation test run alongside it reported every mutation caught. Each mutation had been "caught" by the test that already failed.

**Cause:** `mutation_test.py` counted any failing run of `gate_test.py` as a catch, without first checking that the unmutated tests pass.

**Rule:** run the tests once without any mutation and stop if they fail; count a mutation as caught only against a passing start.

**Check:** `mutation_test.py` runs `gate_test.py` on an unmutated copy first and exits 1, without testing any mutation, if that run fails.
