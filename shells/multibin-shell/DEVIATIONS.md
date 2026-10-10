# DEVIATIONS - known differences between the remake and MultiBuild's shells

This file lists every known difference between `MultiBin Shell - Parametric.scad` and MultiBuild's shell STL files, and every rule the generator applies where MultiBuild publishes no example. Sizes are in LU, MultiBoard's 50 mm layout unit, written width x front-to-back x height as printed.

Evidence commands run from the `analysis` folder with the repository's Python environment, `..\..\..\.venv\Scripts\python.exe`, written below as `python`. The reference files live in the folder that `local-paths.json` names for `shell` (see `tools/mbpaths.py`). `python compare.py KEY` writes each render to `.local-build\out\shell\KEY.stl` at the repository root, which is `..\..\..\.local-build\out\shell\KEY.stl` from the `analysis` folder.

Entries starting with M are measured surface differences, Q entries are quirks of the originals that the generator reproduces, and P entries are rules for configurations with no original.

## Contents

- [M1. Faceting of round features, up to 0.02 mm](#m1-faceting-of-round-features-up-to-002-mm)
- [M2. Mesh artifacts](#m2-mesh-artifacts)
- [M3. Pocket ceiling slits stop 0.01 mm short](#m3-pocket-ceiling-slits-stop-001-mm-short)
- [M4. Seam slots' inner chamfer starts 0.002 mm deeper](#m4-seam-slots-inner-chamfer-starts-0002-mm-deeper)
- [Q1. Short seam groove in a Simple wall's partial top band](#q1-short-seam-groove-in-a-simple-walls-partial-top-band)
- [P1. Half-LU cells](#p1-half-lu-cells)
- [P2. A different wall kind on each side](#p2-a-different-wall-kind-on-each-side)
- [P3. Sizes beyond the published shells](#p3-sizes-beyond-the-published-shells)

## M1. Faceting of round features, up to 0.02 mm

The generator builds each threaded hole, its thread and its entry cone with 32 facets per turn (`thr_steps`). A chord across one facet sits r (1 - cos(180 / 32)) inside the true circle, which is 0.017 mm at a radius of 3.5 mm. The references are faceted more finely, so their vertices and the render's vertices sit up to about 0.02 mm from each other's surfaces at the holes. These are the largest differences anywhere on the references.

The rounded heads of the side clip pockets, radius 2.25 mm, are built with 32 facets too (`arc_fn`), so the references' vertices there sit up to 2.25 (1 - cos(180 / 32)) = 0.011 mm from the render.

Evidence: after `python compare.py T212`, `python worst_points.py T212 ..\..\..\.local-build\out\shell\T212.stl` lists the worst render vertices, 0.0168 mm from the reference surface, on the holes' entry cones, for example at (35.290, -9.807, 0.334) beside the hole at (37.5, -12.5); and the worst reference vertices, 0.0188 mm from the render surface, at the tops of the holes, for example at (15.815, -11.511, 5.200) beside the hole at (12.5, -12.5). `VERIFICATION.md` gives the all-vertices maximum for every reference. After `python compare.py T111`, `python worst_points.py T111 ..\..\..\.local-build\out\shell\T111.stl 6 --away-from-holes --below 0.011` lists reference vertices 0.0108 mm from the render on the side clip pockets' heads, for example at (4.098, -18.708, 3.000); the larger differences away from the holes are the slit ends of M3.

Left as is. The threads dominate render time, and finer facets would slow every render for a difference under a tenth of a 0.2 mm print layer.

## M2. Mesh artifacts

The generator's exports contain four kinds of tiny artifact that the references do not. In binary STL none changes the shape by more than 0.001 mm; OpenSCAD's default ASCII STL adds rounding of its own, described after the list.

- Zero-area triangles, whose three corners lie on one line. OpenSCAD 2021.01 writes them where a face's edge meets a vertex of a neighbouring face: it splits that edge at the vertex and fills the split with a flat sliver. They keep every edge shared by exactly two faces, so the mesh stays closed.
- Slivers and pairs of separate vertices less than 0.0001 mm apart, where the edges of two cuts meet at almost the same point: at the central pocket's steps, at the corners of the pads' bottom chamfer, along the line at z 6.8 where the walls meet the foot, and at the rail channel's notches and at the ends of its bulges on the channel floor. Some slivers fold back against a neighbouring triangle, which a mesh checker may report as a folded edge.
- A step 0.001 mm tall where a loft (a solid that blends one cross-section into another, such as a chamfer) meets the solid that continues it, at the top of the inner rim chamfer and where the central pocket's flat end steps out. The generator builds each loft from end slabs 0.001 mm thick (`slab`, see the lesson on loft overlaps in `docs/lessons-learned.md`), and each step's two edges are vertex pairs 0.001 mm apart.
- Pairs of triangles that touch or cross each other by less than 0.0001 mm, where coordinates rounded on export put a vertex a hair through a neighbouring face. No reference render has a pair that crosses by a measurable depth; the deepest in the locked baseline, 0.00001 mm, is on the 12 x 1 x 1 shell.

OpenSCAD's 3MF export (3D Manufacturing Format, a zipped file that slicers read) stores each vertex once and refers to it by number. In the sizes checked it writes no two separate vertices at identical coordinates, and merging the vertices closer together than 0.00001 mm, or than 0.0001 mm, as a slicer may on import, leaves every edge shared by exactly two triangles. The generator builds the threaded holes' entry cones and the half-size pads so that their faces meet the neighbouring faces exactly, not a hair apart, and keeps the seam slots' inner chamfers out of the inner grooves' floor plane (M4). The gate checks two half-LU sizes and the 4 x 1 x 1 both ways. Spot checks found no coincident vertices on the 1x1x1, the default 2x1x2 and the 3x2x3, and no edges broken by either merge on the 1x1x1 and the 12 x 1 x 1.

These figures are for binary STL, which the harness renders with `--export-format binstl`. OpenSCAD 2021.01's default output is ASCII STL, which keeps six significant digits: 0.001 mm beyond 100 mm from the origin. That rounding merges some of the close vertices, and on 12 LU shells it pushes vertices up to about 0.0003 mm through neighbouring faces.

The drawer generator's exports contain zero-area triangles too.

Evidence: after `python compare.py T111`, `python export_check.py ..\..\..\.local-build\out\shell\T111.stl` reports 8 zero-area triangles, 124 vertex pairs closer than 0.0001 mm, and no crossing triangle pairs. The same command on the 1x1x1 Topped Rail reference reports none of the three. `regress.py` also exports three sizes as 3MF and fails on any separate vertices at identical coordinates or any edge that either merge leaves shared by other than two triangles, and it fails any render in which two triangles that share at most one vertex cross by more than 0.001 mm; that check does not see triangles overlapping while lying in one plane, such as the folded slivers above, or neighbours that share an edge.

Left as is. The generator cannot control how OpenSCAD triangulates and rounds its output, and the 0.001 mm loft steps are the price of a loft construction that exports cleanly at every size. A slicer may report the zero-area triangles as degenerate facets when it imports the file; how each slicer treats them has not been tested here.

## M3. Pocket ceiling slits stop 0.01 mm short

The nine 0.1 mm slits in the ceiling of each pad's central pocket run across the pocket's seven-sided prism, and three more cross the ceiling of each side clip pocket. In the references they end on the pockets' sides. In the generator they stop 0.01 mm short of those sides. With ends flush with the sides, OpenSCAD 2021.01's export sealed some central pocket slits into closed voids for pads at some positions far from the origin, on shells 7 LU or more front to back and on 12 LU wide shells. Depending on the position and on whether the export is ASCII or binary STL, a sealed slit appears as a separate closed body inside the pad or as edges shared by four triangles. No export sealed a side clip pocket's slit, but those slits were built the same way, so they stop short as well.

At the slit ends the references' vertices sit up to 0.014 mm from the render in the central pockets, and up to 0.019 mm in the side clip pockets, where the faceting of the pocket's head (M1) adds to the 0.01 mm.

Evidence: the soundness section of `regress.py` renders 1 x 7 x 1 and 12 x 1 x 1 shells, which exported broken slits before the change, and checks that each is a single sound body. After `python compare.py T111`, `python worst_points.py T111 ..\..\..\.local-build\out\shell\T111.stl 6 --away-from-holes` lists the side clip pocket slit ends first, 0.0187 mm from the render, for example at (16.700, -4.450, 3.200).

## M4. Seam slots' inner chamfer starts 0.002 mm deeper

Each seam slot widens at 45 degrees from 6 x 2 at depth 2.6, measured from the outer face, to the inner face at depth 3.0. Depth 2.6 is also the floor of the inner grooves, which are 0.4 deep: the seam slots at z 27 + 50k cross a seam groove, and the top ones cross the rim groove. The generator starts the widening at depth 2.602 instead and keeps its end, so its first edge is not in the grooves' floor plane; its slope steepens by under 1 %, and its opening at the inner face measures 6.799 x 2.799 against the reference's 6.8 x 2.8. The slot is placed from the outer face and the grooves from the inner face, so with that edge in the floor plane the two met a rounding error apart, leaving zero-width fins where the top seam slots cross the rim groove. Merging the 3MF export's vertices within 0.00001 mm folded those fins into edges shared by four triangles: 2 such edges on a 4 x 1 x 1 shell and 9 on a 12 x 1 x 1. The chamfer's surface lies at most 0.002 mm from the reference's.

Evidence: the soundness section of `regress.py` exports the 4 x 1 x 1 shell as 3MF and fails on any edge left shared by other than two triangles after the merge; `selftest.py` checks that it fails on the fixture, which starts the chamfer at 2.6. `python export_check.py` reports the same counts for any 3MF file.

## Q1. Short seam groove in a Simple wall's partial top band

On a shell whose height Z is not a whole number of LU, the rim cuts the top 50 mm band short. In band b (counting from 0), a seam groove normally runs from z 13.3 + 50b to 7 below the top of the band or the rim. On the Topped Rail and Topless Rail walls of the 1x2x1.5 shells, the groove in the partial band therefore runs from z 63.3 to z 73.0, 7 below the rim. On the Simple Walls 1x2x1.5 shell the same groove starts 9.2 below the rim, at z 70.8, the height of the upper catch slots, and ends at z 73.0 as on the other two. Its section matches the other seam grooves: 0.4 deep, half width 0.5 at the floor, a 1:2 rise at the bottom and 45 degrees at the top.

Evidence, on the seam at y 25 of the +x side wall, whose inner face is at x 22:

- `python wall_depth.py S1215 +x 18 25 22 62 74` reports the recess from z 70.9 to 72.9, reaching full depth 0.4 between z 71.6 and 72.6.
- `python wall_depth.py T1215 +x 18 25 22 62 74` and the same command for O1215 report the recess from z 63.4 to 72.9.
- `python wall_depth.py S1215 -x -18 25 -22 62 74` shows the same short groove on the -x side wall.

The generator reproduces it for every Simple wall with a partial top band. The 1x2x1.5 shell is the only Simple Walls reference with a partial band, and only its two side walls have seams, so this rule rests on one example and is applied to the front and back walls by extension. The partial band is always 25 mm tall, because heights step in half LU, so the example covers every partial band height the generator can make.

## P1. Half-LU cells

MultiBuild publishes no shell whose width or front-to-back size is a half LU. When a size ends in a half LU, the generator lays out whole 50 mm cells from the origin and then one 25 mm cell at the +x end or at the back. This rule is the generator's own:

- The half cell sits at the +x end and at the back (+y). The drawer generator counts its 50 mm height bands from the drawer's bottom, and a drawer's height runs front to back in the shell, so the 1 mm inward steps in its side walls at each 50 mm height boundary (its jogs) line up with the shell's seam slots when the drawer's bottom faces -y. A shell mounted with its print-orientation front (-y) down therefore takes the matching drawer upright, with the half band at the top of both. Across the width the drawer centres its cells while the shell's half cell sits at +x; the drawer is held by detent bumps at its corners, which snap into the shell's corner slots wherever its cells fall.
- The half cell's pad has the same outline rules as a whole pad, at its own size, and keeps the whole pad's features wherever they fit. Each hole, corner and 50 mm side sits at the same distance from the pad's faces as on a whole pad, so these features are placed exactly as there: the threaded holes on the 25 mm grid, a corner clip pocket at each corner, and on each 50 mm side the mid-edge notch and, where the side faces outward, the two side clip pockets.
- Three features are left out. A 25 mm side has no notch: the notch is 9.2 mm wide at the face, wider than the 7.7 mm flat part of the side, so it would cut into both corner chamfers. A 25 mm side has no side clip pockets: centred 7.5 from the middle of the side, they would run into the corner chamfers. And there is no central pocket. On a pad 25 mm across in x, the pocket would overlap the threaded hole at (0, -12.5); on a pad 25 mm across in y, its flat end, 14.9 from the pad centre, would pass the pad face 9.3 from it. A shell's 25 mm pad sides therefore cannot take a side clip.
- No rail channel, and no catch slots, sit on the half cell's stretch of wall. A half cell is always at the end of a face, where the flat outer face between the seam and the corner chamfer is 25 - 8.737 = 16.3 mm long, shorter than a channel bulge, which is 17 mm wide. A pair of catch slots reaches 16.4 mm each way from a cell centre, beyond the half cell's 12.5. On every published shell the outermost cell's catch slot ends where the flat inner face ends, at the inner corner chamfer, so every inner corner has one; the inner corners at a half-LU end have none. Anchoring one catch slot to each corner instead would match every published shell as well.
- The central pocket of each whole pad has the same outline as the magnet pocket in the back wall of a magnet drawer from the drawer generator, so the two appear to be partners: a magnet in each holds the drawer through the shell's floor. Whole-LU widths line them up. At half-LU widths they miss by 12.5 mm, because the drawer generator centres its magnet pockets across the drawer while the shell lays its cells out from the -x end. `docs/roadmap.md` lists aligning them as drawer work.
- A rail channel on a whole cell runs down through the foot of the pad below it even when that pad is a half pad, as on the right wall of a shell whose width ends in a half LU. Without that cut, a Topped Rail channel would be closed at both ends.
- Seam features follow every seam, including the seam next to the half cell: the floor bridge gap, the seam grooves and the seam slots.
- On a Topless Rail wall, the rim groove runs through the half cell, since it has no channel to avoid.

Evidence: the soundness section of `regress.py` renders half-LU configurations, including Topless and Simple ones, and checks that each is a single sound body whose vertices and volume match the locked baseline. For the channel through a half pad's foot, from the repository root run `& "C:\Program Files\OpenSCAD\openscad.com" -o .local-build\out\shell\h.stl -D width_lu=2.5 -D height_lu=1.5 -D depth_lu=2 "shells\multibin-shell\MultiBin Shell - Parametric.scad"`, then from the `analysis` folder compare `python wall_depth.py ..\..\..\.local-build\out\shell\h.stl -x 105 0 100 3.6 7 0.3` (right wall, over a half pad) with `python wall_depth.py ..\..\..\.local-build\out\shell\h.stl +y 0 -30 -25 3.6 7 0.3` (front wall, over a whole pad): both report a depth of 2.2 from z 4.8 upward.

## P2. A different wall kind on each side

MultiBuild publishes each shell with one wall kind on all four sides. The generator takes a kind for each side. Three features follow the kind of the face they belong to: the rail channel and its foot, the rim groove, and the seam groove in a partial top band (Q1). Everything else, including the catch slots, the seam slots, the corners and the base, is the same on all three published kinds. A pad side facing outward carries its side clip pockets on every wall kind.

Evidence: `python compare.py` matches all three kinds with the same catch slot, corner and base construction, and the soundness section of `regress.py` renders shells with Topped, Topless and Simple sides together.

## P3. Sizes beyond the published shells

The generator accepts 1 to 12 LU of width (X, `width_lu`), 0.5 to 12 LU front to back (Y, `height_lu`) and 1 to 12 LU of height as printed (Z, `depth_lu`), in half-LU steps, to match the drawer generator. Every feature repeats on a fixed pitch: pads, channels, catch slots and seam features per 50 mm cell; catch slot rows and seam grooves per 50 mm band of height; and channel bulges every 25 mm of height. The reference shells reach 3 LU wide, 2 LU front to back and 3.5 LU tall.

A shell 0.5 LU front to back has no whole cells along Y, so its left and right walls carry no channels or catch slots, and all its pads are half pads. A Topped Rail or Topless Rail choice for those walls therefore builds the same wall as Simple, and the generator prints a `NOTE` in OpenSCAD's console saying so; MakerWorld's Parametric Model Maker may not show that console.

The shell accepts only the sizes its sliders offer: half-LU steps within each range. Any other value, such as a size typed in off the half-LU step, outside the range, or not a number, stops the render with an error naming the parameter and the allowed values; a value within 0.0000005 LU of a half step counts as that step, to absorb rounding in the number passed in. The error shows the value to six significant digits, so a value just outside that margin, such as 1.000001, is reported as 1. The shell is built only from 25 mm and 50 mm cells, so it cannot take an off-step size as given (a width of 1.3 LU would leave the base 9.2 mm wider than the walls), and the drawer generator builds a drawer at any off-step size it is given, so a shell rounded to another size would not match the drawer made with the same numbers.

Render time grows with the number of cells and the height. `VERIFICATION.md` records the render time of each reference configuration. Larger sizes take much longer. Observed 2026-10-08 with the generator at commit 84ffa3f and OpenSCAD 2021.01, on a Windows 11 desktop with 24 logical processors running four to eight renders at once: 12 x 1 x 1 about 170 s, 1 x 12 x 1 about 160 s, 12 x 1 x 12 about 11 minutes, and 8 x 8 x 1 between 17 and 19 minutes. MakerWorld's Parametric Model Maker may stop a render that runs too long; its limit is not known here.

Evidence: the soundness section of `regress.py` includes 4 LU and 12 LU wide shells, 4 LU and 12 LU tall shells, 7, 7.5 and 12 LU front-to-back shells, and a shell 0.5 LU front to back, and checks that three values the sliders cannot produce (1.3, 0, 12.5) each stop the render with the expected error.
