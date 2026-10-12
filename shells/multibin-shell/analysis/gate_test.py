"""Unit tests for the shell's regression gate. They run in seconds and never
start OpenSCAD, though the tools they import need OpenSCAD's path and the
reference folder configured.

- The policy (the limits and lists docs/verification-method.md names) is
  compared with a literal copy, so no value changes without this file changing.
- The hard limits, the drift tolerances, the shape lock's volume tolerance, the
  crossing limit, the sample count and the 3MF counts are tested at their
  boundaries, and each 3MF merge distance at 0.999 and 1.001 of it.
- The mesh tools run on small synthetic meshes.
- The one render function runs against a stand-in for OpenSCAD.
- Every check in regress.CHECKS is driven through regress.run() with stand-in
  steps. The stand-ins record the arguments they are given, and a clean run is
  checked to have rendered, measured and examined exactly what the policy
  lists, from the SCAD file it was given, with the right output files and
  parameters.
- The real steps, the files they read and write and the command line are
  tested separately on small inputs.

Each run works in its own folders, .local-build/out/shell/gate_test/run_<pid>
and .local-build/out/shell/alt/other_<pid>, and removes them at the end, so two
runs at once do not share files.

Usage: python gate_test.py     (exits 1 if any test fails)
"""

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import trimesh

import compare
import export_check
import policy
import refs
import regress
from policy import REFERENCES, THREEMF_CHECK

HERE = Path(__file__).resolve().parent
TMP = compare.OUT / "gate_test" / f"run_{os.getpid()}"
OTHER_SCAD = TMP / f"other_{os.getpid()}.scad"          # a SCAD file that is not the generator
REF = REFERENCES[0]
CONF = "half_w_1.5x1x1"
REF_STL, CONF_STL, TMF_3MF = f"{REF}.stl", f"soundness/{CONF}.stl", f"soundness/{THREEMF_CHECK[0]}.3mf"
NOTE = policy.EXPECTED_MESSAGES["thin_1.5x0.5x1"][0]
NOTE_STL, NOTE_3MF = "soundness/thin_1.5x0.5x1.stl", "soundness/thin_1.5x0.5x1.3mf"

results = []
covered = set()         # the checks of regress.CHECKS that a test has driven through run()


def check(name, condition):
    results.append((name, bool(condition)))


# ------------------------------------------------------------------ small inputs

def stl(name, mesh):
    TMP.mkdir(parents=True, exist_ok=True)
    path = TMP / f"{name}.stl"
    mesh.export(path)
    return path


def cube(offset=(0, 0, 0)):
    return trimesh.creation.box(extents=(10, 10, 10)).apply_translation(offset)


def joined(*meshes):
    v, f, n = [], [], 0
    for m in meshes:
        v.append(m.vertices)
        f.append(m.faces + n)
        n += len(m.vertices)
    return trimesh.Trimesh(np.vstack(v), np.vstack(f), process=False)


def bowtie():
    """Two pyramids meeting tip to tip through each other: faces that cross
    while sharing a vertex."""
    v = np.array([[0, 0, 10], [-5, -5, 0], [5, -5, 0], [5, 5, 0], [-5, 5, 0]], dtype=float)
    bow = trimesh.Trimesh(v, np.array([[0, 1, 3], [0, 3, 2], [0, 2, 4], [0, 4, 1], [1, 2, 3], [2, 1, 4]]),
                          process=False)
    return stl("bowtie", bow)


def model(coords, tris=((0, 1, 1),)):
    """The text of a 3MF model holding these vertices and triangles."""
    verts = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in coords)
    faces = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}" />' for a, b, c in tris)
    return f'<model><mesh><vertices>{verts}</vertices><triangles>{faces}</triangles></mesh></model>'


def threemf(name, text):
    TMP.mkdir(parents=True, exist_ok=True)
    path = TMP / f"{name}.3mf"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("3D/3dmodel.model", text)
    return path


def fin(gap):
    """Two closed tetrahedra touching along an edge, with that edge's ends
    written twice, gap apart: merging vertices closer than gap folds the two
    copies of the edge into one edge with four triangles."""
    def tet(a, b, c, d):
        return [(a, c, b), (a, b, d), (b, c, d), (c, a, d)]
    coords = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1),
              (gap, 0, 0), (1 + gap, 0, 0), (0, -1, 0), (0, 0, -1)]
    return threemf(f"fin_{gap:g}", model(coords, tet(0, 1, 2, 3) + tet(4, 5, 6, 7)))


def row(bbox=0.0, vol=0.0, p99=(0.0, 0.0), mx=(0.0, 0.0), vmax=(0.0, 0.0), samples=policy.N_SAMPLES, key="K"):
    """A compare.measure row with chosen values."""
    return dict(key=key, bbox=bbox, vol=vol, samples=samples,
                **{tag: dict(mean=0.0, p95=0.0, p99=p99[i], mx=mx[i], vmax=vmax[i])
                   for i, tag in enumerate(("ref->gen", "gen->ref"))})


# ------------------------------------------------------------------ policy and decisions

def test_policy():
    def walls(front, back, left, right):
        return dict(front_wall=f'"{front}"', back_wall=f'"{back}"', left_wall=f'"{left}"', right_wall=f'"{right}"')
    kinds = ("topped", "topless", "simple")
    check("the rules are the documented ones", policy.RULES == dict(
        LIMITS=dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2),
        DRIFT=dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002),
        N_SAMPLES=50000, SAMPLE_SEED=7, P99=0.99, SOUND_VOL=0.01, CROSSING_LIMIT=1e-3, CORNER_TOL=1e-7,
        BARY_TOL=1e-10, MERGE_TOLS=(1e-5, 1e-4), EXPORT_FORMAT=("--export-format", "binstl"),
        NORMAL_RENDER_LINE=(
            r"^(Geometries in cache|Geometry cache size in bytes|CGAL Polyhedrons in cache|CGAL cache size in bytes"
            r"|Total rendering time|Top level object is a 3D object|Vertices|Halfedges|Edges|Halffacets|Facets):"
            r"|^Simple:\s+yes$|^Volumes:\s+2$")))
    check("the shell's coverage is the documented one", policy.SHELL == dict(
        REFERENCES=("T111", "T212", "T313", "T3135", "T323", "T1215", "O111", "O212", "O323", "O1215",
                    "S111", "S212", "S323", "S1215"),
        CUSTOMIZER=dict(width_lu=(1.0, 0.5, 12.0), height_lu=(0.5, 0.5, 12.0), depth_lu=(1.0, 0.5, 12.0),
                        front_wall=kinds, back_wall=kinds, left_wall=kinds, right_wall=kinds),
        SOUNDNESS=(
            ("defaults", {}),
            ("half_w_1.5x1x1", dict(width_lu=1.5, height_lu=1, depth_lu=1)),
            ("half_h_2x1.5x2", dict(width_lu=2, height_lu=1.5, depth_lu=2)),
            ("half_both_2.5x1.5x1.5", dict(width_lu=2.5, height_lu=1.5, depth_lu=1.5)),
            ("thin_1.5x0.5x1", dict(width_lu=1.5, height_lu=0.5, depth_lu=1)),
            ("deep_1x1x4", dict(width_lu=1, height_lu=1, depth_lu=4)),
            ("tall_1x1x12", dict(width_lu=1, height_lu=1, depth_lu=12)),
            ("wide_4x1x1", dict(width_lu=4, height_lu=1, depth_lu=1)),
            ("long_1x7x1", dict(width_lu=1, height_lu=7, depth_lu=1)),
            ("wide_12x1x1", dict(width_lu=12, height_lu=1, depth_lu=1)),
            ("long_1x12x1", dict(width_lu=1, height_lu=12, depth_lu=1)),
            ("long_mixed_2.5x7.5x1.5", dict(width_lu=2.5, height_lu=7.5, depth_lu=1.5,
                                            **walls("topped", "topped", "topless", "simple"))),
            ("mixed_walls_2x2x1", dict(width_lu=2, height_lu=2, depth_lu=1,
                                       **walls("topped", "topless", "simple", "topped"))),
            ("simple_2x1x2", dict(width_lu=2, height_lu=1, depth_lu=2, **walls("simple", "simple", "simple", "simple"))),
            ("topless_half_2.5x1.5x1.5", dict(width_lu=2.5, height_lu=1.5, depth_lu=1.5,
                                              **walls("topless", "topless", "topless", "topless"))),
            ("simple_half_1.5x2x2.5", dict(width_lu=1.5, height_lu=2, depth_lu=2.5,
                                           **walls("simple", "simple", "simple", "simple")))),
        THREEMF_CHECK=("thin_1.5x0.5x1", "half_both_2.5x1.5x1.5", "wide_4x1x1"),
        REJECTED=(
            ("width_near_step", dict(width_lu=1.000002), "width_lu must be a multiple of 0.5 from 1 to 12, not 1"),
            ("width_between_steps", dict(width_lu=1.25), "width_lu must be a multiple of 0.5 from 1 to 12, not 1.25"),
            ("width_below", dict(width_lu=0.5), "width_lu must be a multiple of 0.5 from 1 to 12, not 0.5"),
            ("width_above", dict(width_lu=12.5), "width_lu must be a multiple of 0.5 from 1 to 12, not 12.5"),
            ("height_near_step", dict(height_lu=0.500002),
             "height_lu must be a multiple of 0.5 from 0.5 to 12, not 0.500002"),
            ("height_between_steps", dict(height_lu=0.75), "height_lu must be a multiple of 0.5 from 0.5 to 12, not 0.75"),
            ("height_below", dict(height_lu=0), "height_lu must be a multiple of 0.5 from 0.5 to 12, not 0"),
            ("height_above", dict(height_lu=12.5), "height_lu must be a multiple of 0.5 from 0.5 to 12, not 12.5"),
            ("depth_near_step", dict(depth_lu=1.000002), "depth_lu must be a multiple of 0.5 from 1 to 12, not 1"),
            ("depth_between_steps", dict(depth_lu=1.25), "depth_lu must be a multiple of 0.5 from 1 to 12, not 1.25"),
            ("depth_below", dict(depth_lu=0.5), "depth_lu must be a multiple of 0.5 from 1 to 12, not 0.5"),
            ("depth_above", dict(depth_lu=12.5), "depth_lu must be a multiple of 0.5 from 1 to 12, not 12.5"),
            ("width_not_a_number", dict(width_lu='"a"'), "width_lu must be a multiple of 0.5 from 1 to 12, not a")),
        EXPECTED_MESSAGES={"thin_1.5x0.5x1": (
            "NOTE: left_wall = topped has no effect: the side is shorter than 1 LU, so it has no rail channel.",
            "NOTE: right_wall = topped has no effect: the side is shorter than 1 LU, so it has no rail channel.")}))
    check("every 3MF configuration is a listed configuration",
          set(THREEMF_CHECK) <= {n for n, _ in policy.SOUNDNESS})
    check("the reference list in refs.py is the policy's", refs.EXPECTED == list(REFERENCES))
    check("a reference key gives MultiBuild's file name, which differs for Simple Walls",
          refs.fname("T3135") == "3x1x3.5 LU - Topped Rail - MultiBin Shell.stl"
          and refs.fname("O212") == "2x1x2 LU - Topless Rail - MultiBin Shell.stl"
          and refs.fname("S1215") == "1x2x1.5 CU - Simple Walls - Multibin Shell.stl")
    topless = '"topless"'
    check("a reference key gives its size and wall kind as generator parameters",
          compare.params("O3135") == dict(width_lu=3, height_lu=1, depth_lu=3.5, front_wall=topless,
                                          back_wall=topless, left_wall=topless, right_wall=topless)
          and compare.params("S1215")["front_wall"] == '"simple"' and compare.params("T111")["left_wall"] == '"topped"')
    # the rejected values follow from the sliders: just off the lowest step, halfway to the next, one step
    # below the minimum and one step above the maximum
    probes = {name: p for name, p, _ in policy.REJECTED}
    derived = True
    for size in ("width", "height", "depth"):
        lo, step, hi = policy.CUSTOMIZER[f"{size}_lu"]
        want = dict(near_step=lo + 0.000002, between_steps=lo + step / 2, below=lo - step, above=hi + step)
        derived &= all(abs(probes[f"{size}_{k}"][f"{size}_lu"] - v) < 1e-12 for k, v in want.items())
    check("the rejected values follow from the sliders' ranges", derived)
    rendered = [p for _, p in policy.SOUNDNESS]
    ends = True
    for name in ("width_lu", "height_lu", "depth_lu"):
        lo, _, hi = policy.CUSTOMIZER[name]
        ends &= any(p.get(name) == lo for p in rendered) and any(p.get(name) == hi for p in rendered)
    check("both ends of every slider are rendered", ends)


def test_decisions():
    lim, drift, nan = policy.LIMITS, policy.DRIFT, float("nan")
    zero_drift = dict.fromkeys(drift, 0.0)
    for field, limit in lim.items():
        check(f"HARD {field} at the limit passes", not regress.hard_failures("K", dict(lim)))
        check(f"HARD {field} just over the limit fails", regress.hard_failures("K", dict(lim, **{field: limit + 1e-9})))
    check("HARD fails a metric that is not a number", regress.hard_failures("K", dict(lim, mx=nan)))
    s = compare.summary(row(p99=(0.01, 0.03), mx=(0.02, 0.01), vmax=(0.04, 0.05)))
    check("summary takes p99 from the worse direction", s["p99"] == 0.03)
    check("summary takes the maximum over samples and vertices, both directions", s["mx"] == 0.05)
    check("summary carries a value that is not a number into the maximum",
          np.isnan(compare.summary(row(vmax=(0.0, nan)))["mx"]) and np.isnan(compare.summary(row(p99=(nan, 0.0)))["p99"]))
    check("the required number of samples passes", not regress.sample_failures("K", row()))
    check("one sample fewer fails", regress.sample_failures("K", row(samples=policy.N_SAMPLES - 1)))
    check("one sample more fails", regress.sample_failures("K", row(samples=policy.N_SAMPLES + 1)))
    check("a locked metric missing from the baseline fails",
          len(regress.drift_failures("K", zero_drift, {k: v for k, v in zero_drift.items() if k != "p99"})) == 1
          and len(regress.drift_failures("K", zero_drift, {})) == len(zero_drift))
    zero = zero_drift
    for field, tol in drift.items():
        check(f"DRIFT {field} at the tolerance passes", not regress.drift_failures("K", dict(zero, **{field: tol}), zero))
        check(f"DRIFT {field} just over fails", regress.drift_failures("K", dict(zero, **{field: tol + 1e-9}), zero))
        check(f"DRIFT {field} improvement passes", not regress.drift_failures("K", zero, dict(zero, **{field: 1.0})))
    check("DRIFT fails a metric that is not a number", regress.drift_failures("K", dict.fromkeys(drift, nan), zero))
    a = compare.audit(stl("cube", cube()))
    check("an unchanged shape passes", not regress.lock_failures("n", a, dict(a)))
    check("a changed vertex digest fails", regress.lock_failures("n", a, dict(a, digest="0")))
    check("a volume change at the tolerance passes",
          not regress.lock_failures("n", a, dict(a, volume=a["volume"] + policy.SOUND_VOL)))
    check("a volume change just over the tolerance fails",
          regress.lock_failures("n", a, dict(a, volume=a["volume"] + policy.SOUND_VOL + 1e-6)))
    check("a volume change of exactly the tolerance passes",
          not regress.lock_failures("n", dict(a, volume=policy.SOUND_VOL), dict(a, volume=0.0)))
    far = a["volume"] + 1.0
    for label, was, named in (("vertices alone", dict(a, digest="0"), "(vertices;"),
                              ("volume alone", dict(a, volume=far), "(volume;"),
                              ("vertices and volume together", dict(a, digest="0", volume=far), "(vertices and volume;")):
        found = regress.lock_failures("n", a, was)
        check(f"a change of {label} fails and is named", len(found) == 1 and named in found[0])
    check("a render absent from the baseline fails", regress.lock_failures("n", a, "absent"))
    check("an empty baseline entry fails", regress.lock_failures("n", a, {}))
    # coverage: a reference is reported once, as a missing file or as absent from the baseline
    held = {k: {} for k in REFERENCES}
    lacking = {k: {} for k in REFERENCES[1:]}
    for label, missing, models, want in (
            ("its file missing and the baseline holding it", [REF], held, [f"{REF}: reference file missing"]),
            ("its file missing and the baseline lacking it", [REF], lacking, [f"{REF}: reference file missing"]),
            ("its file present and the baseline lacking it", [], lacking, [f"{REF}: absent from baseline"]),
            ("its file present and the baseline holding it", [], held, [])):
        found = regress.coverage_failures(missing, dict(models=models, soundness={}), False, True)
        check(f"a reference with {label} gives exactly the line for that case",
              len(found) == len(want) and all(w in f for w, f in zip(want, found)))
    # a size the sliders cannot produce: the file and the error, each alone and together
    for path, stopped, lines in ((None, True, 0), ("f.stl", True, 1), (None, False, 1), ("f.stl", False, 2)):
        found = regress.rejection_failures("w", path, stopped, "E")
        check(f"a rejected size with {'a' if path else 'no'} file and {'its' if stopped else 'no'} error gives "
              f"{lines} failure(s)", len(found) == lines)
    check("a rejected size's two failures say which",
          regress.rejection_failures("w", "f.stl", False, "E")
          == ["rejected/w: expected the render to stop, and it wrote a file",
              "rejected/w: expected the render to stop with: E"])
    check("a baseline entry with no shape locked fails", regress.lock_failures("n", a, dict(volume=a["volume"])))
    check("relocking ignores the baseline", not regress.lock_failures("n", a, None))
    check("a crossing at the limit is sound", compare.clean(dict(a, crossing_depth=policy.CROSSING_LIMIT)))
    check("a crossing just over the limit is not", not compare.clean(dict(a, crossing_depth=policy.CROSSING_LIMIT + 1e-9)))
    check("a crossing depth that is not a number is not sound", not compare.clean(dict(a, crossing_depth=nan)))
    check("a crossing at the limit gives no failure reason",
          compare.unsound_reasons(dict(a, crossing_depth=policy.CROSSING_LIMIT)) == [])
    check("a mesh of zero volume is not sound",
          not compare.clean(dict(a, volume=0.0)) and compare.unsound_reasons(dict(a, volume=0.0)) == ["volume 0.0 not positive"])
    none = dict.fromkeys(policy.MERGE_TOLS, 0)
    check("a 3MF export with no fault passes", not regress.threemf_failures("n", 0, none))
    check("one group of coincident 3MF vertices fails", len(regress.threemf_failures("n", 1, none)) == 1)
    for tol in policy.MERGE_TOLS:
        check(f"one edge left by a merge within {tol:g} mm fails",
              len(regress.threemf_failures("n", 0, {**none, tol: 1})) == 1)
    same = dict(policy.CUSTOMIZER)
    check("the policy's own sliders and dropdowns pass", not regress.customizer_failures(same))
    check("a slider with another range fails", regress.customizer_failures(dict(same, depth_lu=(0.25, 0.25, 20.0))))
    check("a dropdown with another value fails", regress.customizer_failures(dict(same, left_wall=("topped", "open"))))
    check("a missing parameter fails", regress.customizer_failures({k: v for k, v in same.items() if k != "width_lu"}))
    check("an extra parameter fails", regress.customizer_failures(dict(same, lid=(0.0, 1.0, 2.0))))


def test_messages():
    normal = "\n".join(["Geometries in cache: 315", "Geometry cache size in bytes: 511888",
                        "CGAL Polyhedrons in cache: 152", "CGAL cache size in bytes: 73485696",
                        "Total rendering time: 0:00:22.030", "   Top level object is a 3D object:",
                        "   Simple:        yes", "   Vertices:     6372", "   Halfedges:   20758",
                        "   Edges:       10379", "   Halffacets:   8156", "   Facets:       4078",
                        "   Volumes:         2", ""])
    check("normal OpenSCAD output is no message", compare.render_problems(normal) == [])
    for line in ["WARNING: x", "ERROR: x", "DEPRECATED: x", 'ECHO: "x"', "TRACE: x",
                 "PolySet has nonplanar faces. Attempting alternate construction", "anything else",
                 "WARNING: Vertices: 3", "Simple: no", "Volumes: 3",
                 "WARNING: Object may not be a valid 2-manifold and may need repair!"]:
        check(f"'{line[:24]}' is a message", compare.render_problems(normal + line) == [line])
    check("the echo of an expected text is not a message", compare.render_problems('ECHO: "NOTE: a"', ["NOTE: a"]) == [])
    check("a message beside an expected text is still a message",
          compare.render_problems('WARNING: x\nECHO: "NOTE: a"', ["NOTE: a"]) == ["WARNING: x"])
    for line in ('ECHO: "NOTE: a and more"', 'ECHO: "NOTE: a", "more"', 'WARNING: NOTE: a', "NOTE: a"):
        check(f"an expected text inside a longer line is a message ({line})",
              compare.render_problems(line, ["NOTE: a"]) == [line])
    for texts in policy.EXPECTED_MESSAGES.values():
        for text in texts:
            line = f'ECHO: "{text}"'
            check(f"a note the policy expects elsewhere is a message in a render that expects none ({text[:24]})",
                  compare.render_problems(line, ()) == [line])
    check("an unexpected message fails", regress.message_failures("K", ["WARNING: x"], [], []))
    check("a missing expected message fails", regress.message_failures("K", [], ["NOTE: a"], []))
    check("an expected message seen passes", not regress.message_failures("K", [], ["NOTE: a"], ["NOTE: a"]))


# ------------------------------------------------------------------ mesh tools

def test_measure():
    m = cube()
    r, _ = compare.measure(m, m.copy(), n_samples=2000)
    check("identical meshes measure zero", max(compare.summary(r).values()) < 1e-9)
    check("measure reports the number of samples it drew", r["samples"] == 2000)
    moved = m.vertices.copy()
    moved[np.argmax(moved.sum(axis=1)), 0] += 0.3          # pull the +x+y+z corner out 0.3 in x
    r, _ = compare.measure(m, trimesh.Trimesh(moved, m.faces, process=False), n_samples=2000)
    check("the vertex sweep finds a corner moved 0.3 mm", abs(r["gen->ref"]["vmax"] - 0.3) < 1e-6)
    check("summary carries the vertex sweep into the maximum", compare.summary(r)["mx"] >= 0.3 - 1e-6)
    check("bounding box difference is measured", abs(r["bbox"] - 0.3) < 1e-6)
    r, _ = compare.measure(m, m.copy().apply_scale(1.01), n_samples=2000)
    check("volume difference is measured", abs(r["vol"] - (1.01 ** 3 - 1) * 100) < 1e-6)
    taller = trimesh.creation.box(extents=(10, 10, 10.1))
    r, _ = compare.measure(m, taller, n_samples=20000)
    check("p99 sees a face 0.1 mm off", abs(compare.summary(r)["p99"] - 0.1) < 1e-3)
    pts = np.array([[0.0, 0, 0], [1, 0, 0], [2, 0, 0], [10, 0, 0], [20, 0, 0]])
    worst = compare.clusters(pts, np.array([0.1, 0.3, 0.3, 0.2, 0.05]), 2)
    check("the worst-spot listing keeps the first worst point of each 3 mm cell, largest first, up to the number asked",
          [(list(p), d) for p, d in worst] == [([1.0, 0.0, 0.0], 0.3), ([10.0, 0.0, 0.0], 0.2)])


def test_audit():
    a = compare.audit(stl("cube", cube()))
    check("a cube is sound", compare.clean(a) and a["bodies"] == 1)
    for field, bad in (("watertight", False), ("winding", False), ("volume", -1.0), ("bodies", 2),
                       ("bad_edges", 1), ("dup_faces", 1), ("crossing_depth", policy.CROSSING_LIMIT + 1e-9)):
        check(f"clean rejects {field} = {bad}", not compare.clean(dict(a, **{field: bad})))
        check(f"the failure names {field} = {bad}", len(compare.unsound_reasons(dict(a, **{field: bad}))) == 1)
    check("a sound mesh has no failure reasons", compare.unsound_reasons(a) == [])
    pierce_v = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [2, 2, -1], [2, 2, 1], [3, 3, 1]], dtype=float)
    for label, faces in (("first", [[0, 1, 2], [3, 4, 5]]), ("second", [[3, 4, 5], [0, 1, 2]])):
        count, deep = export_check.crossings(pierce_v, np.array(faces))
        check(f"a triangle pierced by another's edge is a crossing when it comes {label}", count == 1 and deep > 0.5)
    for label, two in (("watertight and winding", dict(watertight=False, winding=False)),
                       ("bad_edges and dup_faces", dict(bad_edges=1, dup_faces=1)),
                       ("bodies and volume", dict(bodies=2, volume=-1.0)),
                       ("everything", dict(watertight=False, winding=False, bad_edges=1, dup_faces=1, bodies=2,
                                           volume=-1.0, crossing_depth=1.0))):
        check(f"a mesh failing on {label} together is not sound, with each fault named",
              not compare.clean(dict(a, **two)) and len(compare.unsound_reasons(dict(a, **two))) == len(two))
    check("a crossing is named with its depth",
          compare.unsound_reasons(dict(a, crossing_depth=0.0058)) == ["triangles crossing 0.0058 mm deep"])
    flipped = cube()
    faces = flipped.faces.copy()
    faces[0] = faces[0][::-1]
    check("a face wound the wrong way is caught",
          not compare.audit(stl("flipped", trimesh.Trimesh(flipped.vertices, faces, process=False)))["winding"])
    with np.errstate(divide="ignore", invalid="ignore"):       # the bow-tie encloses no volume
        bow_audit = compare.audit(bowtie())
    check("faces crossing while sharing a vertex are caught", bow_audit["crossing_depth"] > policy.CROSSING_LIMIT)
    face = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0]], dtype=float)
    needle = np.array([[2, 2, -1], [2, 2, 1], [2, 2, 0.5]], dtype=float)   # a flat sliver through the face
    check("a zero-area triangle piercing a face is measured",
          export_check.pair_depth(face, needle) >= 1.0 - 1e-9 and export_check.pair_depth(needle, face) >= 1.0 - 1e-9)

    def through(x, y):
        """Whether a vertical edge through (x, y) crosses the face."""
        p0, p1 = np.array([[x, y, -1.0]]), np.array([[x, y, 1.0]])
        return bool(export_check.segment_crosses(p0, p1, face[None, 0], face[None, 1], face[None, 2])[0])
    check("an edge through the inside of a face is a crossing", through(0.5, 0.5))
    check("an edge through a face's corner is a shared point", not through(policy.CORNER_TOL / 10, policy.CORNER_TOL / 10))
    check("an edge through a face's edge is a crossing", through(0.0, 3.0))
    check("an edge passing 0.005 mm outside a face is not a crossing", not through(-0.005, 3.0))
    check("two cubes touching at one vertex are two bodies",
          compare.audit(stl("touch", joined(cube(), cube((10, 10, 10)))))["bodies"] == 2)
    check("two separate cubes are not sound", not compare.clean(compare.audit(stl("apart", joined(cube(), cube((20, 0, 0)))))))
    cross = compare.audit(stl("cross", joined(cube(), cube((3, 3, 3)))))
    check("crossing cubes exceed the crossing limit", cross["crossing_depth"] > policy.CROSSING_LIMIT
          and not compare.clean(cross))
    m = cube()
    opened = compare.audit(stl("open", trimesh.Trimesh(m.vertices, m.faces[1:], process=False)))
    check("a cube missing a face is not watertight", not opened["watertight"])
    check("a cube missing a face has edges not shared by two faces", opened["bad_edges"] == 3)
    check("a duplicated facet is counted",
          compare.audit(stl("dup", trimesh.Trimesh(m.vertices, np.vstack([m.faces, m.faces[:1]]), process=False)))
          ["dup_faces"] == 1)
    rng = np.random.default_rng(1)
    shuffled = m.faces[rng.permutation(len(m.faces))]
    shuffled = np.array([np.roll(f, k) for f, k in zip(shuffled, rng.integers(0, 3, len(shuffled)))])
    d0 = compare.audit(stl("cube", m))["digest"]
    check("digest ignores triangle order and starting corner",
          compare.audit(stl("shuffled", trimesh.Trimesh(m.vertices, shuffled, process=False)))["digest"] == d0)
    # split one square face along its other diagonal: same vertices, different triangles
    resplit = m.faces.copy()
    quad = [i for i in range(len(resplit)) if np.allclose(m.face_normals[i], [0, 0, 1])]
    a0, a1 = resplit[quad[0]], resplit[quad[1]]
    corners = list(dict.fromkeys(list(a0) + list(a1)))
    shared = [x for x in a0 if x in a1]
    other = [x for x in corners if x not in shared]
    resplit[quad[0]] = [other[0], shared[0], other[1]]
    resplit[quad[1]] = [other[1], shared[1], other[0]]
    resplit_mesh = trimesh.Trimesh(m.vertices, resplit, process=False)
    resplit_mesh.fix_normals()
    check("digest ignores how a face is split into triangles",
          compare.audit(stl("resplit", resplit_mesh))["digest"] == d0)
    unchanged = []
    for i in range(len(m.vertices)):
        moved = m.vertices.copy()
        moved[i, 0] += 1e-4
        if compare.audit(stl("moved", trimesh.Trimesh(moved, m.faces, process=False)))["digest"] == d0:
            unchanged.append(i)
    check("digest changes when any one vertex moves 0.0001 mm", not unchanged)


def test_3mf():
    for name, coords, groups in (("apart", [(0, 0, 0), (1, 0, 0)], 0),
                                 ("together", [(0, 0, 0), (1, 0, 0), (0, 0, 0)], 1),
                                 ("signed zero", [("0.000000", 0, 0), ("-0.000000", 0, 0)], 1)):
        check(f"3MF coincident vertices counted ({name})", export_check.coincident_3mf(threemf(name, model(coords))) == groups)
    single = threemf("single_quotes", "<model><mesh><vertices><vertex x='0' y='0' z='0'/><vertex x='1' y='0' z='0'/>"
                                      "<vertex x='0' y='0' z='0'/></vertices><triangles>"
                                      "<triangle v1='0' v2='1' v3='2'/></triangles></mesh></model>")
    check("a 3MF written with single quotes is read", export_check.coincident_3mf(single) == 1)
    try:
        export_check.coincident_3mf(threemf("empty", "<model><mesh><vertices/><triangles/></mesh></model>"))
        refused = False
    except ValueError:
        refused = True
    check("a 3MF with no mesh is an error, not a pass", refused)
    for name, text in (("no_triangles", model([(0, 0, 0), (1, 0, 0)], tris=())), ("no_vertices", model([]))):
        try:
            export_check.read_3mf(threemf(name, text))
            refused = False
        except ValueError:
            refused = True
        check(f"a 3MF with {name.replace('_', ' ')} is an error", refused)
    near = fin(0.000005)
    check("3MF merge folds a fin into an edge with four triangles", export_check.merge_faults(near, 1e-5) == 1)
    check("3MF merge leaves vertices farther apart than the distance", export_check.merge_faults(near, 1e-6) == 0)
    for tol in policy.MERGE_TOLS:
        check(f"3MF merge within {tol:g} mm folds vertices at 0.999 of the distance and leaves those at 1.001 of it",
              export_check.merge_faults(fin(0.999 * tol), tol) == 1 and export_check.merge_faults(fin(1.001 * tol), tol) == 0)


# ------------------------------------------------------------------ the render function and the real steps

STUB = [sys.executable, str(HERE / "fixtures" / "stub_openscad.py")]


@contextlib.contextmanager
def stand_in(write=True, console=""):
    """Point every render at the stand-in for OpenSCAD."""
    TMP.mkdir(parents=True, exist_ok=True)
    text = TMP / "stub_console.txt"
    text.write_text(console, encoding="utf-8")
    saved, compare.OPENSCAD_COMMAND = compare.OPENSCAD_COMMAND, STUB
    os.environ["STUB_WRITE"], os.environ["STUB_CONSOLE"] = ("1" if write else "0"), str(text)
    try:
        yield
    finally:
        compare.OPENSCAD_COMMAND = saved
        del os.environ["STUB_WRITE"], os.environ["STUB_CONSOLE"]


def stub_args(out):
    """The arguments the stand-in received for an output file."""
    return json.loads(Path(str(out) + ".args.json").read_text(encoding="utf-8"))


def test_render():
    folder = TMP / "render"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "a.stl"
    with stand_in():
        r = compare.render(STUB, "gen.scad", dict(width_lu=2, front_wall='"topped"'), out)
    check("a render that wrote its file returns the path", r["path"] == out and out.is_file())
    check("the render passes the output, the generator and every parameter",
          stub_args(out) == ["-o", str(out), "--export-format", "binstl", "gen.scad",
                             "-D", "width_lu=2", "-D", 'front_wall="topped"'])
    with stand_in():
        r = compare.render(STUB, "gen.scad", {}, folder / "a.3mf")
    check("a 3MF render does not ask for binary STL",
          "--export-format" not in stub_args(folder / "a.3mf") and r["path"] is not None)
    out.write_text("left by an earlier run", encoding="utf-8")
    with stand_in(write=False):
        r = compare.render(STUB, "gen.scad", {}, out)
    check("a render that wrote no file returns no path", r["path"] is None)
    check("a file left by an earlier run is deleted before the render", not out.exists())
    with stand_in(console='WARNING: x\nECHO: "NOTE: a"\nECHO: "NOTE: c and more"\n'):
        r = compare.render(STUB, "gen.scad", {}, out, ["NOTE: a", "NOTE: b", "NOTE: c"])
    check("a render's messages beside its expected texts are reported",
          r["problems"] == ["WARNING: x", 'ECHO: "NOTE: c and more"'])
    check("only the expected texts that appeared count as seen", r["seen"] == ["NOTE: a", "NOTE: c"])
    check("the console text is returned", "WARNING: x" in r["console"])
    with stand_in():
        r = compare.render(STUB, "gen.scad", {}, folder / "new" / "b.stl")
    check("a render makes its output folder", r["path"] == folder / "new" / "b.stl")


def test_real_steps():
    """The real run's own steps, on small inputs: the stand-ins in FakeSteps
    cannot show that the real ones do their work."""
    steps = regress.Steps()
    TMP.mkdir(parents=True, exist_ok=True)
    OTHER_SCAD.write_bytes(b"cube(1);\r\n")
    alt = compare.OUT / "alt" / OTHER_SCAD.stem
    shutil.rmtree(alt, ignore_errors=True)
    check("the generator's renders go to the output folder", compare.out_for() == compare.OUT
          and compare.out_for(compare.SCAD) == compare.OUT)
    check("another SCAD file's renders go to a folder of its own, made on demand",
          compare.out_for(OTHER_SCAD) == alt and alt.is_dir())
    target = alt / "soundness" / "a.stl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("left by an earlier run", encoding="utf-8")
    with stand_in(console='WARNING: y\nECHO: "NOTE: a"\n'):
        r = steps.render(OTHER_SCAD, "soundness/a.stl", dict(width_lu=3), ["NOTE: a"])
        version = steps.renderer()
    args = stub_args(target)
    check("the real render step writes under the generator's own output folder", r["path"] == target)
    check("the real render step passes the generator, the parameters and the binary STL format",
          str(OTHER_SCAD) in args and "width_lu=3" in args and "binstl" in args)
    check("the real render step reports messages and the expected texts seen",
          r["problems"] == ["WARNING: y"] and r["seen"] == ["NOTE: a"])
    check("the real renderer step asks the render command for its version", version == "OpenSCAD version 0.0 (stand-in)")
    check("the real clock step gives a date and time", bool(re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d", steps.now())))
    with np.errstate(divide="ignore", invalid="ignore"):
        check("the real audit measures crossings", steps.audit(bowtie())["crossing_depth"] > policy.CROSSING_LIMIT)
    check("the real audit passes a sound mesh", compare.clean(steps.audit(stl("cube", cube()))))
    check("the real 3MF step counts coincident vertices",
          steps.coincident_3mf(threemf("together", model([(0, 0, 0), (1, 0, 0), (0, 0, 0)]))) == 1)
    check("the real merge step applies both distances", steps.merge_faults(fin(0.00005)) == {1e-5: 0, 1e-4: 1})
    check("the real merge step finds a fin at either distance", steps.merge_faults(fin(0.000005)) == {1e-5: 1, 1e-4: 1})
    # the real measuring and coverage steps, with the reference folder pointed
    # at a synthetic reference for the first key
    folder = TMP / "refs"
    folder.mkdir(parents=True, exist_ok=True)
    cube().export(folder / refs.fname(REF))
    saved, refs.STL_DIR = refs.STL_DIR, folder
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            m = steps.measure(REF, stl("scaled", cube().apply_scale(1.01)))
        missing = steps.missing_refs()
    finally:
        refs.STL_DIR = saved
    check("the real measure step measures volume", abs(m["vol"] - (1.01 ** 3 - 1) * 100) < 1e-3)   # STL keeps 32-bit floats
    check("the real measure step measures the bounding box", abs(m["bbox"] - 0.1) < 1e-6)
    check("the real measure step measures both directions", m["ref->gen"]["vmax"] > 0.04 and m["gen->ref"]["vmax"] > 0.04)
    check("the real measure step draws the required number of samples", m["samples"] == policy.N_SAMPLES)
    check("the real coverage step finds missing references", missing == list(REFERENCES[1:]))
    check("the generator digest ignores line endings",
          steps.digest(OTHER_SCAD) == hashlib.sha256(b"cube(1);\n").hexdigest().upper())
    # the Customizer step, on a small generator text
    text = ('/* [Size] */\n// Width = how wide\nwidth_lu = 2; // [1:0.5:12]\nfront_wall = "topped"; // [topped, topless, simple]\n'
            'plain = 3;\n  indented = 1; // [0:1:2]\nsplit =\n  4; // [3:1:5]\n$fn = 32; // [8:1:64]\n'
            '// a brace { in a comment, and one in a string below\nlabel = "{"; // [a, b]\n'
            '/* and a brace { in a block comment */\nafterblock = 1; // [0:1:2]\n'
            'twosemi = 2;; // [1:1:3]\ncalled = round(2); // [1:1:3]\nwords = 1; // [0:1:2] and words\n'
            'nosemi = 1 // [0:1:2]\nnoted = 1; // LU ; // [0:1:2]\nneg = -1.5; // [-2:0.5:2]\n'
            '/* [Hidden] */\nhidden = 1; // [0:1:5]\n/* [Later] */\nlater = 2; // [0:1:9]\n'
            '/* [ Hidden ] */\nspaced = 1;\n/* [Hidden] */\nagain = 1;\n/* a note */\nplainc = 1;\n'
            '/* [Hidden] [B] */\ntwonames = 1;\n/* [Hidden] */\nagain2 = 1;\n/* [A] [Hidden] */\nsecond = 1;\n'
            '/* [Hidden] */\nagain3 = 1;\n/* [Hidden] and words */\nworded = 1;\n'
            'module m() { inside = 1; // [0:1:2]\n}\n/* [After] */\nafter = 1; // [0:1:2]\n')
    cut = compare.before_first_block
    for label, source, kept in (
            ("in code", 'a = 1;\nmodule m() { b }', 'a = 1;\nmodule m() '),
            ("after a brace in a line comment", '// {\na { b', '// {\na '),
            ("after a brace in a block comment", '/* { */ a { b', '/* { */ a '),
            ("after a brace in a string that also holds an escaped quote", 'a = "\\"{"; b { c', 'a = "\\"{"; b '),
            ("after a brace in the middle of a string", 'a = "xy{z"; b { c', 'a = "xy{z"; b '),
            ("nowhere, when the text has none", 'a = 1;\nb = 2;', 'a = 1;\nb = 2;'),
            ("nowhere, when the only brace is in a line comment that ends the text", 'a = 1; // {', 'a = 1; // {'),
            ("nowhere, when the only brace is in a block comment that never closes", 'a /* {', 'a /* {'),
            ("nowhere, when the only brace is in a string that never closes", 'a = "{', 'a = "{'),
            ("nowhere, when a string ends the text", 'a = "b"', 'a = "b"')):
        check(f"the scan for the first block stops at a brace {label}", cut(source) == kept)
    scad = TMP / "customizer.scad"
    scad.write_text(text, encoding="utf-8")
    want = dict(width_lu=(1.0, 0.5, 12.0), front_wall=("topped", "topless", "simple"), plain=(), indented=(0.0, 1.0, 2.0),
                split=(), label=("a", "b"), later=(0.0, 1.0, 9.0), spaced=(), noted=(), plainc=(),
                afterblock=(0.0, 1.0, 2.0), twosemi=(), called=(), words=(), nosemi=(), neg=(-2.0, 0.5, 2.0),
                twonames=(), second=(), worded=())
    want["$fn"] = (8.0, 1.0, 64.0)
    check("the real Customizer step reads every parameter before the first block that no Hidden marker hides: with a "
          "note or none, indented, named with $, after a brace in a comment or a string, in a section opened after the "
          "Hidden one, and after any one-line block comment that is not the Hidden marker alone; a parameter gets its "
          "slider or dropdown only when written as a number or quoted string, one semicolon and the note, and nothing "
          "more", steps.customizer(scad) == want)
    # the real file steps, pointed at scratch files
    saved = regress.BASELINE, regress.REPORT, regress.UNIT_TESTS
    regress.BASELINE, regress.REPORT = TMP / "baseline.json", TMP / "REPORT.md"
    try:
        check("no baseline file loads as none", steps.load_baseline() is None)
        steps.write_baseline(dict(models={}, soundness={}, scad_digest="X"))
        check("the real baseline steps read back what they wrote",
              steps.load_baseline() == dict(models={}, soundness={}, scad_digest="X"))
        check("no report has no digest", steps.report_digest() is None)
        steps.write_report(regress.report_text([dict(row(key=k), seconds=12.0) for k in REFERENCES],
                                               "2026-01-01 00:00", "2026-01-01 00:30", "A" * 64, "OpenSCAD test"))
        report = regress.REPORT.read_text(encoding="utf-8")
        check("the real report steps read back the digest the report names", steps.report_digest() == "A" * 64)
        # the gate marks the environment of the unit tests it runs; this file may be one of them
        marked = os.environ.pop(regress.NESTED, None)
        try:
            for code, passes in ((0, True), (1, False)):
                regress.UNIT_TESTS = TMP / f"unit_tests_{code}.py"
                regress.UNIT_TESTS.write_text(f"import sys\nsys.exit({code})\n", encoding="utf-8")
                check(f"the real unit test step reports exit status {code}", steps.unit_tests() is passes)
            regress.UNIT_TESTS = TMP / "unit_tests_marked.py"
            regress.UNIT_TESTS.write_text(f"import os, sys\nsys.exit(0 if os.environ.get({regress.NESTED!r}) else 1)\n",
                                          encoding="utf-8")
            check("the real unit test step marks the environment of the tests it runs", steps.unit_tests() is True)
            os.environ[regress.NESTED] = "1"
            regress.UNIT_TESTS = TMP / "unit_tests_0.py"
            check("the real unit test step refuses to run from inside the unit tests, so they cannot start themselves",
                  steps.unit_tests() is False)
        finally:
            os.environ.pop(regress.NESTED, None)
            if marked is not None:
                os.environ[regress.NESTED] = marked
    finally:
        regress.BASELINE, regress.REPORT, regress.UNIT_TESTS = saved
    check("the report has a row for every reference", all(f"| {k} |" in report for k in REFERENCES))
    check("the report states the sample count and the limits",
          f"{policy.N_SAMPLES} points" in report and f"maxima <= {policy.LIMITS['mx']} mm" in report)
    check("the report names the renderer", "Renderer: OpenSCAD test." in report)


# ------------------------------------------------------------------ the gate's run

class FakeSteps:
    """Stands in for OpenSCAD, the mesh tools and the files, so run() can be
    driven through each check in a fraction of a second. It records every call
    with its arguments, so a test can see what a run rendered and examined."""

    def __init__(self, baseline=None, **faults):
        self.baseline, self.written, self.report, self.calls = baseline, None, None, []
        self.scads = set()          # (step, SCAD file) for every step that is handed the file
        self.faults = faults
        self.digests = iter(faults.get("digests", []))

    def fault(self, kind, key, default):
        return self.faults.get(kind, {}).get(key, default)

    def unit_tests(self):
        return self.faults.get("unit_tests", True)

    def now(self):
        return "2026-01-01 00:00"

    def digest(self, scad):
        self.scads.add(("digest", scad))
        return next(self.digests, "D")

    def report_digest(self):
        return self.faults.get("report_digest", "D")

    def customizer(self, scad):
        self.scads.add(("customizer", scad))
        return self.faults.get("customizer", dict(policy.CUSTOMIZER))

    def missing_refs(self):
        return list(self.faults.get("missing", []))

    def render(self, scad, name, params, expected):
        self.calls.append(("render", name, dict(params), tuple(expected)))
        self.scads.add((f"render {name}", scad))
        if name in self.faults.get("no_file", []):
            return dict(path=None, seconds=1.0, console="render failed", problems=[], seen=[])
        if any(name == f"soundness/{r[0]}.stl" for r in policy.REJECTED):
            return dict(path=name if self.faults.get("reject_writes") else None, seconds=0.1, console="",
                        problems=[], seen=list(expected) if self.faults.get("rejects", True) else [])
        return dict(path=name, seconds=1.0, console="", problems=list(self.fault("messages", name, [])),
                    seen=[e for e in expected if e not in self.fault("unseen", name, [])])

    def measure(self, key, path):
        self.calls.append(("measure", key, path))
        return row(key=key, **self.fault("measure", key, {}))

    def audit(self, path):
        self.calls.append(("audit", path))
        a = dict(watertight=True, winding=True, bodies=1, bad_edges=0, dup_faces=0, crossing_depth=0.0,
                 extents=[1.0, 1.0, 1.0], volume=1.0, digest=path)
        return dict(a, **self.fault("audit", path, {}))

    def coincident_3mf(self, path):
        self.calls.append(("coincident_3mf", path))
        return self.faults.get("coincident", 0)

    def merge_faults(self, path):
        self.calls.append(("merge_faults", path))
        return {tol: self.faults.get("merged", {}).get(tol, 0) for tol in policy.MERGE_TOLS}

    def renderer(self):
        return "OpenSCAD test"

    def load_baseline(self):
        return self.baseline

    def write_baseline(self, data):
        self.written = data

    def write_report(self, text):
        self.report = text


def gate_run(baseline, log=None, **kw):
    faults = {k: kw.pop(k) for k in list(kw) if k not in ("update", "accept", "quick", "alternate")}
    steps = FakeSteps(baseline, **faults)
    code, failures = regress.run(steps, "fake.scad", log=(lambda *a: None) if log is None else log.append, **kw)
    return code, failures, steps


def has(failures, text):
    return any(text in f for f in failures)


def test_checks():
    """Every check in regress.CHECKS, through run()."""
    code, failures, first = gate_run(None, update=True)
    locked = first.written
    check("a clean relock writes the baseline", code == 0 and locked is not None
          and list(locked["models"]) == list(REFERENCES)
          and list(locked["soundness"]) == [n for n, _ in policy.SOUNDNESS])
    code, failures, clean_run = gate_run(locked)
    check("a clean run passes", code == 0 and not failures)

    def fails(name, label, text, baseline=None, **faults):
        code, failures, _ = gate_run(locked if baseline is None else baseline, **faults)
        check(f"[{name}] a run fails on {label}", code == 1 and has(failures, text))
        covered.add(name)

    code, failures, steps = gate_run(locked, unit_tests=False)
    check("[unit tests] a run stops before rendering when gate_test.py fails", code == 2 and not steps.calls)
    covered.add("unit tests")

    fails("locked generator", "a baseline locked on another generator", "the baseline was locked on another version",
          baseline=dict(locked, scad_digest="OTHER"))
    fails("locked generator", "a VERIFICATION.md for another generator", "VERIFICATION.md is for another version",
          report_digest="OTHER")
    fails("locked generator", "a missing VERIFICATION.md", "VERIFICATION.md is for another version", report_digest=None)
    fails("generator unchanged", "a generator edited during the run", "the file changed during the run",
          digests=["D", "E"])
    fails("customizer", "a slider with another range", "customizer: depth_lu is annotated (0.25, 0.25, 20.0)",
          customizer=dict(policy.CUSTOMIZER, depth_lu=(0.25, 0.25, 20.0)))

    fails("reference coverage", "a missing reference file", f"{REF}: reference file missing", missing=[REF])
    fails("reference coverage", "a baseline reference the policy does not list", "X999: in the baseline but not in",
          baseline=dict(locked, models=dict(locked["models"], X999=locked["models"][REF])))
    fails("reference coverage", "a listed reference the baseline lacks", f"{REF}: absent from baseline",
          baseline=dict(locked, models={k: v for k, v in locked["models"].items() if k != REF}))
    fails("configuration coverage", "a listed configuration the baseline lacks", f"soundness/{CONF}: absent from baseline",
          baseline=dict(locked, soundness={k: v for k, v in locked["soundness"].items() if k != CONF}))
    fails("configuration coverage", "a baseline configuration the policy does not list",
          "soundness/extra: in the baseline but no longer checked",
          baseline=dict(locked, soundness=dict(locked["soundness"], extra={})))

    check("--quick leaves the configurations' coverage to the full run",
          gate_run(dict(locked, soundness=dict(locked["soundness"], extra={})), quick=True)[0] == 0)

    fails("render success", "a failed reference render", f"{REF}: render failed", no_file=[REF_STL])
    fails("render success", "a failed configuration render", f"soundness/{CONF}: render failed", no_file=[CONF_STL])
    fails("render success", "a failed 3MF render", f"soundness/{THREEMF_CHECK[0]}: 3MF render failed", no_file=[TMF_3MF])

    fails("render messages", "a reference render message", f"{REF}: render message: WARNING: x",
          messages={REF_STL: ["WARNING: x"]})
    fails("render messages", "a configuration render message", f"soundness/{CONF}: render message: ECHO: x",
          messages={CONF_STL: ["ECHO: x"]})
    fails("render messages", "a message in a 3MF export only",
          f"soundness/{THREEMF_CHECK[0]} 3MF: render message: WARNING: x", messages={TMF_3MF: ["WARNING: x"]})
    fails("expected messages", "a missing expected note", "soundness/thin_1.5x0.5x1: expected render message missing",
          unseen={NOTE_STL: [NOTE]})
    fails("expected messages", "a missing expected note in the 3MF export",
          "soundness/thin_1.5x0.5x1 3MF: expected render message missing", unseen={NOTE_3MF: [NOTE]})

    fails("hard limits", "a reference over a limit", f"{REF}: HARD mx=0.3000", measure={REF: dict(mx=(0.3, 0.0))})
    fails("hard limits", "a reference metric that is not a number", f"{REF}: HARD p99",
          measure={REF: dict(p99=(float("nan"), 0.0))})
    fails("hard limits", "a reference measured from too few samples", f"{REF}: HARD measured from 500 samples",
          measure={REF: dict(samples=500)})
    fails("drift", "a reference worse than its locked value", f"{REF}: DRIFT mx", measure={REF: dict(mx=(0.003, 0.0))})

    fails("mesh soundness", "an unsound reference", f"{REF}: mesh not a clean single shell: not watertight",
          audit={REF_STL: dict(watertight=False)})
    fails("mesh soundness", "an unsound configuration", f"soundness/{CONF}: mesh not a clean single shell: 2 bodies",
          audit={CONF_STL: dict(bodies=2)})
    fails("crossings", "crossing triangles in a reference",
          f"{REF}: mesh not a clean single shell: triangles crossing 0.01 mm deep",
          audit={REF_STL: dict(crossing_depth=0.01)})
    fails("shape lock", "a configuration's changed vertex digest", f"soundness/{CONF}: geometry changed vs baseline",
          audit={CONF_STL: dict(digest="x")})
    fails("shape lock", "a configuration's changed volume with the same vertices",
          f"soundness/{CONF}: geometry changed vs baseline", audit={CONF_STL: dict(volume=1.0 + policy.SOUND_VOL + 1e-6)})
    fails("shape lock", "a reference's changed vertex digest", f"{REF}: geometry changed vs baseline",
          audit={REF_STL: dict(digest="x")})
    fails("shape lock", "a reference whose shape the baseline does not lock", f"{REF}: absent from baseline",
          baseline=dict(locked, models=dict(locked["models"],
                                            **{REF: {k: v for k, v in locked["models"][REF].items() if k != "digest"}})))
    code, failures, _ = gate_run(locked, quick=True, audit={REF_STL: dict(digest="x")})
    check("[shape lock] --quick still locks the references' shapes", code == 1 and has(failures, f"{REF}: geometry changed"))

    fails("3MF coincident vertices", "coincident 3MF vertices", "3MF has 2 group(s)", coincident=2)
    for tol, text in ((1e-5, "3MF merged within 1e-05 mm leaves 2 edge(s)"),
                      (1e-4, "3MF merged within 0.0001 mm leaves 2 edge(s)")):
        fails("3MF merges", f"a 3MF that a merge within {tol:g} mm folds", text, merged={tol: 2})
    fails("rejected sizes", "a size that stops without its error", "rejected/height_below: expected the render to stop with",
          rejects=False)
    fails("rejected sizes", "a rejected size that still writes a file",
          "rejected/depth_above: expected the render to stop, and it wrote a file", reject_writes=True)
    code, failures, _ = gate_run(locked, rejects=False, reject_writes=True)
    check("[rejected sizes] a run fails on a size the generator builds instead of refusing, on both counts",
          code == 1 and has(failures, "rejected/width_between_steps: expected the render to stop, and it wrote a file")
          and has(failures, "rejected/width_between_steps: expected the render to stop with"))
    for label, path in (("configuration", CONF_STL), ("reference", REF_STL)):
        code, failures, _ = gate_run(locked, audit={path: dict(digest="x", volume=3.0)})
        check(f"[shape lock] a run fails on a {label} whose vertices and volume both changed",
              code == 1 and has(failures, "geometry changed vs baseline (vertices and volume;"))
    fails("shape lock", "a reference whose baseline entry is empty", f"{REF}: absent from baseline",
          baseline=dict(locked, models=dict(locked["models"], **{REF: {}})))

    # a clean run renders, measures and examines exactly what the policy lists
    def renders(names_params_expected):
        return sorted((n, sorted(p.items()), tuple(e)) for n, p, e in names_params_expected)
    want = [(f"{k}.stl", compare.params(k), ()) for k in REFERENCES]
    for n, p in policy.SOUNDNESS:
        notes = policy.EXPECTED_MESSAGES.get(n, ())
        want.append((f"soundness/{n}.stl", p, notes))
        if n in THREEMF_CHECK:
            want.append((f"soundness/{n}.3mf", p, notes))
    want += [(f"soundness/{n}.stl", p, (error,)) for n, p, error in policy.REJECTED]
    done = lambda kind, steps=clean_run: [c[1:] for c in steps.calls if c[0] == kind]     # noqa: E731
    stls = [f"{k}.stl" for k in REFERENCES] + [f"soundness/{n}.stl" for n, _ in policy.SOUNDNESS]
    tmfs = [f"soundness/{n}.3mf" for n in THREEMF_CHECK]
    check("a clean run renders every reference, configuration, 3MF export and rejected size, each with "
          "its own parameters and expected texts", renders(done("render")) == renders(want))
    check("a clean run renders, digests and reads the Customizer of the SCAD file it was given, and no other",
          clean_run.scads == {(f"render {n}", "fake.scad") for n, _, _ in want}
          | {("digest", "fake.scad"), ("customizer", "fake.scad")})
    check("a clean run measures every reference's own render", done("measure") == [(k, f"{k}.stl") for k in REFERENCES])
    check("a clean run audits every STL it rendered", sorted(c[0] for c in done("audit")) == sorted(stls))
    check("a clean run checks every 3MF export both ways",
          sorted(c[0] for c in done("coincident_3mf")) == sorted(tmfs)
          and sorted(c[0] for c in done("merge_faults")) == sorted(tmfs))
    code, _, quick_run = gate_run(locked, quick=True)
    check("--quick renders only the references",
          code == 0 and sorted(c[0] for c in done("render", quick_run)) == sorted(f"{k}.stl" for k in REFERENCES))

    # the run's log, which is what a person reads
    lines = []
    gate_run(locked, log=lines, audit={CONF_STL: dict(digest="x"), NOTE_STL: dict(bodies=2)})
    state = {n: next(ln.split()[1] for ln in lines if ln.split()[:1] == [n]) for n, _ in policy.SOUNDNESS}
    check("the log marks a changed configuration, a broken one and the rest",
          state[CONF] == "CHANGED" and state["thin_1.5x0.5x1"] == "BROKEN"
          and all(s == "ok" for n, s in state.items() if n not in (CONF, "thin_1.5x0.5x1")))

    # relock rules
    check("[relock rules] a relock records the generator's digest and writes the report naming it",
          locked.get("scad_digest") == "D" and first.report and "SHA-256 D," in first.report)
    check("[relock rules] the report a relock writes has a row for every reference, with its measurements",
          all(f"| {k} | 0.0000 | 0.000 |" in first.report for k in REFERENCES))
    check("[relock rules] a relock locks every render's shape",
          all("digest" in m and "volume" in m for m in locked["models"].values())
          and all("digest" in a for a in locked["soundness"].values()))
    check("[relock rules] a plain run writes neither the baseline nor the report",
          clean_run.written is None and clean_run.report is None)
    check("[relock rules] a relock without the configurations is refused", gate_run(locked, update=True, quick=True)[0] == 2)
    check("[relock rules] a relock from another SCAD is refused", gate_run(locked, update=True, alternate=True)[0] == 2)
    check("[relock rules] a run without a baseline stops", gate_run(None)[0] == 2)
    drift = dict(measure={REF: dict(mx=(0.003, 0.0))})
    code, failures, steps = gate_run(locked, update=True, **drift)
    check("[relock rules] a relock refuses drift without --accept-drift",
          code == 1 and steps.written is None and steps.report is None and has(failures, "--accept-drift"))
    lines = []
    code, failures, steps = gate_run(locked, log=lines, update=True, accept=True, **drift)
    check("[relock rules] a relock with --accept-drift writes the baseline", code == 0 and steps.written is not None)
    check("[relock rules] a relock logs each change it accepts",
          any(ln.startswith("accepting 1 change(s)") for ln in lines) and any(f"- {REF}: DRIFT mx" in ln for ln in lines))
    lines = []
    gate_run(locked, log=lines, update=True)
    check("[relock rules] a relock that changes nothing logs no accepted change",
          not any(ln.startswith("accepting") for ln in lines))
    code, failures, steps = gate_run(locked, update=True, accept=True, missing=[REF])
    check("[relock rules] a relock never skips a missing reference file, even with --accept-drift",
          code == 1 and steps.written is None and has(failures, f"{REF}: reference file missing"))
    for label, path in (("configuration", CONF_STL), ("reference", REF_STL)):
        code, failures, steps = gate_run(locked, update=True, audit={path: dict(digest="x")})
        check(f"[relock rules] a relock refuses a {label}'s changed shape without --accept-drift",
              code == 1 and steps.written is None and has(failures, "geometry changed vs baseline"))
    code, failures, steps = gate_run(locked, update=True, accept=True, audit={REF_STL: dict(watertight=False)})
    check("[relock rules] a relock never writes over a failure", code == 1 and steps.written is None and steps.report is None)
    code, failures, steps = gate_run(dict(locked, soundness=dict(locked["soundness"], extra={})), update=True)
    check("[relock rules] a relock refuses to drop a locked configuration without --accept-drift",
          code == 1 and steps.written is None and has(failures, "soundness/extra: locked configuration no longer checked"))
    code, failures, steps = gate_run(dict(locked, models=dict(locked["models"], X999=locked["models"][REF])), update=True)
    check("[relock rules] a relock refuses to drop a locked reference without --accept-drift",
          code == 1 and steps.written is None and has(failures, "X999: locked reference no longer measured"))
    covered.add("relock rules")

    check("every check in regress.CHECKS has a test through run()", covered == set(regress.CHECKS))
    return locked


def test_command_line(locked):
    """What each flag asks of the run, and that main() passes it on."""
    plain = dict(scad=compare.SCAD, update=False, accept=False, quick=False, alternate=False)
    check("no flag asks for a plain full run of the generator", regress.options([]) == plain)
    check("--quick asks for the quick run only", regress.options(["--quick"]) == dict(plain, quick=True))
    check("--update-baseline asks for a relock only", regress.options(["--update-baseline"]) == dict(plain, update=True))
    check("--accept-drift alone accepts drift only", regress.options(["--accept-drift"]) == dict(plain, accept=True))
    check("--scad names another file and marks the run as alternate",
          regress.options(["--scad", str(OTHER_SCAD)]) == dict(plain, scad=OTHER_SCAD.resolve(), alternate=True))

    def main(*argv):
        steps = FakeSteps(locked)
        with contextlib.redirect_stdout(io.StringIO()):
            code = regress.main(list(argv), steps=steps)
        return code, [c[1] for c in steps.calls if c[0] == "render"], steps
    def printed(*argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            regress.main(list(argv), steps=FakeSteps(locked))
        return out.getvalue()
    check("main announces a run on another SCAD file, and only then",
          f"ALTERNATE SCAD: {OTHER_SCAD.name}" in printed("--scad", str(OTHER_SCAD)) and "ALTERNATE" not in printed())
    code, rendered, steps = main()
    check("main with no flag runs the full gate and writes nothing",
          code == 0 and len(rendered) > len(REFERENCES) and steps.written is None)
    code, rendered, _ = main("--quick")
    check("main --quick renders only the references", code == 0 and len(rendered) == len(REFERENCES))
    code, _, steps = main("--update-baseline")
    check("main --update-baseline relocks", code == 0 and steps.written is not None)
    code, _, steps = main("--update-baseline", "--quick")
    check("main refuses a quick relock", code == 2 and steps.written is None)
    code, _, steps = main("--scad", str(OTHER_SCAD), "--update-baseline")
    check("main refuses a relock from another SCAD", code == 2 and steps.written is None)
    steps = FakeSteps(locked, measure={REF: dict(mx=(0.003, 0.0))})
    with contextlib.redirect_stdout(io.StringIO()):
        refused = regress.main(["--update-baseline"], steps=steps)
    check("main without --accept-drift refuses a relock over drift", refused == 1 and steps.written is None)
    steps = FakeSteps(locked, measure={REF: dict(mx=(0.003, 0.0))})
    with contextlib.redirect_stdout(io.StringIO()):
        accepted = regress.main(["--update-baseline", "--accept-drift"], steps=steps)
    check("main --accept-drift relocks over drift", accepted == 0 and steps.written is not None)


def main():
    try:
        for test in (test_policy, test_decisions, test_messages, test_measure, test_audit, test_3mf, test_render,
                     test_real_steps):
            test()
        test_command_line(test_checks())
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
        shutil.rmtree(compare.OUT / "alt" / OTHER_SCAD.stem, ignore_errors=True)
    bad = [name for name, ok in results if not ok]
    for name, ok in results:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print(f"{len(results) - len(bad)} of {len(results)} gate tests passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
