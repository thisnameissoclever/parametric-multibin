# DEVIATIONS - known differences between the remake and MultiBuild's shells

This file lists every known difference between `MultiBin Shell - Parametric.scad` and MultiBuild's shell STL files, and every rule the generator applies where MultiBuild publishes no example. Evidence commands run with `.venv\Scripts\python.exe` from the `analysis` folder. The reference files live in the folder that `local-paths.json` names for `shell` (see `tools/mbpaths.py`), and `python compare.py KEY` writes each render to `.local-build\out\shell\KEY.stl` at the repository root.

Entries starting with M are measured surface differences, Q entries are quirks of the originals that the generator reproduces, and P entries are rules for configurations with no original.

## Contents

- [M1. Faceting of the threaded holes, up to 0.02 mm](#m1-faceting-of-the-threaded-holes-up-to-002-mm)
- [M2. Zero-area triangles in OpenSCAD's export](#m2-zero-area-triangles-in-openscads-export)
- [M3. Pocket ceiling slits stop 0.01 mm short](#m3-pocket-ceiling-slits-stop-001-mm-short)
- [Q1. Short seam groove in a Simple wall's partial top band](#q1-short-seam-groove-in-a-simple-walls-partial-top-band)
- [P1. Half-LU cells](#p1-half-lu-cells)
- [P2. A different wall kind on each side](#p2-a-different-wall-kind-on-each-side)
- [P3. Sizes beyond the published shells](#p3-sizes-beyond-the-published-shells)

## M1. Faceting of the threaded holes, up to 0.02 mm

The generator builds each threaded hole, its thread and its entry cone with 32 facets per turn (`thr_steps`). A chord across one facet sits r (1 - cos(180 / 32)) inside the true circle, which is 0.017 mm at a radius of 3.5 mm. The references are faceted more finely, so their vertices and the render's vertices sit up to about 0.02 mm from each other's surfaces at the holes. These are the largest differences anywhere on the references.

Evidence: after `python compare.py T212`, `python worst_points.py T212 ..\..\..\.local-build\out\shell\T212.stl` lists the worst render vertex, 0.0168 mm from the reference surface, at (9.063, 12.744, 0.339) on the entry cone of the hole at (12.5, 12.5), and the worst reference vertex, 0.0188 mm from the render surface, at (15.815, -11.511, 5.200) at the top of the hole at (12.5, -12.5). `VERIFICATION.md` gives the all-vertices maximum for every reference.

Left as is. The threads dominate render time, and finer facets would slow every render for a difference under a tenth of a 0.2 mm print layer.

## M2. Zero-area triangles in OpenSCAD's export

Every exported shell contains some triangles whose three corners lie on one line, so they have no area; the references have none. OpenSCAD 2021.01 writes them where a face's edge meets a vertex of a neighbouring face: it splits that edge at the vertex and fills the split with a flat sliver triangle. They keep every edge shared by exactly two faces, so the mesh stays closed, and they do not change the shape. The drawer generator's exports contain them too.

Evidence: `python compare.py T111` prints the count for that render on a line starting `[T111] zero-area triangles in the export`, and `regress.py` checks that every render is watertight, one body, and has every edge shared by exactly two faces.

Left as is: the generator cannot control how OpenSCAD triangulates its output. A slicer may report these triangles as degenerate facets when it imports the file; how each slicer treats them has not been tested here.

## M3. Pocket ceiling slits stop 0.01 mm short

The nine 0.1 mm slits in the ceiling of each pad's central pocket run across the pocket's pointed prism. In the references they end on the prism's sides. In the generator they stop 0.01 mm short of those sides. With ends flush with the sides, OpenSCAD 2021.01's export sealed some slits into closed voids, with edges shared by four triangles, for pads at some positions far from the origin, for example on shells 7 LU or more front to back and on 12 LU wide shells.

Evidence: the soundness section of `regress.py` renders a 1 x 7 x 1 shell, which exported broken slits before the change, and checks that it is a single sound body. The 0.01 mm difference is below the faceting differences in M1.

## Q1. Short seam groove in a Simple wall's partial top band

On a shell whose height Z is not a whole number of LU, the top 50 mm band is cut short by the rim. On the Topped Rail and Topless Rail walls of the 1x2x1.5 shells, the vertical seam groove in that band runs from 13.3 above the band's base, z 63.3, to 7 below the rim, z 73.0. On the Simple Walls 1x2x1.5 shell the same groove starts 9.2 below the rim, at z 70.8, the height of the upper catch slots, and ends at z 73.0 as on the other two. Its section matches the other seam grooves: 0.4 deep, half width 0.5 at the floor, a 1:2 rise at the bottom and 45 degrees at the top.

Evidence, on the seam at y 25 of the +x side wall, whose inner face is at x 22:

- `python wall_depth.py S1215 +x 18 25 22 62 74` reports the recess from z 70.9 to 72.9, reaching full depth 0.4 between z 71.6 and 72.6.
- `python wall_depth.py T1215 +x 18 25 22 62 74` and the same command for O1215 report the recess from z 63.4 to 72.9.
- `python wall_depth.py S1215 -x -18 25 -22 62 74` shows the same short groove on the -x side wall.

The generator reproduces it for every Simple wall with a partial top band. The 1x2x1.5 shell is the only Simple Walls reference with a partial band, and only its two side walls have seams, so this rule rests on one example and is applied to the front and back walls by extension. The partial band is always 25 mm tall, because heights step in half LU, so the example covers every partial band height the generator can make. The groove is 0.4 mm deep and does not affect fit.

## P1. Half-LU cells

MultiBuild publishes no shell whose width or front-to-back size is a half LU. When a size ends in a half LU, the generator lays out whole 50 mm cells from the origin and then one 25 mm cell at the +x end or at the back. This rule is the generator's own:

- The half cell sits at the +x end and at the back (+y). The drawer generator counts its 50 mm height bands from the drawer's bottom, and a drawer's height runs front to back in the shell, so its side-wall jogs line up with the shell's seam slots when the drawer's bottom faces -y. A shell mounted with its print-orientation front (-y) down therefore takes the matching drawer upright, with the half band at the top of both. Across the width the drawer centres its cells, but no drawer feature engages a shell feature across the width.
- The half cell's pad has the same outline rules as a whole pad, at its own size. It carries the threaded holes that fall on the 25 mm hole grid (at the half cell's centre along its short direction) and the mid-edge notches on its 50 mm sides, but no notches on its 25 mm sides and no central pocket, corner pockets or side clip pockets. A notch is 9.2 mm wide at the face, wider than the 7.7 mm flat part of a 25 mm side, so on that side it would cut into both corner chamfers. Those pockets are laid out for a 50 mm pad. On a 25 mm side the flat part of the pad side spans only 3.85 mm each way from its middle, so side pockets centred 7.5 from the middle would run into the pad's corner chamfers. The central pocket's pointed end reaches 14.9 from the pad centre, past a pad face 9.3 from it. As a result, a shell's half-LU side cannot be clipped to a neighbouring shell at the base.
- No rail channel, and no catch slots, sit on the half cell's stretch of wall. A 17 mm channel with its bulges, and a pair of catch slots each reaching 16.4 mm from the cell centre, do not fit in 25 mm.
- A rail channel on a whole cell runs down through the foot of the pad below it even when that pad is a half pad, as on the right wall of a shell whose width ends in a half LU. Without that cut, a Topped Rail channel would be closed at both ends.
- Seam features follow every seam, including the seam next to the half cell: the floor bridge gap, the seam grooves and the seam slots.
- On a Topless Rail wall, the rim groove runs through the half cell, since it has no channel to avoid.

Evidence: the soundness section of `regress.py` renders half-LU configurations, including a Topless one and a Simple one, and checks that each is a single sound body with locked bounding box and volume. For the channel through a half pad's foot, render a 2.5 x 1.5 x 2 Topped shell to `h.stl` and run `python wall_depth.py h.stl -x 105 0 100 3.6 7 0.3` (right wall, over a half pad) beside `python wall_depth.py h.stl +y 0 -30 -25 3.6 7 0.3` (front wall, over a whole pad): both report a depth of 2.2 from z 4.8 upward.

## P2. A different wall kind on each side

MultiBuild publishes each shell with one wall kind on all four sides. The generator takes a kind for each side, and each feature follows the kind of the face it belongs to: the rail channel and its foot, the catch slots, the seam grooves and the rim groove. Features at the corners and in the base do not depend on the wall kind; the corner slots and corner faces measure the same on all three published kinds. A pad side facing outward carries its side clip pockets on every wall kind.

Evidence: `python compare.py` matches all three kinds with the same corner and base construction, and the soundness section of `regress.py` renders a shell with Topped, Topless and Simple sides together.

## P3. Sizes beyond the published shells

The generator accepts 1 to 12 LU of width (X, `width_lu`), 0.5 to 12 LU front to back (Y, `height_lu`) and 1 to 12 LU of height as printed (Z, `depth_lu`), in half-LU steps, to match the drawer generator. Every feature repeats on a fixed pitch: pads, channels, catch slots and seam features per 50 mm cell; catch slot rows and seam grooves per 50 mm band of height; and channel bulges every 25 mm of height. The reference shells reach 3 LU wide, 2 LU front to back and 3.5 LU tall.

A shell 0.5 LU front to back has no whole cells along Y, so its left and right walls carry no channels or catch slots, and all its pads are half pads.

The shell is built only from 25 mm and 50 mm cells, so a size typed in off the half-LU step is rounded to the nearest half LU, and a size below the slider's minimum is raised to it. Either adjustment prints a `NOTE` line in OpenSCAD's console. Without the rounding, a width of 1.3 LU would leave the base 9.2 mm wider than the walls.

Render time grows with the number of cells and the height. `VERIFICATION.md` records the render time of each reference configuration. Larger sizes take much longer: observed 2026-10-08 with OpenSCAD 2021.01 on Tim's Windows 11 desktop, with several other renders running at once, a 4 x 4 x 4 shell took about 220 s, 6 x 6 x 2 about 410 s, 12 x 1 x 12 about 11 minutes and 8 x 8 x 1 between 14 and 17 minutes. MakerWorld's Parametric Model Maker may stop a render that runs too long; its limit is not known here.

Evidence: the soundness section of `regress.py` includes a 4 LU wide shell, a 4 LU tall shell and a shell 0.5 LU front to back.
