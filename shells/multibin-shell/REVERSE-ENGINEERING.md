# MultiBin Shell - reverse-engineering notes

This folder holds a parametric OpenSCAD remake of MultiBoard's MultiBin shells with the Standard Base, measured from MultiBuild's STL files for the Topped Rail, Topless Rail and Simple Walls shells. The deliverable is `MultiBin Shell - Parametric.scad`; the `analysis` folder holds the measurement and verification tools. Match results live in `VERIFICATION.md`, and every known difference from the originals, including the rules for sizes MultiBuild does not publish, lives in `DEVIATIONS.md`.

## Contents

- [Coordinate and size system](#coordinate-and-size-system)
- [Walls and rim](#walls-and-rim)
- [Base](#base)
- [Base pockets and holes](#base-pockets-and-holes)
- [Rail channel](#rail-channel)
- [Inner wall recesses](#inner-wall-recesses)
- [Clip slots through the walls](#clip-slots-through-the-walls)
- [Wall kinds on each side](#wall-kinds-on-each-side)
- [Analysis tools](#analysis-tools)

## Coordinate and size system

MultiBuild names a shell X x Y x Z in LU (layout units, 50 mm each), and a drawer named W x H x D fits the shell with the same three numbers. The generator's parameters keep the drawer's names: `width_lu` is X, `height_lu` is Y and `depth_lu` is Z.

All coordinates here are in the print orientation, in mm: the base is on the build plate and the opening is on top. X is the width, Y runs from the front of the build plate to the back, and Z is up. The first 50 mm cell is centred on the origin, so the outer faces sit at X0 = -25, X1 = 50X - 25, Y0 = -25 and Y1 = 50Y - 25, and the rim is at ZT = 50Z + 5.

Positions along a wall are given as t, the distance along the face from a cell centre, and n, the depth into the wall from the face named.

## Walls and rim

- Outer plan: an octagon with its flat faces on the cell grid and 45 degree corner faces, chamfer leg 8.737.
- Wall thickness 3.0 at the flat faces. The cavity has 45 degree corner faces with leg 5.565, which leaves the corner wall 2.0 thick measured along the diagonal.
- Floor top at z 6.0, with a 1 mm 45 degree chamfer where the floor meets the walls.
- Rim: a 1 mm 45 degree chamfer on the outer edge of the four flat faces only; the diagonal corner faces run straight to the top. Inside, a chamfer runs 1.6 out over the top 1.2.

## Base

Each 50 mm cell stands on its own pad.

- Pad sides are vertical, inset 3.2 from the cell edge, up to z 3.6, then turn out at 45 degrees; the outer flat faces reach full size at z 6.8.
- Pad corners are chamfered with leg 5.448 (the generator uses 5.4483, which puts the pad's corner faces exactly on the corner planes described next). Each corner face sits 2.2 inside a 45 degree corner face of leg 8.737 on the cell's own outline (at a shell corner, the shell's outer corner face) and chamfers out at 45 degrees to meet it at z 5.8.
- The pad's bottom edge has a 0.4 mm 45 degree chamfer.
- Between neighbouring pads, the floor's underside is at z 5.2. In the gap between two pads' 45 degree faces it stops at z 5.4 instead: beside the flat part of each pad side between columns, and along the whole length of each seam between rows, through the crossings. The gap's half width at height z is 6.8 - z.
- Where a face carries a rail channel, the channel's dovetail runs down through the foot to the base.

## Base pockets and holes

Each whole cell's pad, centred on the cell, has these features.

- Four blind threaded holes at (+/-12.5, +/-12.5), up to z 5.2, with a 45 degree entry cone of radius 3.8 at z 0. The thread is right-handed with pitch 3.125. Along the helix coordinate u = z - 3.125 a / 360 (mod 3.125), where a is the angle about the hole axis from +x, the radius rises from 3.0 to 3.5 over u 1.0735 to 2.0110, stays at 3.5 to 2.6360, falls back to 3.0 by 3.5735, and is 3.0 elsewhere.
- A central pocket:
  - a flared octagon, half width 6.0 at z 0.4 growing at 45 degrees to 8.5 at z 2.9, with corner legs 3.515 and 4.979, and a ceiling at z 3.2;
  - a prism with a flat end at y -14.5 and vertices (+/-3.521, -14.5), (+/-8.5, -9.521) and (+/-8.5, -2.479), whose sides would meet in a point at (0, 6.021); the pocket stops at the octagon's face, y 6.0, so the point is cut off there. Its flat end steps out at 45 degrees to y -14.9 between z 1.8 and 2.2;
  - nine ceiling slits 0.1 wide across the prism, every 1 mm from y -14.2, up to z 3.4;
  - a plate up to z 3.4 over |y| <= 5.1, keeping only the octagon's two top chamfers;
  - a square of half width 5.1 up to z 3.6;
  - an octagon of half width 5.1 and leg 2.988 up to z 5.2.
- Four T-shaped corner pockets along the diagonals, between z 1 and 3 with 0.4 chamfers on their long edges. Each has a neck of half width 2.0 running 2.8 in from the pad's corner face, 26.977 from the pad centre, then a head of half width 3.0 for 2 mm, with a 0.2 chamfer around the opening.
- Two side clip pockets on each outward-facing pad side, centred at t = +/-7.5, between z 1 and 3. Each is a 6 wide entry from the pad face to an obround head: two arcs of radius 2.25 centred 1.25 either side of the pocket's centre line, 18.05 from the pad centre, with a 0.2 chamfer at the opening and ceiling slits 0.1 wide at 16.7, 17.6 and 19.7 from the pad centre, z 2.9 to 3.2. A pad side that faces a neighbouring pad has none.
- A pyramid notch under the middle of each pad side. For the +y side, with the pad face at h = 21.8 from the pad centre, it is bounded by y - z >= h - 2.3 and y -+ x - sqrt(2) z >= h - 4.578.

## Rail channel

Topped Rail and Topless Rail walls carry one dovetail channel per whole cell, centred on the cell, running the full height of the wall and down through the foot.

- Profile: half width 7.0 at the face, straight for 0.4, then a 45 degree flank out to half width 8.5 at depth 1.9; the floor is at depth 2.2.
- Bulges centred at z 5 + 25k, where the slot widens to half width 8.5 through its full depth, the face included. A bulge is at full width for 3.5 each way from its centre and narrows at 45 degrees to the normal half width 7.0 at 5 from its centre.
- At both ends of each bulge's full-width section, a notch in each side wall: 0.8 deep beyond the bulge side, starting 1.0 below the face, 2.2 long, with 45 degree ends.
- Topped Rail end: the slot stops below a cap at the rim. The cap's underside sits 5.5 below the rim at the face and is hooked at 45 degrees up to 4.0 below the rim at the flank. The slot also closes in a 45 degree gable, made by sweeping the dovetail profile along two 45 degree lines whose centrelines meet 12.5 below the rim.
- Topless Rail end: the channel runs out through the rim, and the wall behind it is cut flat 0.9 below the rim across the channel's full width, back to the inner rim chamfer.

Simple walls have no channel; their outer face is plain.

## Inner wall recesses

Every recess has the same section: 0.4 deep and 2.2 tall, rising at 1:2 (0.8 tall) from its bottom edge and closing at 45 degrees at its top. Its ends are 45 degrees in plan, which at the cavity corners is the inner corner chamfer plane.

- Catch slots, on every wall kind, for each whole cell: from t 10.435 to 16.435 on both sides of the cell centre, at z 13.3, and 9.2 below the top of each 50 mm band (bands end at z 5 + 50k). When Z is not a whole number of LU, a row also sits 9.2 below the rim.
- Seam grooves at each seam between cells: half width 0.5 at the groove floor with 45 degree sides, one per 50 mm band: in band b, counting from 0, from z 13.3 + 50b to 7 below the band's top or the rim, whichever is lower. On a Simple wall the groove in a partial top band starts 9.2 below the rim instead (see `DEVIATIONS.md`).
- Rim groove, 4.2 below the rim: along the whole flat inner face on Topped Rail and Simple walls, ending at the inner corner chamfers. A Topless Rail wall leaves it out within t 10.435 of each whole cell's centre, behind the rail channel, so the groove continues across the seams between cells.

## Clip slots through the walls

- Seam slots at each seam between cells, on every face and every wall kind, centred at z 27 + 25k up to 1 below the rim. Each is 6 x 2 (half sizes 3.0 x 1.0 with 0.4 corner chamfers) from the outer face to depth 0.8 and from depth 2.0 to the inner face. Between depths 0.8 and 2.0 it narrows to 4 wide, with a 0.2 mm 45 degree chamfer on each step's edge. The opening has a 0.2 chamfer at the outer face and a 0.4 chamfer at the inner face.
- Corner slots through each diagonal corner face, centred 3 below the rim. The corner wall is 2.0 thick, so only the outer 2.0 of the seam slot section exists there, with a 0.2 chamfer where it opens into the cavity.

## Wall kinds on each side

MultiBuild publishes each shell with one wall kind on all four sides. Every feature above belongs either to one face or to the shared corners and base. The corner features measure identical across the three kinds, so the generator sets each side's kind independently. A pad side facing outward carries side clip pockets whatever the wall kind, and only a face with a rail channel continues the channel into the foot.

## Analysis tools

Run these from the `analysis` folder with the repository's Python environment, `..\..\..\.venv\Scripts\python.exe`. `docs/verification-method.md` at the repository root defines the gates they serve.

- `compare.py` renders each reference configuration and reports the Gate 1 metrics, exiting 1 when any fails; `--report` rewrites `VERIFICATION.md` and refuses unless every expected reference is present.
- `regress.py` is the regression gate, with its locked `baseline.json`. `selftest.py` runs it against the known-bad fixture in `fixtures` and checks that each section of the gate reports a failure the fixture is known to cause.
- `export_check.py` counts the mesh artifacts described in `DEVIATIONS.md` M2.
- `gate_test.py` tests the gate's decisions at their limits in seconds; `selftest.py` runs it first.
- `worst_points.py` lists the worst vertex deviations with their locations; `wall_depth.py` measures recess depth along a vertical line on a wall.
- `fingerprint.py` (plane inventory), `section.py` (sections with circle fits), `window.py` (windowed sections), `facemap.py` (ray-cast depth images) and `thread_fit.py` (thread profile fit) were used to take the measurements above.
