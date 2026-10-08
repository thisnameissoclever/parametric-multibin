# VERIFICATION - Gate 1 mechanical match

Harness: `analysis\compare.py`, run 2026-08-29 07:31 UTC, 50000 surface samples per direction per model, bbox-aligned.

Thresholds: bbox delta <= 0.02 mm/axis; volume delta <= 0.5 %; p99 <= 0.05 mm; max <= 0.2 mm (excursions above must be covered in DEVIATIONS.md).

| model | bbox dmax (mm) | vol delta (%) | p99 (worse dir) | sampled max | all-vertices max | gate |
|---|---|---|---|---|---|---|
| n111 | 0.0000 | 0.004 | 0.0013 | 0.0072 | 0.0113 | PASS |
| s111 | 0.0000 | 0.004 | 0.0013 | 0.0057 | 0.0113 | PASS |
| m212 | 0.0000 | 0.003 | 0.0013 | 0.0056 | 0.0110 | PASS |
| c212 | 0.0000 | 0.004 | 0.0013 | 0.0056 | 0.0113 | PASS |
| g212 | 0.0000 | 0.005 | 0.0013 | 0.0095 | 0.0113 | PASS |
| L323 | 0.0000 | 0.002 | 0.0008 | 0.0056 | 0.0112 | PASS |
| L332 | 0.0000 | 0.002 | 0.0007 | 0.0055 | 0.0113 | PASS |
| c313 | 0.0000 | 0.004 | 0.0013 | 0.0106 | 0.1333 | PASS |
| c3135 | 0.0000 | 0.004 | 0.0013 | 0.0103 | 0.1333 | PASS |

A PASS* row would mean every threshold met except a localized max excursion covered by DEVIATIONS.md; no row currently needs it.

The all-vertices column is a deterministic sweep of every mesh vertex against the opposing surface, in both directions. It is reported because random surface sampling understates deviations that follow an edge rather than covering a patch: on the two 3-wide divided models it reads 0.010 where the true worst case is 0.133.

## Provenance

File verified: `MultiBin Simple Drawer - Parametric.scad`, sha256 85487774FE3198E0EAA4B1342B4FC1D6006A1B7664ECC542CD957FD046D97E03.
Renderer: OpenSCAD 2021.01. Every render exits 0 with no warning or error; the
nine reference configurations trigger none of the file's own echo() notices.

Beyond the nine references, `analysis\sweep.py` checks 15 varied configurations
and `analysis\manifold_grid.py` sweeps 75 depth and height combinations; all
export a watertight, winding-consistent single shell with the expected outer box
and a base on z = 0. Independent audits extended this to 428 configurations and
856 exports in both STL formats with the same result.

Known deviations, each with measured evidence, are listed in DEVIATIONS.md. The
only one above 0.05 mm is D5, a 0.133 mm fragment the two 3-wide divided
originals carry and the remake does not.

## Raw harness output

```text
[n111] bbox ref=[43. 57. 43.] gen=[43. 57. 43.] maxdelta=0.0000  vol ref=12603.5 gen=12604.0 (0.004%)
[n111] ref->gen: all-vertices max=0.0015 at (16.207, -4.057, 1.993)
[n111] gen->ref: all-vertices max=0.0113 at (-20.116, -46.950, 5.903)
[s111] bbox ref=[43. 57. 43.] gen=[43. 57. 43.] maxdelta=0.0000  vol ref=12771.4 gen=12771.9 (0.004%)
[s111] ref->gen: all-vertices max=0.0015 at (16.207, -4.057, 1.993)
[s111] gen->ref: all-vertices max=0.0113 at (-20.116, -46.950, 5.903)
[m212] bbox ref=[ 93. 107.  43.] gen=[ 93. 107.  43.] maxdelta=0.0000  vol ref=42189.6 gen=42190.8 (0.003%)
[m212] ref->gen: all-vertices max=0.0016 at (67.146, -95.398, 2.932)
[m212] gen->ref: all-vertices max=0.0110 at (70.117, -96.950, 5.903)
[c212] bbox ref=[ 93. 107.  43.] gen=[ 93. 107.  43.] maxdelta=0.0000  vol ref=39204.9 gen=39206.4 (0.004%)
[c212] ref->gen: all-vertices max=0.0020 at (26.052, -1.552, 4.317)
[c212] gen->ref: all-vertices max=0.0113 at (70.117, -96.950, 5.903)
[g212] bbox ref=[ 93. 107.  43.] gen=[ 93. 107.  43.] maxdelta=0.0000  vol ref=43281.4 gen=43283.4 (0.005%)
[g212] ref->gen: all-vertices max=0.0022 at (25.502, -48.998, 6.477)
[g212] gen->ref: all-vertices max=0.0113 at (70.117, -96.950, 5.903)
[L323] bbox ref=[143. 157.  93.] gen=[143. 157.  93.] maxdelta=0.0000  vol ref=100853.4 gen=100855.2 (0.002%)
[L323] ref->gen: all-vertices max=0.0018 at (119.023, -146.668, 4.809)
[L323] gen->ref: all-vertices max=0.0112 at (120.117, -146.950, 5.903)
[L332] bbox ref=[143. 107. 143.] gen=[143. 107. 143.] maxdelta=0.0000  vol ref=112255.2 gen=112257.2 (0.002%)
[L332] ref->gen: all-vertices max=0.0015 at (-16.207, -4.057, 1.993)
[L332] gen->ref: all-vertices max=0.0113 at (120.117, -96.950, 5.903)
[c313] bbox ref=[143. 157.  43.] gen=[143. 157.  43.] maxdelta=0.0000  vol ref=78173.0 gen=78176.4 (0.004%)
[c313] ref->gen: all-vertices max=0.1333 at (73.167, -147.000, 1.500)
[c313] gen->ref: all-vertices max=0.0500 at (73.300, -146.950, 1.650)
[c3135] bbox ref=[143. 182.  43.] gen=[143. 182.  43.] maxdelta=0.0000  vol ref=87897.0 gen=87900.6 (0.004%)
[c3135] ref->gen: all-vertices max=0.1333 at (73.167, -172.000, 1.500)
[c3135] gen->ref: all-vertices max=0.0500 at (73.300, -171.950, 1.650)



```
