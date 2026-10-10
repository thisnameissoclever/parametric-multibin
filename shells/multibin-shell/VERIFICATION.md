# VERIFICATION - shell Gate 1 mechanical match

Written by `analysis/regress.py --update-baseline` when it locked `analysis/baseline.json`, in a run from 2026-10-10 15:01 to 2026-10-10 15:55 UTC. The gate writes this file only when every check listed in `docs/verification-method.md` passes: every reference below meets every limit, every render is a sound mesh, and no render prints anything beyond OpenSCAD's normal statistics and the expected notes.

File verified: `MultiBin Shell - Parametric.scad`, SHA-256 ED7B180F3F57CE3298C1EF2AE963E02C610630583C9D132F3D929E83832D1B38, computed with Unix (LF) line endings, as git stores the file (`git show <commit>:"shells/multibin-shell/MultiBin Shell - Parametric.scad" | sha256sum`). A plain `regress.py` run fails if the generator is any other file.

Renderer: OpenSCAD version 2021.01.

Method: each render is moved so that the two bounding-box minimum corners coincide. Then 50000 points sampled on each surface are measured against the other mesh, and every vertex of each mesh is measured against the other.

Columns: bbox dmax is the largest difference between the two bounding boxes on any axis; vol delta is the volume difference as a percentage of the reference's; p99 is the 99th percentile of the sampled distances, in whichever direction (reference to render, or render to reference) is worse; sampled max is the largest sampled distance; and all-vertices max is the largest distance from any vertex of either mesh to the other.

Limits: bounding box <= 0.02 mm per axis, volume <= 0.5 %, p99 <= 0.05 mm, and both maxima <= 0.2 mm.

The sampled columns can differ between runs, p99 in the fourth decimal and the sampled maximum in the third, because OpenSCAD does not write its triangles in a fixed order, so the sample points differ; the bounding box, volume and all-vertices columns repeat.

| model | bbox dmax (mm) | vol delta (%) | p99 (worse dir) | sampled max | all-vertices max | render (s) |
|---|---|---|---|---|---|---|
| T111 | 0.0000 | 0.008 | 0.0092 | 0.0173 | 0.0188 | 28 |
| T212 | 0.0000 | 0.005 | 0.0060 | 0.0179 | 0.0188 | 54 |
| T313 | 0.0000 | 0.004 | 0.0037 | 0.0183 | 0.0188 | 90 |
| T3135 | 0.0000 | 0.003 | 0.0014 | 0.0173 | 0.0188 | 93 |
| T323 | 0.0000 | 0.006 | 0.0061 | 0.0184 | 0.0188 | 144 |
| T1215 | 0.0000 | 0.007 | 0.0081 | 0.0170 | 0.0188 | 51 |
| O111 | 0.0000 | 0.009 | 0.0091 | 0.0186 | 0.0188 | 27 |
| O212 | 0.0000 | 0.005 | 0.0061 | 0.0182 | 0.0188 | 54 |
| O323 | 0.0000 | 0.006 | 0.0065 | 0.0173 | 0.0188 | 144 |
| O1215 | 0.0000 | 0.007 | 0.0080 | 0.0177 | 0.0188 | 49 |
| S111 | 0.0000 | 0.007 | 0.0091 | 0.0177 | 0.0188 | 20 |
| S212 | 0.0000 | 0.004 | 0.0069 | 0.0185 | 0.0188 | 39 |
| S323 | 0.0000 | 0.005 | 0.0068 | 0.0181 | 0.0188 | 98 |
| S1215 | 0.0000 | 0.006 | 0.0083 | 0.0182 | 0.0188 | 39 |
