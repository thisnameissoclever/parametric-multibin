# VERIFICATION - shell Gate 1 mechanical match

Harness: `analysis/compare.py`, run 2026-10-08 23:00 UTC, 50000 surface samples per direction per model, bounding-box aligned, plus a sweep of every vertex in both directions.

File verified: `MultiBin Shell - Parametric.scad`, SHA-256 3CDD67BA11E88F1CC4F025DD7315C9EE04DD2D9E535EC07A5FD82BFDCC601A63.

Renderer: OpenSCAD version 2021.01.

Thresholds (`docs/verification-method.md`): bounding box <= 0.02 mm per axis, volume <= 0.5 %, p99 <= 0.05 mm, maximum <= 0.2 mm. The sound column means watertight, one body, every edge shared by exactly two faces and no duplicated facets.

| model | bbox dmax (mm) | vol delta (%) | p99 (worse dir) | sampled max | all-vertices max | sound | render (s) | gate |
|---|---|---|---|---|---|---|---|---|
| T111 | 0.0000 | 0.014 | 0.0109 | 0.0174 | 0.0188 | yes | 17 | PASS |
| T212 | 0.0000 | 0.011 | 0.0105 | 0.0182 | 0.0188 | yes | 32 | PASS |
| T313 | 0.0000 | 0.009 | 0.0100 | 0.0183 | 0.0189 | yes | 52 | PASS |
| T3135 | 0.0000 | 0.009 | 0.0096 | 0.0173 | 0.0189 | yes | 56 | PASS |
| T323 | 0.0000 | 0.011 | 0.0105 | 0.0182 | 0.0189 | yes | 84 | PASS |
| T1215 | 0.0000 | 0.013 | 0.0107 | 0.0179 | 0.0188 | yes | 30 | PASS |
| O111 | 0.0000 | 0.016 | 0.0117 | 0.0174 | 0.0188 | yes | 17 | PASS |
| O212 | 0.0000 | 0.012 | 0.0112 | 0.0177 | 0.0188 | yes | 33 | PASS |
| O323 | 0.0000 | 0.012 | 0.0106 | 0.0173 | 0.0189 | yes | 85 | PASS |
| O1215 | 0.0000 | 0.014 | 0.0109 | 0.0179 | 0.0188 | yes | 30 | PASS |
| S111 | 0.0000 | 0.009 | 0.0100 | 0.0177 | 0.0188 | yes | 14 | PASS |
| S212 | 0.0000 | 0.005 | 0.0077 | 0.0176 | 0.0188 | yes | 24 | PASS |
| S323 | 0.0000 | 0.006 | 0.0082 | 0.0179 | 0.0189 | yes | 62 | PASS |
| S1215 | 0.0000 | 0.007 | 0.0092 | 0.0182 | 0.0188 | yes | 23 | PASS |

PASS* means every limit is met except a localized maximum covered by DEVIATIONS.md.

Every render printed no warning, error or nonplanar-face notice.
