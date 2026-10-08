# DEVIATIONS - knowing differences between the remake and the original STLs

Every entry lists the evidence commands (run with `.venv\Scripts\python.exe` from `analysis\`). Reference originals live in `C:\Users\myema\OneDrive\3DP\Multiboard\Multi-BIN\Bin Inserts\Drawer Inserts`.

Current state, from the deterministic all-vertices sweep in `analysis\compare.py`: seven of the nine models have a worst deviation between 0.0110 and 0.0113 mm. The two 3-wide divided models reach 0.133 mm at one spot, the boolean fragment in D5. Nothing anywhere else exceeds 0.05 mm.

Entries below run D3a, D3b, D5 first, since those are the measured surface differences, then the reproduced quirks, then rules and resolved defects.

## D3a. Front cavity corner fade band, 0.0110 to 0.0113 mm, on all nine models

This is the worst deviation on the seven models that do not carry the D5 fragment, and it has nothing to do with dividers: it appears on n111 and s111, which have none. On c313 and c3135 the D5 fragment is larger, at 0.133.

Where the 0.4 leg chamfer in each front cavity corner fades into the floor blends, the originals use a slightly twisted surface. Five facets carry normals whose Z component climbs steadily across the band while X and Y barely move: (-0.7058, 0.7082, 0.0169), (-0.7070, 0.7068, 0.0241), (-0.7072, 0.7059, 0.0402), (-0.7059, 0.7065, 0.0507), (-0.7111, 0.6981, 0.0837). The remake closes the same gap with one fitted plane, normal (-0.7084, 0.7043, 0.0451), which sits inside that spread but cannot follow the twist.

Evidence: `python region.py n111 19.9 21.1 -47.3 -46.4 5.5 6.7` returns those five reference facets. The residual appears in `analysis\compare.py` as the all-vertices worst case at (-20.116, -46.950, 5.903) and its mirror. Per model it measures 0.0113 on n111, s111, c212, g212 and L332, 0.0112 on L323, c313 and c3135, and 0.0110 on m212.

The band totals about 0.27 mm2 of surface, so sampling under-reads it: `python probe_flare.py n111 19.5 21.1 -47.4 -46.3 5.4 6.8` puts about 40 of 400,000 samples in the box and reads at most 0.0072, against the deterministic 0.0113. (An earlier draft reported zero samples here. That was a bug in `probe_flare.py`, which tested for more than eight arguments where a supplied box makes exactly eight, so it silently discarded the box and reused its default. Fixed.)

Left as is. Following the twist would replace one fitted plane with a lofted pair for a 0.011 mm gain, well under a tenth of a print layer. It is also the model's thinnest construction; see D9.

## D3b. Divider end flare against the leaning back wall, 0.0106 mm, four models

On c212, g212, c313 and c3135 the originals build the transition between the flare's lower run (against the 1 mm wall) and its upper run (against the 2 mm wall) as a single plane containing the wall's 1:4 lean direction and tilted 45 degrees in X. Its face normal measures (0.7071, -0.6860, -0.1715). The remake lofts between the two runs instead, giving (0.6963, -0.6963, -0.1741), a plane tilted 0.868 degrees from the original.

Where the offset sits: the flare is a 0.5 chamfer running from the divider face, 0.5 in front of the wall, out to the wall face, 0.5 to the side of the divider. Measured on c212 in the reference frame, the originals put the transition corner at z 29.666 at the divider-face end (x 25.500, y -1.500) and at z 29.728 at the wall-face end (x 26.000, y -1.000), and likewise 33.666 against 33.728 at the top of the lean. So the height drops 0.0616 at the divider-face end and by nothing at the wall-face end. The remake holds both ends level at 29.728 and 33.728.

Evidence: `python region.py c212 24.9 26.6 -3.1 -0.9 28.5 34.5` on the original returns the two transition triangles with vertices (25.500,-1.500,29.666) (26.000,-1.000,29.728) (26.000,-2.000,33.728) (25.500,-2.500,33.666). The straight runs above and below match exactly; only the transition differs.

The vertex offset is 0.0616 in z, but the face is nearly edge-on to that direction, so the perpendicular surface displacement is far smaller. `python probe_flare.py c212` measures max 0.01021 and mean 0.00173 reference to remake, and max 0.00979 and mean 0.00064 the other way; an independent audit measured 0.0106. The loft is kept: at a twentieth of a print layer the difference cannot be printed, and restructuring the flare risks a construction that currently holds every model to 0.0113 mm.

## D5. Divider-over-gusset fragment on the two 3-wide divided originals (boolean residue, not reproduced)

On c313 and c3135 the column dividers sit at x +/-23.167/24.167 while the pull-lip gussets reach x +/-23.300, so each divider overhangs its gusset by 0.133. The front-bottom fillet cut is bounded by the gusset bands, so it passes through that strip in both the originals and the remake. In the originals a small fragment survives inside it, bounded by the divider face, the front wall inner plane, and a horizontal face at z 1.500, measuring 0.1333 by 0.2005 by 0.2010. Two mirrored instances per model, about 0.00268 mm3 each, 0.0107 mm3 across both models.

Evidence: `python region.py c313 72.9 74.4 -148.5 -145.5 1.2 3.0` returns the 8 reference triangles that form the fragment. The remake has no fragment there; the same box on the remake holds only arc facets lying on the gusset-band plane, so check it against a rendered STL rather than with `region.py`, which reads the reference set. Both cut boundaries terminate on the same plane, x 23.300 in the model frame, confirming the cut follows the gusset band and not the divider in either set. The overhang cannot occur on c212 and g212, where the gusset fully spans the divider, and no fragment exists there.

Building the cut boundary from the divider positions instead was tried and rejected: it makes the remake keep the entire divider foot through that strip, which the originals do not, and it raises the sampled deviation on c313 from 0.010 to 0.133 in both directions.

The fragment is left unreproduced. It has the signature of boolean residue rather than a designed feature, and its 0.1333 width is a third of a 0.4 mm nozzle, so it cannot print however the other two dimensions fall (both are about one 0.2 mm layer). It accounts for the 0.133 worst case on those two models, inside the 0.2 gate. The remake's own corner of the same cut, at (73.300, -146.950, 1.6502), reads 0.0500 in the opposite direction.

Scaling on configurations with no reference: a wider drawer can place a divider further outside its gusset band, widening the affected strip but not deepening the cut. On a 4 LU wide, 4-section drawer the cavity spans -95.5 to 95.5, so the dividers land at +/-[47.5, 48.5] and +/-0.5, and the outer ones overhang their bands by 0.800. Measured there, from the project root, on a 4 LU wide, 1 LU tall, 2 LU deep drawer with 4 width sections (`python analysis\probe_divider_foot.py out\v_44.stl -48.15 -48.6 -97`): material is absent only at 0.05 behind the front wall inner face at z 1.62, and present at z 1.70 there and at every height 0.2 or more behind that face. The notch above the floor top measures 0.1010 by 0.1010, below print resolution, and does not weaken the divider.

## D1. Detent bump variant split (internal inconsistency in the originals, reproduced)

The side detent bump exists in two variants across the nine originals. Figures below are the originals' own measurements; the remake reproduces each to within 0.0005.

- Five models, all 1 LU tall and at least 2 LU wide (m212, c212, g212, c313, c3135): face bottom z 2.2825, top half-length 1.500.
- Four models (n111, s111, L323, L332; every 1-LU-wide or 2+-LU-tall reference): face bottom z 2.5653, top half-length 1.300.

Face plane at |x| = half - 1.5754, face top z 3.6967, shelf plane z 1.5754 on all nine.

Evidence: `python sections.py m212 y -96` and `python sections.py n111 y -46`; a plane survey of the -X face separates the two groups cleanly.

The remake reproduces the split with the rule: the 2.282 variant when height = 1 LU and width >= 2 LU, else the 2.565 variant. That matches all nine references; for novel configurations it extends the observed pattern.

## D2. g212 depth-divider placement (internal inconsistency in the original, reproduced)

g212's width divider makes exactly equal compartments (faces at x +/-0.500, the equal split of the 91 mm cavity), but its depth divider does not: faces at y -49/-50, back face on the cavity midpoint -49, making the rear compartment 48 mm and the front 47 mm instead of 47.5/47.5. Centring it would put the faces at -49.5/-48.5.

Evidence: `python sections.py g212 z 20`.

The remake reproduces this rule (depth-divider back faces on the equal division lines), so g212 matches. The entry documents the rule for configurations with three or more depth sections, which have no original example.

## D7. Back cavity corner chamfer fades out inside the wall lean (faithful, not a defect)

The 0.414 leg chamfer on the two back cavity corners shrinks as the back wall leans inward, following leg(z) = 0.414 - (z - lean0)/4 and reaching zero about 6.34 below the wall top, so the top of that corner is square. This looks like a truncation but reproduces the originals exactly.

Evidence: `python sections.py n111 z 31 --raw` on the original returns the corner run (20.2175,-1.3180) (20.4038,-1.3180) (20.5000,-1.4142), a leg of 0.0962 at z 31 against the leaning face at y -1.318. The same law holds on the original at z 29.928 (0.3642), 30 (0.3462) and 31.228 (0.0392), with the corner square by z 31.5, and it holds on L323 in its own lean zone. Forcing the chamfer to run to the wall top would break the match.

Consequence for configurations with no original: on a 0.5 LU tall drawer the wall top is 12.728 and the floor blends already occupy everything below 6.6, so the back corner reads as square over its whole exposed height. That follows the original's own rule rather than a separate decision.

## D8. Sub-micron vertex pairs from the hull-slab constant

Several transitions are built by lofting between two thin slabs placed on their nominal planes, with the slab thickness set by `hs = 0.0005`. That leaves vertex pairs closer together than the originals ever place them: the binary exports carry 40 to 96 pairs under 0.001 apart, where the closest pair in any original is 0.0238.

Measured consequence: at native precision every export is watertight, winding-consistent, single-bodied and free of any edge shared by other than two faces, in both ASCII and binary. But a tool that re-welds vertices at a 0.001 tolerance collapses those pairs and makes the mesh non-manifold (53 bad edges on n111, 84 on c313), where the originals survive the same treatment untouched.

Left as is. Raising `hs` would trade a real tenfold increase in the systematic surface residual for a hypothetical repair step, and the model is watertight as delivered. Anyone re-welding these meshes should use a tolerance below 0.0005, or simply not weld: no repair is needed.

## D6. Corner-brace tangency at the wall top (found, then fixed)

Recorded because it shaped the corner-brace construction, and because it is the kind of defect a reference comparison cannot see.

The brace's leaning faces met the side wall's two faces edge-on at the wall top, where the wall's faces stop. Surfaces that touch along a line rather than crossing make CGAL emit duplicated facets. Symptoms were a pair of non-manifold edges 3.8147e-06 long in binary export on drawers 2 LU or taller, and genuinely non-watertight output at some depth and height combinations, where one facet was emitted three times, leaving three edges shared by four faces and the mesh splitting into four components. A 1 LU wide, 3 LU tall, 1 LU deep drawer was among the failures.

An earlier attempt had already moved the flange profile below the wall top and offset the band outboard, which did not help: the leaning faces still landed on the wall planes at that height. The fix that worked gives the band a short skirt running 0.5 below the wall top exactly on the wall's own two faces, so the two merge into one flat face instead of touching along a line.

Verification: `analysis\manifold_grid.py` sweeps 75 depth and height combinations and reports every one exporting a clean single shell; an independent audit reproduced that result with its own sweep, and confirmed the superseded `frozen_round5.scad` still fails at 1x3x1 in ASCII and on every drawer 2 LU or taller in binary. Binary export of the 3x2x3 and 3x3x2 is now watertight with zero non-manifold edges. The reference match is unchanged: Gate 1 numbers are identical before and after, to four decimals on every model.

## D9. Off-grid widths near 2.3 LU export a broken ASCII STL (not reachable from the customizer)

At `width_lu` values of 2.26, 2.28, 2.30 and 2.32 the ASCII export contains 10 duplicated facets and 10 edges shared by four faces, and is not watertight; the binary export of the same solid is clean, and 2.24 and 2.34 are clean in both. The affected band is half-widths 53.0 to 54.5 mm and is independent of depth, height, section counts, magnet, label and divider height.

Cause: the front cavity corner fade band of D3a passes very close to the front floor fillet, and the resulting sliver is thin enough that whether the exporter emits it once or twice comes down to coordinate rounding.

Reachability: none through the declared parameters. Width steps by 0.5 LU, so on-grid half-widths step by 12.5 mm (46.5, then 59.0) and straddle the band entirely. Audits probed all 23 on-grid widths, 23 depths and 24 heights, plus several hundred full configurations, and found every one clean in both formats; only a hand-typed off-grid width reaches it.

Left as is, and recorded because it marks that sliver as the model's thinnest construction. Anyone changing the front-corner fade geometry should re-run `analysis\manifold_grid.py` and a width scan before trusting the result.

Related and now fixed: the feature gates for the label frame and magnet pocket were written as millimetre thresholds on the outer height (30 for the label, 35.5 for the magnet) rather than as the layout-unit rule they stand for. Off-grid heights therefore built features they should have omitted: from 0.74 LU up the label frame was built, and it fused into the pull lip; from 0.85 LU up the magnet pocket was built as well. The gates now test the height in layout units directly, so both are omitted below 1 LU at any input. On-grid behaviour is unchanged, since 0.5 LU gated off before and still does and 1 LU built both before and still does; Gate 1 is identical to four decimals on all nine models before and after.

## D4. Parametrization decisions with no original example

- Fractional widths: full 50 mm cells are centered, and the magnet pockets and lip gussets follow those centers. The back scoop does not: it is driven from the half-width so its flat always ends 18.544 short of the side wall. On whole-LU widths that is identical to the outer cell centers plus 2.956, which is what the originals measure; on half-LU widths it keeps the same shoulder instead of leaving 12.5 of extra full-height wall at each end.
- Fractional heights: a back-wall groove and side-wall jogs appear at every internal 50 mm height boundary, matching the shell rib pitch.
- Divider height d LU puts divider tops at 50d - 12.272, clamped to the wall height.
- Label sizing: `large` uses the 2-cell frame (76.4 mm window) where the drawer is at least 2 LU wide, and falls back to the 1-cell frame (26.4 mm window) below that, with an echoed note. `small` always uses the 1-cell frame and echoes nothing.
- Feature gates: the label frame and the magnet pocket each require a full layout unit of height. Below 1 LU both are omitted with an echoed warning rather than emitting geometry that hangs below the base or opens through the scooped back edge.
- Corner brace flange length is 8H + 2, clamped to 50D - 5 so the braces cannot pierce the front wall of a tall shallow drawer.
- Magnet on drawers taller than 1 LU: the 4 mm back wall runs full height, outer grooves still cut 1 mm deep, and pockets stay bottom-referenced at each cell center. Divider back flares run the full divider height against that flat wall, matching the front flares.

## Countersign

Audited independently against the originals, claim by claim, twice.

The first audit refused to countersign and named four errors: the front cavity corner band was undocumented and the divider flare was wrongly credited as the global worst case; a parenthetical claimed the remake carries an arc facet on the divider face plane; the exposed strip on a 4 LU wide 4-section drawer was given as 0.3 when it measures 0.800; and the label sizing rule wrongly said both fallback cases echo a note.

The second audit confirmed those four corrections and verified seven entries outright, including the D5 fragment, the D6 fix, the D7 chamfer fade, the D8 vertex pairs and the D9 off-grid band, most to four decimal places. It named five further errors, all corrected above: a false claim that sampling found no points in the front-corner band, which came from an argument-handling bug in `probe_flare.py` (now fixed); the divider flare's 0.0616 offset placed at the wrong end of the chamfer; a stale description of the millimetre feature gates that the file no longer contains; and two miscounts of how many models reach 0.0113. It also confirmed that no deviation above 0.05 mm anywhere is undocumented, and that no on-grid configuration fails to produce a sound mesh.

A targeted re-audit of the corrected passages then verified all five corrections and re-verified every entry against its own fresh renders, confirmed that `VERIFICATION.md` reproduces row for row, and countersigned the document. Its three remaining notes, the exact notch size, the layer-height wording, and the working directory of one evidence command, are folded into D5 above.
