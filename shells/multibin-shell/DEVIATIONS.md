# DEVIATIONS - known differences between the remake and MultiBuild's shells

This file lists every known difference between `MultiBin Shell - Parametric.scad` and MultiBuild's shell STL files, and every rule the generator applies where MultiBuild publishes no example. A difference under 0.001 mm has no entry of its own. Such differences arise, for example, where a constant in the generator is a reference dimension rounded to 0.001 mm: the outer corner chamfer leg (`c_out`) is 8.737 where the references have 8.7365, which puts the shell's outer corner faces 0.0003 mm inside the references'. Sizes are in LU, MultiBoard's 50 mm layout unit, written width x front-to-back x height as printed.

Each entry gives the difference and its size, its cause, why it stays, and one check. The checks run from the `analysis` folder with the repository's Python environment, `..\..\..\.venv\Scripts\python.exe`, written below as `python`. `python compare.py KEY` renders a reference configuration to `.local-build\out\shell\KEY.stl` at the repository root, which is `..\..\..\.local-build\out\shell\KEY.stl` from the `analysis` folder, and prints how far it is from the reference. The reference files live in the folder that `local-paths.json` names for `shell` (see `tools/mbpaths.py`).

Entries starting with M are measured surface differences, Q entries are quirks of the originals that the generator reproduces, and P entries are rules for configurations with no original.

## Contents

- [M1. Faceting of round features, up to 0.019 mm](#m1-faceting-of-round-features-up-to-0019-mm)
- [M2. Mesh artifacts](#m2-mesh-artifacts)
- [M3. Pocket ceiling slits stop 0.01 mm short](#m3-pocket-ceiling-slits-stop-001-mm-short)
- [M4. Seam slots' inner chamfer starts 0.002 mm deeper](#m4-seam-slots-inner-chamfer-starts-0002-mm-deeper)
- [Q1. Short seam groove in a Simple wall's partial top band](#q1-short-seam-groove-in-a-simple-walls-partial-top-band)
- [P1. Half-LU cells](#p1-half-lu-cells)
- [P2. A different wall kind on each side](#p2-a-different-wall-kind-on-each-side)
- [P3. Sizes beyond the published shells](#p3-sizes-beyond-the-published-shells)
- [P4. Which floor gap runs unbroken](#p4-which-floor-gap-runs-unbroken)

## M1. Faceting of round features, up to 0.019 mm

**Difference.** The generator builds each threaded hole, its thread and its entry cone with 32 facets per turn (`thr_steps`); the references are faceted more finely. At the holes, vertices of one mesh sit up to 0.019 mm from the other's surface, which is the largest difference on every reference (the all-vertices maximum in `VERIFICATION.md`). The rounded heads of the side clip pockets, radius 2.25 mm, are built with 32 facets too (`arc_fn`) and differ by up to 0.011 mm.

**Cause.** A chord across one facet sits r (1 - cos(180 / 32)) inside the true circle: 0.017 mm at the thread's radius of 3.5 mm, and 0.011 mm at 2.25 mm. On the thread the largest distances are 0.002 mm more than that chord figure; what adds them has not been isolated.

**Left as is.** Finer facets would slow every render for a difference under a tenth of a 0.2 mm print layer. Observed 2026-10-12 with OpenSCAD 2021.01 on a Windows 11 desktop running other renders at the same time: a 1 x 1 x 1 shell took about 24 s to render with 32 facets per turn and about 37 s with 64.

**Check.** After `python compare.py T212`, `python worst_points.py T212 ..\..\..\.local-build\out\shell\T212.stl` lists the worst points in each direction: the render's vertices at 0.0168 and the reference's at 0.0188 are beside threaded holes, and the reference's at 0.0187 are slit ends of side clip pockets (M3). Adding `--away-from-holes --below 0.011` lists the render's slit ends, at 0.0100, and the reference's vertices on the pocket heads, at 0.0108.

## M2. Mesh artifacts

**Difference.** The generator's exports contain small artifacts that the references do not. None changes the shape by more than 0.001 mm, and every edge stays shared by exactly two triangles.

- Zero-area triangles, whose three corners lie on one line, where a face's edge meets a vertex of a neighbouring face.
- Slivers and pairs of separate vertices less than 0.0001 mm apart, where the edges of two cuts meet at almost the same point. Some slivers fold back against a neighbouring triangle. Far from the origin the rounding of coordinates on export can turn a zero-area triangle into such a fold, about 0.0001 mm2 in area or less. Both the binary STL and the 3MF export (3D Manufacturing Format, a zipped mesh format that slicers read) keep at most 24 significant binary digits of each coordinate, so neighbouring values are about 0.00006 mm apart at 550 mm from the origin. The 3MF export of a shell 12 LU wide has two folds in each pad of its last column, at z 3.2 around x 550, and the binary STL of the 12 x 1 x 1 shell has the same two.
- A step 0.001 mm tall where a loft (a solid that blends one cross-section into another, such as a chamfer) meets the solid that continues it.
- Pairs of triangles that touch, or cross each other by less than 0.0001 mm.

OpenSCAD 2021.01 also cannot use an exported shell in further boolean operations: the operation stops with an assertion from CGAL, its geometry library, while the same operation on a reference file only warns. The cause within the mesh has not been isolated.

**Cause.** How OpenSCAD 2021.01 splits faces into triangles and rounds coordinates on export, and the generator's lofts, which are built from end slabs 0.001 mm thick (`slab`; see the lesson on loft overlaps in `docs/lessons-learned.md`).

**Left as is.** The generator cannot control how OpenSCAD triangulates and rounds its output, and the 0.001 mm steps are the price of a loft construction that has exported a sound mesh at every size rendered so far. A slicer may report the zero-area triangles as degenerate facets; how each slicer treats them has not been tested.

**Check.** After `python compare.py T111`, `python export_check.py ..\..\..\.local-build\out\shell\T111.stl` counts the zero-area triangles, close vertex pairs and crossing pairs in the render; the same command on the 1x1x1 Topped Rail reference reports none. The gate (`regress.py`) fails any render with a crossing deeper than 0.001 mm, and exports three sizes as 3MF to check that merging close vertices leaves every edge shared by two triangles. For the boolean operation, render `intersection() { import(f); translate([-30, -30, 0]) cube([60, 60, 3]); }` with `-D f=` set to the absolute path of `T111.stl`.

## M3. Pocket ceiling slits stop 0.01 mm short

**Difference.** Nine 0.1 mm slits cross the ceiling of each pad's central pocket, and three cross the ceiling of each side clip pocket. In the references they end on the pocket's sides; in the generator they stop 0.01 mm short. At the slit ends the references' vertices sit up to 0.014 mm from the render in the central pockets, and up to 0.019 mm in the side clip pockets, where the faceting of the pocket's head (M1) adds to the 0.01 mm.

**Cause.** With slit ends flush with the pocket's sides, OpenSCAD 2021.01's export sealed some central pocket slits into closed voids on pads far from the origin, on shells 7 LU or more front to back and on 12 LU wide shells. No export sealed a side clip pocket's slit, but those slits were built the same way, so they stop short as well.

**Check.** The gate renders 1 x 7 x 1 and 12 x 1 x 1 shells, which exported sealed slits before the change, and requires each to be one sound body. After `python compare.py T111`, `python worst_points.py T111 ..\..\..\.local-build\out\shell\T111.stl 6 --away-from-holes` lists the side clip pocket slit ends first.

## M4. Seam slots' inner chamfer starts 0.002 mm deeper

**Difference.** In the references each seam slot widens at 45 degrees from 6 x 2 at depth 2.6, measured from the outer face, to the inner face at depth 3.0. The generator starts the widening at depth 2.602 and keeps its end, so the slot's opening at the inner face measures 6.799 x 2.799 against the reference's 6.8 x 2.8, and the chamfer's surface lies at most 0.002 mm from the reference's.

**Cause.** Depth 2.6 is also the floor of the inner grooves, which are 0.4 deep. The slot is placed from the outer face and the grooves from the inner face, so with the chamfer's first edge in the grooves' floor plane the two met a rounding error apart. That left zero-width fins where the top seam slots cross the rim groove, and merging a 3MF export's vertices within 0.00001 mm folded those fins into edges shared by four triangles.

**Check.** The gate exports the 4 x 1 x 1 shell as 3MF and fails on any edge left shared by other than two triangles after the merge. `selftest.py` checks that this fails on the fixture, which starts the chamfer at 2.6.

## Q1. Short seam groove in a Simple wall's partial top band

**Quirk.** On a shell whose height is not a whole number of LU, the rim cuts the top 50 mm band short. In band b (counting from 0), a seam groove normally runs from z 13.3 + 50b to 7 below the top of the band or the rim. On the Topped Rail and Topless Rail 1x2x1.5 shells, the groove in the partial band therefore runs from z 63.3 to z 73.0. On the Simple Walls 1x2x1.5 shell the same groove starts 9.2 below the rim, at z 70.8, the height of the upper catch slots, and ends at z 73.0 as on the other two.

**Rule.** The generator reproduces the short groove on every Simple wall with a partial top band. The 1x2x1.5 shell is the only Simple Walls reference with a partial band, and only its two side walls have seams, so the rule rests on one example and is applied to the front and back walls by extension. The partial band is always 25 mm tall, because heights step in half LU.

**Check.** On the seam at y 25 of the +x side wall, whose inner face is at x 22: `python wall_depth.py S1215 +x 18 25 22 62 74` reports the recess from z 70.9 to 72.9, and the same command for `T1215` and `O1215` reports it from z 63.4 to 72.9.

## P1. Half-LU cells

MultiBuild publishes no shell whose width or front-to-back size ends in a half LU. For such a size the generator lays out whole 50 mm cells from the origin and then one 25 mm cell at the +x end or at the back (+y). The rule is the generator's own:

- **Pad.** The half cell's pad follows a whole pad's outline rules at its own size. Its threaded holes stay on the 25 mm grid, each corner has a corner clip pocket, and each 50 mm side has the mid-edge notch and, where it faces outward, the two side clip pockets.
- **Left out of the pad.** A 25 mm side has no notch and no side clip pockets: the notch is 8.0 mm wide at the lower edge of the pad's side face, where it is widest on that face, wider than the side's 7.7 mm flat part, and the pockets would run into the corner chamfers. The pad has no central pocket: across a 25 mm pad it would overlap a threaded hole or pass the pad's face. A shell 0.5 LU front to back has only half pads, so it has no central pocket at all.
- **Rail channel.** The half cell's stretch of wall has none: its flat outer face is 16.3 mm long, shorter than a channel bulge, which is 17 mm wide. A channel on a whole cell still runs down through the foot of the pad below it when that pad is a half pad; without that cut a Topped Rail channel would be closed at both ends.
- **Catch slots.** On every published shell the outermost catch slot of a wall ends where the flat inner face ends, so every inner corner has one. A half cell has no centre to place a pair of slots from, so the inner corner at its end gets one slot of the same 6 mm length, ending where the flat inner face ends, in every row. A side shorter than 1 LU is a half cell alone, with a flat inner face 7.9 mm long: its two corner slots would overlap, so each row is one recess along the whole flat face.
- **Seam features.** The floor bridge gap, the seam grooves and the seam slots follow every seam, including the one beside the half cell. On a Topless Rail wall the rim groove runs through the half cell, which has no channel to avoid.
- **Drawer.** The drawer generator counts its 50 mm height bands from the drawer's bottom, and a drawer's height runs front to back in the shell, so the 1 mm inward steps in its side walls at each band boundary (its jogs) line up with the shell's seam slots when the drawer's bottom faces -y. Across the width the drawer centres its cells while the shell's half cell sits at +x; the drawer is held by detent bumps at its corners, which snap into the shell's corner slots wherever its cells fall.
- **Magnet pockets.** The central pocket of each whole pad has the same outline as the magnet pocket in the back wall of a magnet drawer from the drawer generator, so the two appear to be partners. At half-LU widths they are offset by 12.5 mm and overlap by only 4.5 mm of their 17 mm width, because the drawer centres its magnet pockets while the shell lays its cells out from the -x end. `docs/roadmap.md` lists aligning them as drawer work.

**Check.** The gate renders half-LU configurations with each wall kind, and requires each to be one sound body whose vertices and volume match the locked baseline. To see the corner catch slot and the channel through a half pad's foot, render a 2.5 x 1.5 x 2 shell from the repository root with `& "C:\Program Files\OpenSCAD\openscad.com" -o .local-build\out\shell\h.stl --export-format binstl -D width_lu=2.5 -D height_lu=1.5 -D depth_lu=2 "shells\multibin-shell\MultiBin Shell - Parametric.scad"`. Then, from the `analysis` folder, `python wall_depth.py ..\..\..\.local-build\out\shell\h.stl -y 88 -15 -22 10 20` shows the slot on the front wall's inner face at x 88, 0.4 deep, and `python wall_depth.py ..\..\..\.local-build\out\shell\h.stl -x 105 0 100 3.6 7 0.3` shows the right wall's channel 2.2 deep from z 4.8 upward, over a half pad.

## P2. A different wall kind on each side

MultiBuild publishes each shell with one wall kind on all four sides. The generator takes a kind for each side. Three features follow the kind of the face they belong to: the rail channel and its foot, the rim groove, and the seam groove in a partial top band (Q1). Everything else, including the catch slots, the seam slots, the corners and the base, is the same on all three published kinds. A pad side facing outward carries its side clip pockets on every wall kind.

**Check.** The gate matches all three kinds against their references with one catch slot, corner and base construction, and renders shells with Topped, Topless and Simple sides together.

## P3. Sizes beyond the published shells

The generator accepts 1 to 12 LU of width (`width_lu`), 0.5 to 12 LU front to back (`height_lu`) and a drawer depth of 1 to 12 LU (`depth_lu`), in half-LU steps, to match the drawer generator. The drawer depth sets the shell's height as printed, at 50 mm per LU plus 5 mm. The features repeat on a fixed pitch: pads, channels, catch slots and seam features per 50 mm cell; one catch slot row and one seam groove per 50 mm band of height; and channel bulges and seam slots every 25 mm of height. The lowest catch slot row, the rim groove and the slot at each corner occur once. The reference shells reach 3 LU wide, 2 LU front to back and a drawer depth of 3.5 LU.

- **A shell 0.5 LU front to back** has no whole cell along its left and right walls, so they carry no channel, and all its pads are half pads. A Topped Rail or Topless Rail choice for those walls builds the same wall as Simple, and the generator prints a `NOTE` in OpenSCAD's console saying so; MakerWorld's Parametric Model Maker may not show that console.
- **Other sizes are rejected.** A value off the half-LU step, outside the range, or not a number stops the render with an error naming the parameter and the allowed values. A value within 0.0000005 LU of a half step counts as that step, to absorb rounding in the number passed in; the error shows a rejected value to six significant digits. The shell is built only from 25 mm and 50 mm cells, so it cannot take an off-step size as given, and the drawer generator builds a drawer at any off-step size, so a shell rounded to another size would not match the drawer made with the same numbers.
- **Render time** grows with the number of cells and the height; `VERIFICATION.md` records it for each reference. Observed 2026-10-09 with the generator at commit 19f1615 and OpenSCAD 2021.01, on a Windows 11 desktop with 24 logical processors running other renders at the same time: a 6 x 6 x 1 shell took 1629 s to render and write both an STL and a 3MF, 698 s of it writing the 3MF. MakerWorld's Parametric Model Maker may stop a render that runs too long; its limit is not known here, and `docs/roadmap.md` lists testing it.

**Check.** The gate renders 4 LU and 12 LU wide shells, shells with a drawer depth of 4 LU and 12 LU, 7, 7.5 and 12 LU front-to-back shells and a shell 0.5 LU front to back. For each of the three sizes it requires the render of a value just off a step, of a value halfway between two steps, of the step below the slider's minimum and of the step above its maximum to write no file and to print that value's error, and likewise the render of a width that is not a number.

## P4. Which floor gap runs unbroken

Between neighbouring pads the floor's underside steps up by 0.2 mm in a narrow gap. On the 3 x 2 x 3 references, the only ones with pads side by side in both directions, the gap between the two rows runs unbroken along the width, through the crossings, and the gaps between columns run only beside each pad's flat side, so they stop short of the crossings. Those shells are 3 LU wide and 2 LU front to back, so "the gap between rows runs unbroken" and "the gap along the longer side runs unbroken" describe them equally.

**Rule.** The generator runs the gap between rows unbroken at every size. The two readings differ only on a shell with at least two pads each way that is longer front to back than it is wide, and there by a 0.2 mm step on the underside of the floor.

**Check.** After `python compare.py T323`, the 3 x 2 x 3 Topped Rail render matches its reference within the limits; the gate locks the shape of a shell 2.5 LU wide and 7.5 LU front to back.
