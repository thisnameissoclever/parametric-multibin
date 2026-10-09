# DEVIATIONS - known differences between the remake and MultiBuild's shells

This file lists every known difference between `MultiBin Shell - Parametric.scad` and MultiBuild's shell STL files, and every rule the generator applies where MultiBuild publishes no example. Sizes are in LU, MultiBoard's 50 mm layout unit, written width x front-to-back x height as printed.

Evidence commands run from the `analysis` folder with the repository's Python environment, `..\..\..\.venv\Scripts\python.exe`, written below as `python`. The reference files live in the folder that `local-paths.json` names for `shell` (see `tools/mbpaths.py`). `python compare.py KEY` writes each render to `.local-build\out\shell\KEY.stl` at the repository root, which is `..\..\..\.local-build\out\shell\KEY.stl` from the `analysis` folder.

Entries starting with M are measured surface differences, Q entries are quirks of the originals that the generator reproduces, and P entries are rules for configurations with no original.

## Contents

- [M1. Faceting of the threaded holes, up to 0.02 mm](#m1-faceting-of-the-threaded-holes-up-to-002-mm)
- [M2. Mesh artifacts under 0.001 mm](#m2-mesh-artifacts-under-0001-mm)
- [M3. Pocket ceiling slits stop 0.01 mm short](#m3-pocket-ceiling-slits-stop-001-mm-short)
- [Q1. Short seam groove in a Simple wall's partial top band](#q1-short-seam-groove-in-a-simple-walls-partial-top-band)
- [P1. Half-LU cells](#p1-half-lu-cells)
- [P2. A different wall kind on each side](#p2-a-different-wall-kind-on-each-side)
- [P3. Sizes beyond the published shells](#p3-sizes-beyond-the-published-shells)

## M1. Faceting of the threaded holes, up to 0.02 mm

The generator builds each threaded hole, its thread and its entry cone with 32 facets per turn (`thr_steps`). A chord across one facet sits r (1 - cos(180 / 32)) inside the true circle, which is 0.017 mm at a radius of 3.5 mm. The references are faceted more finely, so their vertices and the render's vertices sit up to about 0.02 mm from each other's surfaces at the holes. These are the largest differences anywhere on the references.

Evidence: after `python compare.py T212`, `python worst_points.py T212 ..\..\..\.local-build\out\shell\T212.stl` lists the worst render vertices, 0.0168 mm from the reference surface, on the holes' entry cones, for example at (34.063, 12.744, 0.339) beside the hole at (37.5, 12.5); and the worst reference vertices, 0.0188 mm from the render surface, at the tops of the holes, for example at (15.815, -11.511, 5.200) beside the hole at (12.5, -12.5). `VERIFICATION.md` gives the all-vertices maximum for every reference.

Left as is. The threads dominate render time, and finer facets would slow every render for a difference under a tenth of a 0.2 mm print layer.

## M2. Mesh artifacts under 0.001 mm

The generator's exports contain four kinds of tiny artifact that the references do not. None changes the shape by more than 0.001 mm.

- Zero-area triangles, whose three corners lie on one line. OpenSCAD 2021.01 writes them where a face's edge meets a vertex of a neighbouring face: it splits that edge at the vertex and fills the split with a flat sliver. They keep every edge shared by exactly two faces, so the mesh stays closed.
- Slivers and pairs of separate vertices less than 0.0001 mm apart, where the edges of two cuts meet at almost the same point, for example at the threaded holes' entry cones, where the side clip pockets' ceiling slits meet their rounded heads, and at the rail channel notches. Some slivers fold back against a neighbouring triangle, which a mesh checker may report as a folded edge.
- A step 0.001 mm tall where a loft meets the solid that continues it, at the top of the inner rim chamfer and where the central pocket's flat end steps out. The generator builds each loft from end slabs 0.001 mm thick (`slab`, see the lesson on loft overlaps in `docs/lessons-learned.md`), and each step's two edges are vertex pairs 0.001 mm apart.
- A few pairs of triangles that cross each other by less than 0.0000001 mm, where coordinates rounded on export put a vertex a hair through a neighbouring face. On the 1x1x1 Topped Rail render all of them are at the threaded holes' entry cones.

These figures are for binary STL, which the harness renders with `--export-format binstl`. OpenSCAD 2021.01's default output is ASCII STL, which keeps six significant digits: 0.001 mm beyond 100 mm from the origin. That rounding merges some of the close vertices, and on long shells it pushes vertices up to about 0.003 mm through neighbouring faces.

The drawer generator's exports contain zero-area triangles too.

Evidence: after `python compare.py T111`, `python export_check.py ..\..\..\.local-build\out\shell\T111.stl` reports 24 zero-area triangles, 208 vertex pairs closer than 0.0001 mm and 12 crossing triangle pairs with a deepest overlap of 2.8e-08 mm. The same command on the 1x1x1 Topped Rail reference reports none of the three. `regress.py` fails any render with two triangles crossing by more than 0.001 mm; across the locked baseline the deepest crossing is under 0.00001 mm.

Left as is. The generator cannot control how OpenSCAD triangulates and rounds its output, and the 0.001 mm loft steps are the price of a loft construction that exports cleanly at every size. A slicer may report the zero-area triangles as degenerate facets when it imports the file; how each slicer treats them has not been tested here.

## M3. Pocket ceiling slits stop 0.01 mm short

The nine 0.1 mm slits in the ceiling of each pad's central pocket run across the pocket's seven-sided prism. In the references they end on the prism's sides. In the generator they stop 0.01 mm short of those sides. With ends flush with the sides, OpenSCAD 2021.01's export sealed some slits into closed voids for pads at some positions far from the origin: on a 1 x 7 x 1 shell with edges shared by four triangles, and on a 12 x 1 x 1 shell as a separate closed body inside the pad.

Evidence: the soundness section of `regress.py` renders 1 x 7 x 1 and 12 x 1 x 1 shells, which exported broken slits before the change, and checks that each is a single sound body. The 0.01 mm difference is below the faceting differences in M1.

## Q1. Short seam groove in a Simple wall's partial top band

On a shell whose height Z is not a whole number of LU, the rim cuts the top 50 mm band short. In band b (counting from 0), a seam groove normally runs from z 13.3 + 50b to 7 below the top of the band or the rim. On the Topped Rail and Topless Rail walls of the 1x2x1.5 shells, the groove in the partial band therefore runs from z 63.3 to z 73.0, 7 below the rim. On the Simple Walls 1x2x1.5 shell the same groove starts 9.2 below the rim, at z 70.8, the height of the upper catch slots, and ends at z 73.0 as on the other two. Its section matches the other seam grooves: 0.4 deep, half width 0.5 at the floor, a 1:2 rise at the bottom and 45 degrees at the top.

Evidence, on the seam at y 25 of the +x side wall, whose inner face is at x 22:

- `python wall_depth.py S1215 +x 18 25 22 62 74` reports the recess from z 70.9 to 72.9, reaching full depth 0.4 between z 71.6 and 72.6.
- `python wall_depth.py T1215 +x 18 25 22 62 74` and the same command for O1215 report the recess from z 63.4 to 72.9.
- `python wall_depth.py S1215 -x -18 25 -22 62 74` shows the same short groove on the -x side wall.

The generator reproduces it for every Simple wall with a partial top band. The 1x2x1.5 shell is the only Simple Walls reference with a partial band, and only its two side walls have seams, so this rule rests on one example and is applied to the front and back walls by extension. The partial band is always 25 mm tall, because heights step in half LU, so the example covers every partial band height the generator can make.

## P1. Half-LU cells

MultiBuild publishes no shell whose width or front-to-back size is a half LU. When a size ends in a half LU, the generator lays out whole 50 mm cells from the origin and then one 25 mm cell at the +x end or at the back. This rule is the generator's own:

- The half cell sits at the +x end and at the back (+y). The drawer generator counts its 50 mm height bands from the drawer's bottom, and a drawer's height runs front to back in the shell, so its side-wall jogs line up with the shell's seam slots when the drawer's bottom faces -y. A shell mounted with its print-orientation front (-y) down therefore takes the matching drawer upright, with the half band at the top of both. Across the width the drawer centres its cells while the shell's half cell sits at +x; the drawer is held by detent bumps at its corners, which snap into the shell's corner slots wherever its cells fall.
- The half cell's pad has the same outline rules as a whole pad, at its own size, and keeps the whole pad's features wherever they fit. Each hole, corner and 50 mm side sits at the same distance from the pad's faces as on a whole pad, so these features are placed exactly as there: the threaded holes on the 25 mm grid, a corner clip pocket at each corner, and on each 50 mm side the mid-edge notch and, where the side faces outward, the two side clip pockets.
- Three features are left out. A 25 mm side has no notch: the notch is 9.2 mm wide at the face, wider than the 7.7 mm flat part of the side, so it would cut into both corner chamfers. A 25 mm side has no side clip pockets: centred 7.5 from the middle of the side, they would run into the corner chamfers. And there is no central pocket: its flat end is 14.9 from the pad centre, beyond a pad face 9.3 from it. A shell's 25 mm pad sides therefore cannot take a side clip.
- No rail channel, and no catch slots, sit on the half cell's stretch of wall. A half cell is always at the end of a face, where the flat outer face between the seam and the corner chamfer is 25 - 8.737 = 16.3 mm long, shorter than a channel bulge, which is 17 mm wide. A pair of catch slots reaches 16.4 mm each way from a cell centre, beyond the half cell's 12.5.
- A rail channel on a whole cell runs down through the foot of the pad below it even when that pad is a half pad, as on the right wall of a shell whose width ends in a half LU. Without that cut, a Topped Rail channel would be closed at both ends.
- Seam features follow every seam, including the seam next to the half cell: the floor bridge gap, the seam grooves and the seam slots.
- On a Topless Rail wall, the rim groove runs through the half cell, since it has no channel to avoid.

Evidence: the soundness section of `regress.py` renders half-LU configurations, including Topless and Simple ones, and checks that each is a single sound body whose exact geometry matches the locked baseline. For the channel through a half pad's foot, from the repository root run `& "C:\Program Files\OpenSCAD\openscad.exe" -o .local-build\out\shell\h.stl -D width_lu=2.5 -D height_lu=1.5 -D depth_lu=2 "shells\multibin-shell\MultiBin Shell - Parametric.scad"`, then from the `analysis` folder compare `python wall_depth.py ..\..\..\.local-build\out\shell\h.stl -x 105 0 100 3.6 7 0.3` (right wall, over a half pad) with `python wall_depth.py ..\..\..\.local-build\out\shell\h.stl +y 0 -30 -25 3.6 7 0.3` (front wall, over a whole pad): both report a depth of 2.2 from z 4.8 upward.

## P2. A different wall kind on each side

MultiBuild publishes each shell with one wall kind on all four sides. The generator takes a kind for each side. Three features follow the kind of the face they belong to: the rail channel and its foot, the rim groove, and the seam groove in a partial top band (Q1). Everything else, including the catch slots, the seam slots, the corners and the base, is the same on all three published kinds. A pad side facing outward carries its side clip pockets on every wall kind.

Evidence: `python compare.py` matches all three kinds with the same catch slot, corner and base construction, and the soundness section of `regress.py` renders shells with Topped, Topless and Simple sides together.

## P3. Sizes beyond the published shells

The generator accepts 1 to 12 LU of width (X, `width_lu`), 0.5 to 12 LU front to back (Y, `height_lu`) and 1 to 12 LU of height as printed (Z, `depth_lu`), in half-LU steps, to match the drawer generator. Every feature repeats on a fixed pitch: pads, channels, catch slots and seam features per 50 mm cell; catch slot rows and seam grooves per 50 mm band of height; and channel bulges every 25 mm of height. The reference shells reach 3 LU wide, 2 LU front to back and 3.5 LU tall.

A shell 0.5 LU front to back has no whole cells along Y, so its left and right walls carry no channels or catch slots, and all its pads are half pads.

The shell is built only from 25 mm and 50 mm cells, so a size typed in off the half-LU step is rounded to the nearest half LU, and a size outside the slider's range is held to it. Each adjustment prints a `NOTE` line in OpenSCAD's console naming the reason: off the half-LU grid, below the minimum or above the maximum. Without the rounding, a width of 1.3 LU would leave the base 9.2 mm wider than the walls.

Render time grows with the number of cells and the height. `VERIFICATION.md` records the render time of each reference configuration. Larger sizes take much longer. Observed 2026-10-08 with the generator at commit 84ffa3f and OpenSCAD 2021.01, on a Windows 11 desktop with 24 logical processors running four to eight renders at once: 12 x 1 x 1 about 170 s, 1 x 12 x 1 about 160 s, 12 x 1 x 12 about 11 minutes, and 8 x 8 x 1 between 17 and 19 minutes. MakerWorld's Parametric Model Maker may stop a render that runs too long; its limit is not known here.

Evidence: the soundness section of `regress.py` includes 4 LU wide, 12 LU wide, 4 LU tall and 7 LU and 7.5 LU front-to-back shells, and a shell 0.5 LU front to back.
