# Roadmap

Planned work for the generators, with the agreed design wherever one exists. Each item keeps the ID it was given in discussion (for example P2 or C6), so it can be referred to unambiguously; IDs are never renumbered.

## Contents

- [Simple drawer](#simple-drawer)
  - [Next drawer iteration](#next-drawer-iteration)
  - [Accepted, design still to do](#accepted-design-still-to-do)
  - [Parked: embossed faceplate text](#parked-embossed-faceplate-text)
  - [Considered and not planned](#considered-and-not-planned)
- [Shell generator, later versions](#shell-generator-later-versions)
- [Both parts](#both-parts)

## Simple drawer

### Next drawer iteration

These three start after the shell generator is signed off, in this order. The designs below were proposed in discussion and are the plan of record; Tim confirms them before implementation starts. Every change must keep the regression gate in `drawers/simple-drawer/analysis/regress.py` passing with the new parameters at their defaults, and each new parameter needs at least one non-default row in that gate's soundness list.

#### [P2] Uneven compartment sizes

Two free-text parameters in the Compartments section:

```
width_ratios = "";  // blank = equal
depth_ratios = "";
```

The usable cavity, total width minus the dividers' own thickness, is split in proportion to the numbers given. `2,1,1` on three width sections gives a first column twice as wide as each of the other two. `width_ratios` reads left to right; `depth_ratios` reads front to back, as you look into the drawer.

Input handling, so odd input never produces broken geometry:

- Fewer numbers than sections: pad with the last value given, so a single number always means equal sizes.
- More numbers than sections: ignore the extras.
- Blank, unparseable, or any value that is zero or negative: fall back to equal sizes and echo a warning.

OpenSCAD 2021.01 has no string-to-number function, so the generator carries a small parser built from `search()` and string indexing. The tested version is `drawers/simple-drawer/analysis/probe/parse_test.scad`. A text field is used instead of sliders because the Customizer can only show numeric vectors of up to four elements, and the drawer allows twelve sections.

Depth dividers must keep the measured placement rule: each divider's back face sits on its division line, as in the originals.

The front-bottom fillet cut is placed from the 50 mm cell boundaries, not from the divider positions (deviation D5), so uneven dividers do not move it. The comment above `divider_x()` currently says the opposite; correct it in the same change.

#### [P3] Divider finger scoops

```
divider_scoop = "none"; // [none, front, center]
divider_scoop_mm = 10;  // [2:1:40]
```

`front` ramps the top of each width divider down toward the front of the drawer, continuing the front wall's scoop inward. `center` cuts a notch in the middle of each divider's run so a finger can reach into a narrow cell. Both cuts have 45-degree walls and remove material from the top only, so they add no overhangs. `front` applies to width dividers only, because a depth divider runs side to side and has no front end; `center` applies to both.

#### [P11] Divider thickness

```
divider_thickness = 1.0; // [0.6:0.1:4]
```

Replaces the fixed `div_t = 1.0`. The end flares and the depth-divider placement already derive from `div_t`. Below 0.6 mm a divider is less than two extrusion widths of a 0.4 mm nozzle. If the resulting compartment width drops under 2 mm, echo a warning instead of producing a sliver.

### Accepted, design still to do

- **[P4] Skip individual dividers.** A mask such as `1,1,0` omits a divider so two cells merge. Combines with [P2] uneven compartment sizes.
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
- **[C7] Render time on MakerWorld.** MakerWorld's Parametric Model Maker may stop a render that runs too long, and its limit is not known. Test the default shell there once the first version has merged. If it times out, add a faster, less exact detail option; the threaded holes dominate render time, so they are the first candidate.

Decided against for now:

- **[C3]** Heights of 0.25 and 0.75 LU, which MultiBuild publishes. The shell follows the drawer generator's 0.5 LU steps instead, because the two are meant to be used together.
- **[C5]** A print-fit clearance offset. Shells match MultiBuild's dimensions exactly.

## Both parts

- **Reference coverage.** Each part's regression gate reports any missing reference file on every run. A restored file makes the gate fail until the baseline is relocked, so it cannot sit outside the drift check unnoticed.
- **Magnet pockets at half-LU widths.** A magnet drawer's back-wall pockets and the shell's central base pockets share one outline and appear to be magnet partners. At half-LU widths they miss by 12.5 mm: the drawer generator centres its magnet cells, and the shell lays its cells out from the -x end. Placing the drawer's magnet pockets from its -x end, 50 mm apart, would line them up at every width and change nothing at whole widths. Awaiting Tim's decision.
- **Drawer gate.** The shell's gate gained checks the drawer's gate lacks: failing on a missing reference, a locked vertex digest for sizes without a reference, a relock that refuses unaccepted drift, tests of its whole run, and a mutation check. Port them to the drawer's gate.
