# Parametric MultiBin

OpenSCAD generators for MultiBoard's MultiBin storage parts (MultiBoard now trades as MultiBuild). Each generator is a single self-contained `.scad` file: paste the whole file into MakerWorld's Parametric Model Maker, or open it in OpenSCAD 2021.01 or later and use the Customizer, then choose the size and options you want.

For each size checked against MultiBuild's own files, a generator reproduces their part to within a few hundredths of a millimetre. For other sizes and options, it applies the same construction rules.

## Contents

- [Generators](#generators)
- [Using a generator](#using-a-generator)
- [How the generators are verified](#how-the-generators-are-verified)
- [Running the analysis tools](#running-the-analysis-tools)
- [Repository layout](#repository-layout)
- [Credit and license](#credit-and-license)

## Generators

Sizes are in LU, MultiBoard's 50 mm layout unit.

| Part | File | Settings |
|---|---|---|
| Simple drawer insert | [`drawers/simple-drawer/MultiBin Simple Drawer - Parametric.scad`](drawers/simple-drawer/MultiBin%20Simple%20Drawer%20-%20Parametric.scad) | Width and depth 1 to 12 LU and height 0.5 to 12 LU, all in 0.5 LU steps; 1 to 12 compartments across and front to back; divider height; magnet opening; label holder none, small or large |
| MultiBin shell, Standard Base | [`shells/multibin-shell/MultiBin Shell - Parametric.scad`](shells/multibin-shell/MultiBin%20Shell%20-%20Parametric.scad) | The same three sizes as the drawer that fits inside: width 1 to 12 LU, drawer height 0.5 to 12 LU (front to back as printed) and drawer depth 1 to 12 LU (height as printed), all in 0.5 LU steps; Topped Rail, Topless Rail or Simple wall on each side |

Planned work for each part is in [`docs/roadmap.md`](docs/roadmap.md).

## Using a generator

In MakerWorld's Parametric Model Maker, open the `.scad` file in a text editor, copy all of it, paste it into the editor, then set the parameters and generate.

In OpenSCAD, open the file, choose **Window > Customizer**, set the parameters, then render (F6) and export an STL.

A generator prints a `WARNING` or `NOTE` line in the console when it adjusts a request, for example when a feature needs a taller part than the one requested.

## How the generators are verified

Every generator is compared against MultiBuild's own STL files with a harness that measures bounding box, volume and surface distance in both directions, including a sweep of every vertex. Independent reviewers then try to break it, by reproducing the measurements from scratch, by auditing what each feature means, and by trying sizes MultiBuild never published. The method and its limits are in [`docs/verification-method.md`](docs/verification-method.md).

Each part folder holds three records: `REVERSE-ENGINEERING.md` for the measured construction, `DEVIATIONS.md` for every known difference from the originals with its evidence, and `VERIFICATION.md` for the dated harness results.

## Running the analysis tools

The tools need MultiBuild's original STL files, which this repository does not include because MultiBuild's license forbids redistributing them. Download them from [multibuild.io](https://multibuild.io) first.

1. Install OpenSCAD 2021.01 and Python 3.12. The shell's regression gate locks OpenSCAD 2021.01's output, including its console lines; another version may fail it until the baseline is relocked.
2. Copy `local-paths.example.json` to `local-paths.json` and set the folders holding your reference files. Environment variables `OPENSCAD` and `MULTIBIN_REFS_<PART>` override the file.
3. Create the environment:

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```

4. Run a part's regression gate, for example the drawer's:

   ```powershell
   .venv\Scripts\python drawers\simple-drawer\analysis\regress.py
   ```

Generated meshes go to `.local-build/out/`, which git ignores and which is safe to delete.

The regression baselines were recorded with Python 3.12.10 and the package versions in `requirements.txt`. If a fresh setup reports drift without any change to a generator, check the interpreter with `.venv\Scripts\python --version` and the packages with `.venv\Scripts\python -m pip freeze` before suspecting the geometry; random sampling and mesh libraries can shift slightly between versions.

## Repository layout

| Path | Contents |
|---|---|
| `drawers/simple-drawer/` | The drawer generator and its records |
| `drawers/simple-drawer/analysis/` | Comparison harness, regression gate and baseline, and the measurement scripts cited as evidence in `DEVIATIONS.md` |
| `shells/multibin-shell/` | The shell generator and its records |
| `shells/multibin-shell/analysis/` | The same tools for the shell |
| `docs/` | Verification method, roadmap, lessons learned |
| `tools/mbpaths.py` | Resolves the OpenSCAD and reference-file locations for each machine |

## Credit and license

The generators are Remixed Designs of MultiBoard designs by MULTIBOARD LTD, [multibuild.io](https://multibuild.io), and are distributed under the [MultiBuild License](https://multibuild.io/license). See [`LICENSE.md`](LICENSE.md). This project is not affiliated with or endorsed by MULTIBOARD LTD.
