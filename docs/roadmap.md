# Roadmap

Planned work for the generators, with the agreed design wherever one exists. Each item keeps the ID it was given in discussion (for example P2 or C6), so it can be referred to unambiguously; IDs are never renumbered.

## Contents

- [Simple drawer](#simple-drawer)
  - [Accepted, design still to do](#accepted-design-still-to-do)
  - [Parked: embossed faceplate text](#parked-embossed-faceplate-text)
  - [Considered and not planned](#considered-and-not-planned)
- [Shell generator, later versions](#shell-generator-later-versions)
- [Both parts](#both-parts)

## Simple drawer

### Accepted, design still to do

- **[P4] Skip individual dividers.** A mask such as `1,1,0` omits a divider so two cells merge. Combines with the uneven compartment sizes of `width_ratios` and `depth_ratios`.
- **[P6] One label frame per compartment.** For a divided drawer, a small frame over each column instead of one large frame. This changes the faceplate, so it must default to off and needs the full reference comparison, not only the soundness checks.
- **[P8] Sloped floor.** The interior floor tilts a few degrees toward the front so small parts collect under the scoop.

### Parked: embossed faceplate text

**[P5]** Raised or engraved text on the faceplate, typed in the Customizer.

Multicolour printing is the open question. Slicers split a model into parts by disconnected shells, and text unioned into the faceplate is part of one connected shell, so "split to parts" cannot separate it. OpenSCAD's experimental lazy union, which keeps top-level objects separate, is not available in 2021.01. The approach that works is a part selector parameter (`part = "drawer"` or `part = "text"`): the user renders twice, and both files share one coordinate frame, so they assemble exactly in the slicer as two parts of one object with different filaments.

The faceplate is vertical in the print orientation, so the text spans the same layers as the wall beside it, and a single colour change at one layer height does not work. Two-colour text needs a multi-material printer, or text placed on a horizontal surface such as the floor.

Fonts are a second risk: `text()` needs a font that exists in MakerWorld's renderer, which has not been checked beyond the usual default of Liberation Sans.

### Considered and not planned

Tim chose not to pursue these when selecting drawer features:

- **[P1]** Print-fit clearance offset.
- **[P7]** Press-fit pockets for real magnets.
- **[P9]** Drain or lightening holes in the floor.
- **[P10]** Pull style selector.
- **[P12]** Lid or stacking rim.

## Shell generator, later versions

The first shell generator covers the Standard Base with the Topped Rail, Topless Rail and Simple walls, one wall choice per side, at the drawer generator's sizes. These items are for later versions.

- **[C6] Paired mode.** One script with a part selector that outputs the shell, the drawer, or both from the same size settings, so they cannot be mismatched. The cost is one very large file.
- **[U2] Per-unit rail selection.** Keep the four per-side dropdowns, and add four optional text fields with one letter per LU along that side: `T` topped rail, `O` topless (open) rail, `S` simple. A blank field means the dropdown applies to the whole side. A short string pads with the dropdown's value, extra letters are ignored, and an unknown letter falls back to the dropdown with a console warning. The first version ships [U1] one dropdown per side; this follows if mixing within a side turns out to be needed.
- **[C1] Other base types.** MultiBuild also publishes the Standard Click-In Extension, Universal Click-In Extension and Baseless Extension bases; the extensions add a Shell Position choice of Edge or Center. Each needs its own reference set.
- **[C4] Micro and Shell Rings walls.** Not yet inspected.
- **[C8] A drawer depth of 0.5 LU.** One of MultiBuild's rail files is named for a 0.5 LU bin, which suggests shells that shallow exist. No shell reference at that depth is in hand to rebuild from, and the drawer generator's depth also starts at 1 LU.
- **[C7] Render time on MakerWorld.** MakerWorld's Parametric Model Maker may stop a render that runs too long, and its limit is not known. Test the default shell there once the first version has merged. If it times out, add a faster, less exact detail option; the threads of the holes took 24 to 37 % of the render time at the three sizes measured, so they are the first candidate.
- **[C9] Test print of a 25 x 25 mm pad.** A shell with a half LU in both width and front-to-back size has one 25 x 25 mm pad. Its single threaded hole has four clip pockets around it, the nearest 1.0 mm away. The walls are no thinner than published ones: each hole of MultiBuild's own 1 x 1 x 1 shell has three clip pockets around it, the nearest 0.95 mm away. What no published shell has is a hole with four clip pockets. Print a 1.5 x 1.5 x 1 shell and check that the hole holds its bolt; if it does not, take the corner pockets off that pad.

Decided against for now:

- **[C3]** Heights of 0.25 and 0.75 LU, which MultiBuild publishes. The shell follows the drawer generator's 0.5 LU steps instead, because the two are meant to be used together.
- **[C5]** A print-fit clearance offset. Shells match MultiBuild's dimensions exactly.

## Both parts

- **Reference coverage.** Each part's regression gate reports any missing reference file on every run. A restored file makes the gate fail until the baseline is relocked, so it cannot sit outside the drift check unnoticed.
- **Magnet pockets at half-LU widths.** A magnet drawer's back-wall pockets and the shell's central base pockets share one outline and appear to be magnet partners. At half-LU widths they miss by 12.5 mm: the drawer generator centres its magnet cells, and the shell lays its cells out from the -x end. Placing the drawer's magnet pockets from its -x end, 50 mm apart, would line them up at every width and change nothing at whole widths. Awaiting Tim's decision.
- **Drawer gate.** The shell's gate gained checks the drawer's gate lacks: failing on a missing reference, a locked vertex digest for sizes without a reference, a relock that refuses unaccepted drift, tests of its whole run, and a mutation check. Port them to the drawer's gate.
