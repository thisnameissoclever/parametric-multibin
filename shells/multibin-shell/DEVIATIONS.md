# DEVIATIONS - known differences between the remake and MultiBuild's shells

This file lists every known difference between `MultiBin Shell - Parametric.scad` and MultiBuild's shell STL files, and every rule the generator applies where MultiBuild publishes no example. Evidence commands run with `.venv\Scripts\python.exe` from the `analysis` folder. The reference files live in the folder that `local-paths.json` names for `shell` (see `tools/mbpaths.py`), and `python compare.py KEY` writes each render to `.local-build\out\shell\KEY.stl` at the repository root.

Entries starting with M are measured surface differences, Q entries are quirks of the originals that the generator reproduces, and P entries are rules for configurations with no original.

## Contents

- [M1. Faceting of the threaded holes, up to 0.02 mm](#m1-faceting-of-the-threaded-holes-up-to-002-mm)
- [Q1. Short seam groove in a Simple wall's partial top band](#q1-short-seam-groove-in-a-simple-walls-partial-top-band)
- [P1. Half-LU cells](#p1-half-lu-cells)
- [P2. A different wall kind on each side](#p2-a-different-wall-kind-on-each-side)
- [P3. Sizes beyond the published shells](#p3-sizes-beyond-the-published-shells)

## M1. Faceting of the threaded holes, up to 0.02 mm

The generator builds each threaded hole, its thread and its entry cone with 32 facets per turn (`thr_steps`). A chord across one facet sits r (1 - cos(180 / 32)) inside the true circle, which is 0.018 mm at the entry cone's 3.8 mm radius. The references are faceted more finely, so their vertices and the render's vertices sit up to about 0.02 mm from each other's surfaces at the holes.

Evidence: `python worst_points.py T212 ..\..\..\.local-build\out\shell\T212.stl` lists the worst render vertex, 0.0187 mm from the reference surface, at (11.539, -15.565, 0.572) on the entry cone of the hole at (12.5, -12.5), and the worst reference vertex, 0.0199 mm from the render surface, at (13.408, -9.435, 5.200) at the top of the hole at (12.5, -12.5). `VERIFICATION.md` gives the all-vertices maximum for every reference.

Left as is. The threads dominate render time, and finer facets would slow every render for a difference a tenth of a 0.2 mm print layer.

## Q1. Short seam groove in a Simple wall's partial top band

On a shell whose height Z is not a whole number of LU, the top 50 mm band is cut short by the rim. On the Topped Rail and Topless Rail walls of the 1x2x1.5 shells, the vertical seam groove in that band runs from 13.3 above the band's base, z 63.3, to 7 below the rim, z 73.0. On the Simple Walls 1x2x1.5 shell the same groove starts 9.2 below the rim, at z 70.8, the height of the upper catch slots, and ends at z 73.0 as on the other two. Its section matches the other seam grooves: 0.4 deep, half width 0.5 at the floor, a 1:2 rise at the bottom and 45 degrees at the top.

Evidence, on the seam at y 25 of the +x side wall, whose inner face is at x 22:

- `python wall_depth.py S1215 +x 18 25 22 62 74` reports the recess from z 70.9 to 72.9, reaching full depth 0.4 between z 71.6 and 72.6.
- `python wall_depth.py T1215 +x 18 25 22 62 74` and the same command for O1215 report the recess from z 63.4 to 72.9.
- `python wall_depth.py S1215 -x -18 25 -22 62 74` shows the same short groove on the -x side wall.

The generator reproduces it for every Simple wall with a partial top band. The 1x2x1.5 shell is the only Simple Walls reference with a partial band, so this rule rests on one example. MultiBuild's partial band is always 25 mm tall, because heights step in half LU, so the example covers every partial band the generator can make.

## P1. Half-LU cells

MultiBuild publishes no shell whose width or front-to-back size is a half LU. When a size ends in a half LU, the generator lays out whole 50 mm cells from the origin and then one 25 mm cell at the +x end or at the back. This rule is the generator's own:

- The half cell's pad has the same outline rules as a whole pad, at its own size. It carries the threaded holes that fall on the 25 mm hole grid (at the half cell's centre along its short direction) and the mid-edge notches, but no central pocket, corner pockets or side clip pockets.
- No rail channel, and no catch slots, sit on the half cell's stretch of wall. A 17 mm channel with its bulges, and a pair of catch slots each reaching 16.4 mm from the cell centre, do not fit in 25 mm.
- Seam features follow every seam, including the seam next to the half cell: the floor bridge gap, the seam grooves and the seam slots.
- On a Topless Rail wall, the rim groove runs through the half cell, since it has no channel to avoid.

Evidence: the soundness section of `regress.py` renders half-LU configurations, including a Topless one and a Simple one, and checks that each is a single sound body with locked bounding box and volume.

## P2. A different wall kind on each side

MultiBuild publishes each shell with one wall kind on all four sides. The generator takes a kind for each side, and each feature follows the kind of the face it belongs to: the rail channel and its foot, the catch slots, the seam grooves and the rim groove. Features at the corners and in the base do not depend on the wall kind; the corner slots and corner faces measure the same on all three published kinds. A pad side facing outward carries its side clip pockets on every wall kind.

Evidence: `python compare.py` matches all three kinds with the same corner and base construction, and the soundness section of `regress.py` renders a shell with Topped, Topless and Simple sides together.

## P3. Sizes beyond the published shells

The generator accepts 1 to 12 LU of width (X, `width_lu`), 0.5 to 12 LU front to back (Y, `height_lu`) and 1 to 12 LU of height as printed (Z, `depth_lu`), in half-LU steps, to match the drawer generator. Every feature repeats on a fixed pitch: pads, channels, catch slots and seam features per 50 mm cell; catch slot rows and seam grooves per 50 mm band of height; and channel bulges every 25 mm of height. The reference shells reach 3 LU wide, 2 LU front to back and 3.5 LU tall.

A shell 0.5 LU front to back has no whole cells along Y, so its left and right walls carry no channels or catch slots, and all its pads are half pads.

Render time grows with the number of cells and the height. `VERIFICATION.md` records the render time of each reference configuration.

Evidence: the soundness section of `regress.py` includes a 4 LU wide shell, a 4 LU tall shell and a shell 0.5 LU front to back.
