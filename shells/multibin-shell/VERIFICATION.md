# VERIFICATION - shell Gate 1 mechanical match

Harness: `analysis/compare.py`, run 2026-10-09 16:08 UTC, 50000 surface samples per direction per model, bounding-box aligned, plus a sweep of every vertex in both directions.

File verified: `MultiBin Shell - Parametric.scad`, SHA-256 277DF969FF28367D0C078A98ABBE22FD76C421291B99B3DA9DED6C3DB5948437, computed with LF line endings as git stores the file (`git show <commit>:"shells/multibin-shell/MultiBin Shell - Parametric.scad" | sha256sum`).

Renderer: OpenSCAD version 2021.01.

Columns: bbox dmax is the largest difference between the two bounding boxes on any axis; vol delta is the volume difference as a percentage of the reference's; p99 is the 99th percentile of the distances from sampled surface points to the other mesh, in whichever direction (reference to render, or render to reference) is worse; sampled max is the largest of those distances; and all-vertices max is the largest distance from any vertex of either mesh to the other.

Thresholds (`docs/verification-method.md`): bounding box <= 0.02 mm per axis, volume <= 0.5 %, p99 <= 0.05 mm, maximum <= 0.2 mm. The sound column means watertight, one body (counted through shared edges), every edge shared by exactly two faces, no duplicated facets, and no two triangles crossing by more than 0.001 mm. The gate column is PASS only when every limit is met, the mesh is sound and the render printed nothing beyond OpenSCAD's normal statistics.

The sampled columns can differ in the fourth decimal between runs, because OpenSCAD does not write its triangles in a fixed order; the bounding box, volume and all-vertices columns repeat.

| model | bbox dmax (mm) | vol delta (%) | p99 (worse dir) | sampled max | all-vertices max | sound | render (s) | gate |
|---|---|---|---|---|---|---|---|---|
| T111 | 0.0000 | 0.014 | 0.0109 | 0.0174 | 0.0188 | yes | 15 | PASS |
| T212 | 0.0000 | 0.011 | 0.0105 | 0.0183 | 0.0188 | yes | 29 | PASS |
| T313 | 0.0000 | 0.009 | 0.0100 | 0.0183 | 0.0188 | yes | 47 | PASS |
| T3135 | 0.0000 | 0.009 | 0.0098 | 0.0173 | 0.0188 | yes | 51 | PASS |
| T323 | 0.0000 | 0.011 | 0.0105 | 0.0178 | 0.0188 | yes | 74 | PASS |
| T1215 | 0.0000 | 0.013 | 0.0107 | 0.0178 | 0.0188 | yes | 27 | PASS |
| O111 | 0.0000 | 0.016 | 0.0118 | 0.0174 | 0.0188 | yes | 16 | PASS |
| O212 | 0.0000 | 0.012 | 0.0112 | 0.0177 | 0.0188 | yes | 29 | PASS |
| O323 | 0.0000 | 0.012 | 0.0106 | 0.0173 | 0.0188 | yes | 76 | PASS |
| O1215 | 0.0000 | 0.014 | 0.0109 | 0.0174 | 0.0188 | yes | 27 | PASS |
| S111 | 0.0000 | 0.009 | 0.0100 | 0.0177 | 0.0188 | yes | 12 | PASS |
| S212 | 0.0000 | 0.005 | 0.0076 | 0.0171 | 0.0188 | yes | 21 | PASS |
| S323 | 0.0000 | 0.006 | 0.0082 | 0.0179 | 0.0188 | yes | 54 | PASS |
| S1215 | 0.0000 | 0.007 | 0.0092 | 0.0182 | 0.0188 | yes | 21 | PASS |

Every render printed nothing beyond OpenSCAD's normal statistics.
