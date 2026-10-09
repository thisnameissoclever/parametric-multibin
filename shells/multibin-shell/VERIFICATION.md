# VERIFICATION - shell Gate 1 mechanical match

Harness: `analysis/compare.py`, run 2026-10-09 17:54 UTC, 50000 surface samples per direction per model, bounding-box aligned, plus a sweep of every vertex in both directions.

File verified: `MultiBin Shell - Parametric.scad`, SHA-256 084192F7561A4FC445B059B29CC19EF72D3A1AC042B3BBDB218D01F718D45D5E, computed with LF line endings as git stores the file (`git show <commit>:"shells/multibin-shell/MultiBin Shell - Parametric.scad" | sha256sum`).

Renderer: OpenSCAD version 2021.01.

Columns: bbox dmax is the largest difference between the two bounding boxes on any axis; vol delta is the volume difference as a percentage of the reference's; p99 is the 99th percentile of the distances from sampled surface points to the other mesh, in whichever direction (reference to render, or render to reference) is worse; sampled max is the largest of those distances; and all-vertices max is the largest distance from any vertex of either mesh to the other.

Thresholds (`docs/verification-method.md`): bounding box <= 0.02 mm per axis, volume <= 0.5 %, p99 <= 0.05 mm, maximum <= 0.2 mm. The sound column means watertight and consistently wound with positive volume, one body (counted through shared edges), every edge shared by exactly two faces, no duplicated facets, and no two triangles that share at most one vertex crossing by more than 0.001 mm. The gate column is PASS only when every limit is met, the mesh is sound and the render printed nothing beyond OpenSCAD's normal statistics.

A feature smaller than the 0.2 mm maximum, such as a 0.2 mm opening chamfer or a 0.1 mm slit, could be missing without failing these limits; the regression gate (`analysis/regress.py`) holds every reference to its locked worst point within 0.002 mm, which catches that.

The sampled columns can differ in the fourth decimal between runs, because OpenSCAD does not write its triangles in a fixed order; the bounding box, volume and all-vertices columns repeat.

| model | bbox dmax (mm) | vol delta (%) | p99 (worse dir) | sampled max | all-vertices max | sound | render (s) | gate |
|---|---|---|---|---|---|---|---|---|
| T111 | 0.0000 | 0.011 | 0.0107 | 0.0170 | 0.0188 | yes | 16 | PASS |
| T212 | 0.0000 | 0.009 | 0.0100 | 0.0170 | 0.0188 | yes | 29 | PASS |
| T313 | 0.0000 | 0.008 | 0.0099 | 0.0168 | 0.0188 | yes | 46 | PASS |
| T3135 | 0.0000 | 0.007 | 0.0089 | 0.0173 | 0.0188 | yes | 51 | PASS |
| T323 | 0.0000 | 0.009 | 0.0104 | 0.0171 | 0.0188 | yes | 74 | PASS |
| T1215 | 0.0000 | 0.010 | 0.0103 | 0.0180 | 0.0188 | yes | 27 | PASS |
| O111 | 0.0000 | 0.013 | 0.0116 | 0.0169 | 0.0188 | yes | 16 | PASS |
| O212 | 0.0000 | 0.009 | 0.0108 | 0.0168 | 0.0188 | yes | 30 | PASS |
| O323 | 0.0000 | 0.009 | 0.0105 | 0.0176 | 0.0188 | yes | 77 | PASS |
| O1215 | 0.0000 | 0.011 | 0.0107 | 0.0170 | 0.0188 | yes | 27 | PASS |
| S111 | 0.0000 | 0.006 | 0.0095 | 0.0171 | 0.0188 | yes | 12 | PASS |
| S212 | 0.0000 | 0.004 | 0.0071 | 0.0179 | 0.0188 | yes | 21 | PASS |
| S323 | 0.0000 | 0.004 | 0.0074 | 0.0175 | 0.0188 | yes | 54 | PASS |
| S1215 | 0.0000 | 0.005 | 0.0088 | 0.0177 | 0.0188 | yes | 20 | PASS |

Every render printed nothing beyond OpenSCAD's normal statistics.
