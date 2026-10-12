# VERIFICATION - shell Gate 1 mechanical match

Written by `analysis/regress.py --update-baseline` when it locked `analysis/baseline.json`, in a run from 2026-10-12 16:40 to 2026-10-12 17:10 UTC. `docs/verification-method.md` lists what that run compares.

File verified: `MultiBin Shell - Parametric.scad`, SHA-256 704AFAD06A35F500663451FBB84FD3AF5BDE6CAC119B123A9DBCD7FE14230032, computed with CR LF line endings turned into LF. `git show <commit>:"shells/multibin-shell/MultiBin Shell - Parametric.scad" | sha256sum` prints the same digest in lower case when git holds the file with LF line endings.

Renderer: OpenSCAD version 2021.01.

Method: each render is moved so that the two bounding-box minimum corners coincide. Then 50000 points sampled on each surface are measured against the other mesh, and every vertex of each mesh is measured against the other.

Columns: bbox dmax is the largest difference between the two bounding boxes on any axis; vol delta is the volume difference as a percentage of the reference's; p99 is the 99th percentile of the sampled distances, in whichever direction (reference to render, or render to reference) is worse; sampled max is the largest sampled distance; and all-vertices max is the largest distance from any vertex of either mesh to the other. The two sampled columns vary a little from one run to the next.

Limits: bounding box <= 0.02 mm per axis, volume <= 0.5 %, p99 <= 0.05 mm, and both maxima <= 0.2 mm.

| model | bbox dmax (mm) | vol delta (%) | p99 (worse dir) | sampled max | all-vertices max | render (s) |
|---|---|---|---|---|---|---|
| T111 | 0.0000 | 0.008 | 0.0092 | 0.0174 | 0.0188 | 16 |
| T212 | 0.0000 | 0.005 | 0.0060 | 0.0177 | 0.0188 | 30 |
| T313 | 0.0000 | 0.004 | 0.0037 | 0.0183 | 0.0188 | 50 |
| T3135 | 0.0000 | 0.003 | 0.0014 | 0.0173 | 0.0188 | 60 |
| T323 | 0.0000 | 0.006 | 0.0061 | 0.0178 | 0.0188 | 84 |
| T1215 | 0.0000 | 0.007 | 0.0080 | 0.0180 | 0.0188 | 29 |
| O111 | 0.0000 | 0.009 | 0.0091 | 0.0186 | 0.0188 | 16 |
| O212 | 0.0000 | 0.005 | 0.0062 | 0.0182 | 0.0188 | 31 |
| O323 | 0.0000 | 0.006 | 0.0065 | 0.0173 | 0.0188 | 81 |
| O1215 | 0.0000 | 0.007 | 0.0079 | 0.0174 | 0.0188 | 29 |
| S111 | 0.0000 | 0.007 | 0.0092 | 0.0177 | 0.0188 | 12 |
| S212 | 0.0000 | 0.004 | 0.0069 | 0.0185 | 0.0188 | 22 |
| S323 | 0.0000 | 0.005 | 0.0068 | 0.0179 | 0.0188 | 55 |
| S1215 | 0.0000 | 0.006 | 0.0083 | 0.0182 | 0.0188 | 21 |
