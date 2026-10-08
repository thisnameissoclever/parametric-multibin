# MultiBin Simple Drawer - reverse-engineering notes

This folder holds a parametric OpenSCAD remake of MultiBoard's "MultiBin Simple Drawer" inserts, reverse-engineered from nine official STLs in `C:\Users\myema\OneDrive\3DP\Multiboard\Multi-BIN\Bin Inserts\Drawer Inserts`. The deliverable is `MultiBin Simple Drawer - Parametric.scad`; everything else is the measurement and verification harness. Match results live in `VERIFICATION.md`, and every knowing difference from the originals lives in `DEVIATIONS.md`.

## Coordinate and size system

Names follow Width x Height x Depth in LU. One LU is a 50 mm grid step.

- Outer width = 50W - 7, outer height = 50H - 7 (3.5 mm clearance per side inside the shell).
- Outer depth = 50D + 7: the body is 50D - 1 deep and the pull lip floats 8 mm in front of it.
- The model is X-centered; the back face is Y = 0 (front toward -Y); the base is Z = 0.
- Wall top WT = outer height - 5.272. Side walls, back wall, and dividers stop there; only the front wall and the back corner braces reach full height.

## Measured construction (all values in mm)

- Floor 1.6 thick. Side walls 1.0, back wall 1.0 thickening to 2.0 over an 8-tall 1:4 lean just below the top edge, front wall 2.0. Magnetic drawers use a flat 4.0 back wall instead.
- Interior floor blends: r5 fillets along the front wall, back wall, and both sides of every divider; a 4.686-leg 45 degree chamfer along the side walls; 0.414-leg (back) and 0.4-leg (front) vertical chamfers in the cavity corners, each fading into the floor blends on a measured tilted plane near z 6.3 (back plane normal (0.5, 0.7071, -0.5) through the outer corner at z 6.286).
- Outer bottom edges: 5.272-leg 45 degree chamfers on the sides; 1 mm chamfer at the back; a 1.65 45 degree lead plus r7 fillet at the front, applied only across the finger-slot span.
- 1 mm 45 degree chamfers on all vertical corners and top outer edges; 5.272-leg 45 degree chamfers on the top corners. Where the 1 mm edge chamfers cross the sloped corner zones they tilt into hip planes (verified normals in the (1, +/-2, +/-1)/sqrt(6) family).
- Scoop in the back wall top edge: the flat ends 18.544 short of each side wall, rising at 45 degrees. On whole-LU widths that is identical to the outermost cell centers plus 2.956, which is what the originals measure; driving it from the half-width keeps the same shoulder on half-LU widths too.
- Back corner braces: a 1 mm arm leaning 45 degrees inward from the side wall top to full height, with a flange running 8H + 2 along the side wall (clamped to 50D - 5 so it cannot pierce the front wall).
- Pull lip: a 2 mm plate (front face at depth + 7, top edge 5.272 with a 0.869 chamfer and a 22.5 degree back slope), 45 degree wings merging into the body on the plane x - 2y + z = half - 2F + 6.772, gussets at internal 50 mm cell boundaries (3.4 wide, ridge rising 45 degrees to 13.272 on the front face, flank chamfers dropping sqrt(2) per mm beyond the +/-0.7 ridge band), and a finger slot behind the lip with end walls inset 8.101 from the sides.
- Detent bumps on both side bottom chamfers: a pad 3 mm behind the front face, face plane at |x| = half - 1.575 topping out at z 3.697, shelf at z 1.575. The face bottom is z 2.282 on 1-LU-tall drawers at least 2 LU wide and z 2.565 otherwise (see DEVIATIONS.md D1).
- Label holder, top-referenced: card channel walls at +/-(14.25 + 25(cells-1)), window at +/-(13.2 + 25(cells-1)), frame 1.6 proud, hook slot floor at height - 18.75, window bottom at height - 17.7, rail tops at height - 4.9 chamfered 45 degrees to a window ledge at height - 6.5. Small is the 1-cell frame, large the 2-cell frame, both centered.
- Magnet option: 4 mm back wall with one keyhole pocket per cell, 3.2 deep. A fixed lower octagon (+/-8.5 wide, floor z 7 at the entry dropping to 6.6 between depths 1.8 and 2.2) plus an upper waist and top that hold their entry outline for the first 0.4 of depth and then flare at 45 degrees to +/-8.5 and z 30.
- For every internal 50 mm height boundary (H >= 1.5): the back wall jogs inward 1 mm and each side wall jogs inward 1 mm, clearing the shell's stacking ribs. Both are octagonal, with 60 degree edge drafts and 45 degree corner chamfers whose legs shrink linearly with depth: recess 2.929 - 1.015d, jog window the same, inward panel 3.086 - 1.015d on its back corners. The jog panel's front corners are cut at about 52.4 degrees instead (legs 3.239 - 1.004d in Z against 2.497 - 0.774d in Y), and the panel sits shifted 0.268 forward in Y.
- Dividers: 1.0 thick, r5 floor fillets, 0.5-leg 45 degree flares where they meet walls, tops at the wall height by default. Width dividers make exactly equal compartments. Depth dividers sit with their back face on the equal division line (see DEVIATIONS.md D2).

## Verification

`analysis\compare.py` regenerates all nine reference configurations with OpenSCAD and reports bidirectional surface-sample distances against the originals, plus a deterministic sweep of every mesh vertex in both directions; run it with `.venv\Scripts\python.exe` and pass `--report` to rewrite `VERIFICATION.md`. Current state: bounding boxes exact on every axis, volumes within 0.005 percent, 99th-percentile surface distance at or below 0.0013 mm, and worst-case vertex deviation 0.0113 mm on seven models against a 0.2 mm gate. The two 3-wide divided models reach 0.133 mm at the single documented fragment in DEVIATIONS.md D5.

The all-vertices sweep exists because random surface sampling proved unreliable here: it reported 0.010 mm where the true worst case was 0.133 mm, a 13x understatement, because that deviation follows an edge and carries almost no area for an area-weighted sampler to hit. Keep the deterministic checks in any future verification.

Beyond the harness, three independent adversarial reviewers audited the work over five rounds with their own tooling: one replicating the match metrics from scratch, one auditing feature semantics through its own cross-sections, and one fuzzing configurations that have no reference model. Their findings drove the corner chamfer leg laws, the cavity corner fade construction, the low-height feature gates, the corner brace clamp, the model-scaled half-space helper, the label cutter planes, and the width-scaled scoop.

Other analysis tools: `fingerprint.py` (plane inventory), `sections.py` (cross-section outlines with arc fitting; verify suspicious arcs with `--raw`), `query.py`, `region.py`, and `planefit.py` for targeted triangle queries.
