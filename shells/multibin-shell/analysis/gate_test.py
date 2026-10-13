"""Unit tests for the shell's regression gate. They run in seconds and never
start OpenSCAD, though the tools they import need OpenSCAD's path and the
reference folder configured.

What is here:
- the policy against a literal copy, so no value changes without this file changing;
- each decision function of regress.py on small inputs;
- the measuring and mesh tools on small synthetic meshes, with whole results
  compared with literal values;
- the render function against a stand-in for OpenSCAD, and the real steps of
  the gate on small inputs;
- every check in regress.CHECKS driven through regress.run() with stand-in
  steps, from one table of faults.

Each run works in its own folders, .local-build/out/shell/gate_test/run_<pid>
and .local-build/out/shell/alt/other_<pid>, and removes them at the end, so two
runs at once do not share files.

Usage: python gate_test.py     (exits 1 if any test fails)
"""

import contextlib
import hashlib
import io
import itertools
import json
import os
import re
import shutil
import subprocess
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
NOTES = policy.EXPECTED_MESSAGES["thin_1.5x0.5x1"]
# what OpenSCAD 2021.01 wrote for the 1.5 x 0.5 x 1 shell after its two notes
STATISTICS = ("Geometries in cache: 297\nGeometry cache size in bytes: 476248\nCGAL Polyhedrons in cache: 148\n"
              "CGAL cache size in bytes: 45063448\nTotal rendering time: 0:00:16.417\n"
              "   Top level object is a 3D object:\n   Simple:        yes\n   Vertices:     3648\n"
              "   Halfedges:   11896\n   Edges:        5948\n   Halffacets:   4724\n   Facets:       2362\n"
              "   Volumes:         2\n")
# and for a rejected width of 1.25
REJECTION = ("ERROR: Assertion 'on_slider(v[1], v[2])' failed: \"width_lu must be a multiple of 0.5 from 1 to 12, "
             "not 1.25\" in file MultiBin Shell - Parametric.scad, line 58\n"
             "TRACE: called by 'assert' in file MultiBin Shell - Parametric.scad, line 58\n"
             "TRACE: called by 'for' in file MultiBin Shell - Parametric.scad, line 57\n"
             "Geometries in cache: 1\nGeometry cache size in bytes: 0\nCGAL Polyhedrons in cache: 0\n"
             "CGAL cache size in bytes: 0\nTotal rendering time: 0:00:00.000\nCurrent top level object is empty.\n")

results = []
covered = set()         # the checks of regress.CHECKS that a test has driven through run()


def check(name, condition):
    results.append((name, bool(condition)))


def console(notes=()):
    """A clean render's console text after these notes."""
    return "".join(f'ECHO: "{note}"\n' for note in notes) + STATISTICS


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


def row(bbox=0.0, vol=0.0, p99=(0.0, 0.0), mx=(0.0, 0.0), vmax=(0.0, 0.0), samples=None, key="K"):
    """A compare.measure row with chosen values."""
    return dict(key=key, bbox=bbox, vol=vol, samples=samples or [policy.N_SAMPLES, policy.N_SAMPLES],
                **{tag: dict(mean=0.0, p95=0.0, p99=p99[i], mx=mx[i], vmax=vmax[i])
                   for i, tag in enumerate(("ref->gen", "gen->ref"))})


def close(a, b, tol=1e-8):
    """Whether two nested results of numbers, strings and containers agree."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return abs(a - b) <= tol
    return a == b


# ------------------------------------------------------------------ the policy

def test_policy():
    def walls(front, back, left, right):
        return dict(front_wall=f'"{front}"', back_wall=f'"{back}"', left_wall=f'"{left}"', right_wall=f'"{right}"')
    kinds = ("topped", "topless", "simple")
    check("the rules are the documented ones", policy.RULES == dict(
        LIMITS=dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2),
        DRIFT=dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002),
        N_SAMPLES=50000, SAMPLE_SEED=7, P99=0.99, SOUND_VOL=0.01, CROSSING_LIMIT=1e-3, CORNER_TOL=1e-7,
        BARY_TOL=1e-10, MERGE_TOLS=(1e-5, 1e-4), EXPORT_FORMAT=("--export-format", "binstl"), RENDER_LIMIT=3600,
        CONSOLE_STATISTICS=(
            r"Geometries in cache: [0-9]+",
            r"Geometry cache size in bytes: [0-9]+",
            r"CGAL Polyhedrons in cache: [0-9]+",
            r"CGAL cache size in bytes: [0-9]+",
            r"Total rendering time: [0-9]+:[0-9][0-9]:[0-9][0-9]\.[0-9][0-9][0-9]",
            r"   Top level object is a 3D object:",
            r"   Simple:        yes",
            r"   Vertices: +[0-9]+",
            r"   Halfedges: +[0-9]+",
            r"   Edges: +[0-9]+",
            r"   Halffacets: +[0-9]+",
            r"   Facets: +[0-9]+",
            r"   Volumes:         2")))
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
    check("every configuration with expected notes is a listed configuration",
          set(policy.EXPECTED_MESSAGES) <= {n for n, _ in policy.SOUNDNESS})
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
    # the rejected values follow from the ranges the policy records: just off the lowest step, halfway to the
    # next, one step below the minimum and one step above the maximum
    probes = {name: p for name, p, _ in policy.REJECTED}
    derived = True
    for size in ("width", "height", "depth"):
        lo, step, hi = policy.CUSTOMIZER[f"{size}_lu"]
        want = dict(near_step=lo + 0.000002, between_steps=lo + step / 2, below=lo - step, above=hi + step)
        derived &= all(abs(probes[f"{size}_{k}"][f"{size}_lu"] - v) < 1e-12 for k, v in want.items())
    check("the rejected values follow from the recorded ranges", derived)
    rendered = [p for _, p in policy.SOUNDNESS]
    ends = True
    for name in ("width_lu", "height_lu", "depth_lu"):
        lo, _, hi = policy.CUSTOMIZER[name]
        ends &= any(p.get(name) == lo for p in rendered) and any(p.get(name) == hi for p in rendered)
    check("both ends of every recorded range are rendered", ends)


# ------------------------------------------------------------------ the decisions

def test_decisions():
    lim, drift, nan = policy.LIMITS, policy.DRIFT, float("nan")
    zero = dict.fromkeys(drift, 0.0)
    for field, limit in lim.items():
        check(f"HARD {field} at the limit passes", not regress.hard_failures("K", dict(lim)))
        check(f"HARD {field} just over the limit fails", regress.hard_failures("K", dict(lim, **{field: limit + 1e-9})))
    check("HARD fails a metric that is not a number", regress.hard_failures("K", dict(lim, mx=nan)))
    check("HARD names every metric over its limit", len(regress.hard_failures("K", {f: v + 1 for f, v in lim.items()})) == 4)
    s = compare.summary(row(bbox=0.011, vol=0.022, p99=(0.01, 0.03), mx=(0.02, 0.01), vmax=(0.04, 0.05)))
    check("summary is the bounding box, the volume, p99 from the worse direction, and the largest of the "
          "sampled and vertex maxima", s == dict(bbox=0.011, vol=0.022, p99=0.03, mx=0.05))
    check("summary takes the maximum from the samples when they are larger",
          compare.summary(row(mx=(0.07, 0.01), vmax=(0.04, 0.05)))["mx"] == 0.07)
    check("summary carries a value that is not a number into the maximum",
          np.isnan(compare.summary(row(vmax=(0.0, nan)))["mx"]) and np.isnan(compare.summary(row(p99=(nan, 0.0)))["p99"]))
    n = policy.N_SAMPLES
    check("the required number of samples in both directions passes", not regress.sample_failures("K", row()))
    for label, counts in (("one sample fewer on the reference", [n - 1, n]), ("one sample fewer on the render", [n, n - 1]),
                          ("one sample more on the reference", [n + 1, n]), ("one sample more on the render", [n, n + 1]),
                          ("a count for one direction only", [n]), ("a single number", n), ("no count", None)):
        check(f"{label} fails", len(regress.sample_failures("K", dict(row(), samples=counts))) == 1)
    check("a baseline entry that is not a table of values counts as an empty one",
          regress.entries(dict(models=dict(a=None, b=dict(x=1), c=5, d=[])), "models") == dict(a={}, b=dict(x=1), c={}, d={})
          and regress.entries({}, "soundness") == {})
    said = "width_lu must be a multiple of 0.5 from 1 to 12, not 1.25"
    check("a console text holds an error only as the whole quoted message",
          regress.stopped_with(REJECTION, said) and not regress.stopped_with(REJECTION, said[:-3])
          and not regress.stopped_with(REJECTION, said[:-1]) and not regress.stopped_with(REJECTION.replace('"', ""), said)
          and not regress.stopped_with("", said))
    for field, tol in drift.items():
        check(f"DRIFT {field} at the tolerance passes", not regress.drift_failures("K", dict(zero, **{field: tol}), zero))
        check(f"DRIFT {field} just over fails", regress.drift_failures("K", dict(zero, **{field: tol + 1e-9}), zero))
        check(f"DRIFT {field} improvement passes", not regress.drift_failures("K", zero, dict(zero, **{field: 1.0})))
    check("DRIFT fails a metric that is not a number", len(regress.drift_failures("K", dict.fromkeys(drift, nan), zero)) == 4)
    check("a locked metric missing from the baseline fails",
          len(regress.drift_failures("K", zero, {k: v for k, v in zero.items() if k != "p99"})) == 1
          and len(regress.drift_failures("K", zero, {})) == len(zero))

    a = compare.audit(stl("cube", cube()))
    check("an unchanged shape passes", not regress.lock_failures("n", a, dict(a)))
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
    check("a baseline entry with no shape locked fails", regress.lock_failures("n", a, dict(volume=a["volume"])))
    unusable = lambda what: [f"n: baseline entry has no usable {what}; relock to cover it"]     # noqa: E731
    for gone in ("volume", "extents"):
        check(f"a baseline entry without its {gone} fails and says so",
              regress.lock_failures("n", a, {k: v for k, v in a.items() if k != gone}) == unusable(gone))
    check("a baseline entry with only its digest names both things it lacks",
          regress.lock_failures("n", a, dict(digest=a["digest"])) == unusable("volume or extents"))
    huge = 10 ** 400        # valid JSON, and too large to be a floating-point number
    for bad in (None, "1.0", nan, float("inf"), True, [1.0], huge):
        check(f"a baseline volume of {str(bad)[:12]!r} fails as unusable",
              regress.lock_failures("n", a, dict(a, volume=bad)) == unusable("volume"))
    check("a baseline volume written as a whole number is usable",
          not regress.lock_failures("n", dict(a, volume=5.0), dict(a, volume=5)))
    for bad in (None, "0.0", nan, True, huge):
        found = regress.drift_failures("K", zero, dict(zero, p99=bad))
        check(f"a locked metric of {str(bad)[:12]!r} fails as having no locked value",
              found == ["K: DRIFT p99: no locked value in the baseline"])
    for bad in (None, [], a["extents"][:2], a["extents"] + [1.0], a["extents"][:2] + ["x"], a["extents"][:2] + [nan], "abc", 3.0):
        check(f"baseline extents of {bad!r} fail as unusable",
              regress.lock_failures("n", a, dict(a, extents=bad)) == unusable("extents"))
    check("extents read as a tuple of three numbers are usable", not regress.lock_failures("n", a, dict(a, extents=tuple(a["extents"]))))
    found = regress.lock_failures("n", dict(a, volume=nan), dict(a))
    check("a render whose own volume is not a number fails the lock", len(found) == 1 and "(volume;" in found[0])
    check("relocking ignores the baseline", not regress.lock_failures("n", a, None))

    # coverage: a reference is reported once, as a missing file or as absent from the baseline
    ref = REFERENCES[0]
    names = {n: {} for n, _ in policy.SOUNDNESS}
    held = {k: {} for k in REFERENCES}
    lacking = {k: {} for k in REFERENCES[1:]}
    for label, missing, models, want in (
            ("its file missing and the baseline holding it", [ref], held, [f"{ref}: reference file missing"]),
            ("its file missing and the baseline lacking it", [ref], lacking, [f"{ref}: reference file missing"]),
            ("its file present and the baseline lacking it", [], lacking, [f"{ref}: absent from baseline"]),
            ("its file present and the baseline holding it", [], held, [])):
        found = regress.coverage_failures(missing, dict(models=models, soundness=names), False)
        check(f"a reference with {label} gives exactly the line for that case",
              len(found) == len(want) and all(w in f for w, f in zip(want, found)))
    found = regress.coverage_failures([], dict(models=dict(held, X999={}), soundness=dict(names, extra={})), False)
    check("a reference and a configuration the policy does not list are each reported",
          len(found) == 2 and "X999: in the baseline but not in" in found[0]
          and "soundness/extra: in the baseline but no longer checked" in found[1])
    check("a relock reports only missing files, whatever the old baseline holds",
          regress.coverage_failures([ref], dict(models=dict(lacking, X999={}), soundness=dict(extra={})), True)
          == [f"{ref}: reference file missing: {refs.fname(ref)}"])

    # a size the sliders cannot produce: the file and the error, each alone and together
    for path, stopped, lines in ((None, True, 0), ("f.stl", True, 1), (None, False, 1), ("f.stl", False, 2)):
        found = regress.rejection_failures("w", path, stopped, "E")
        check(f"a rejected size with {'a' if path else 'no'} file and {'its' if stopped else 'no'} error gives "
              f"{lines} failure(s)", len(found) == lines)
    check("a rejected size's two failures say which",
          regress.rejection_failures("w", "f.stl", False, "E")
          == ["rejected/w: expected the render to stop, and it wrote a file",
              "rejected/w: expected the render to stop with: E"])

    # the locked generator: the baseline's digest and the report's, each alone and together
    for locked, reported, want in (("D", "D", []), ("X", "D", ["baseline"]), ("D", "X", ["VERIFICATION.md"]),
                                   ("X", "Y", ["baseline", "VERIFICATION.md"]), (None, None, ["baseline", "VERIFICATION.md"])):
        found = regress.locked_generator_failures("D", locked, reported)
        check(f"a generator D against a baseline for {locked} and a report for {reported} gives the lines for "
              f"{want or 'neither'}", len(found) == len(want) and all(w in f for w, f in zip(want, found)))

    # a 3MF export: coincident vertices and each merge distance, alone and together
    none = dict.fromkeys(policy.MERGE_TOLS, 0)
    both = dict.fromkeys(policy.MERGE_TOLS, 1)
    check("a 3MF export with no fault passes", not regress.threemf_failures("n", 0, none))
    check("one group of coincident 3MF vertices fails", len(regress.threemf_failures("n", 1, none)) == 1)
    for tol in policy.MERGE_TOLS:
        found = regress.threemf_failures("n", 0, {**none, tol: 1})
        check(f"one edge left by a merge within {tol:g} mm fails and names the distance",
              len(found) == 1 and f"within {tol:g} mm" in found[0])
    check("an edge left at both merge distances gives a line for each", len(regress.threemf_failures("n", 0, both)) == 2)
    check("coincident vertices and both merge distances together give three lines",
          len(regress.threemf_failures("n", 3, both)) == 3)

    check("a crossing at the limit is sound", compare.clean(dict(a, crossing_depth=policy.CROSSING_LIMIT)))
    check("a crossing just over the limit is not", not compare.clean(dict(a, crossing_depth=policy.CROSSING_LIMIT + 1e-9)))
    check("a crossing depth that is not a number is not sound", not compare.clean(dict(a, crossing_depth=nan)))
    check("a mesh of zero volume is not sound",
          not compare.clean(dict(a, volume=0.0)) and compare.unsound_reasons(dict(a, volume=0.0)) == ["volume 0.0 not positive"])
    for field, bad in (("watertight", False), ("winding", False), ("volume", -1.0), ("bodies", 2),
                       ("bad_edges", 1), ("dup_faces", 1), ("crossing_depth", policy.CROSSING_LIMIT + 1e-9)):
        check(f"a mesh failing only on {field} is not sound, and that alone is named",
              not compare.clean(dict(a, **{field: bad})) and len(compare.unsound_reasons(dict(a, **{field: bad}))) == 1)
    everything = dict(watertight=False, winding=False, bad_edges=1, dup_faces=1, bodies=2, volume=-1.0, crossing_depth=1.0)
    for one, two in itertools.combinations(everything, 2):
        pair = dict(a, **{one: everything[one], two: everything[two]})
        check(f"a mesh failing on {one} and {two} together is not sound, with both named",
              not compare.clean(pair) and len(compare.unsound_reasons(pair)) == 2)
    check("a sound mesh has no failure reasons", compare.clean(a) and compare.unsound_reasons(a) == [])
    check("a crossing is named with its depth",
          compare.unsound_reasons(dict(a, crossing_depth=0.0058)) == ["triangles crossing 0.0058 mm deep"])


def test_console():
    """The console decision: the whole text, in one piece."""
    ok = console(NOTES)
    fails = lambda text, stdout="", notes=NOTES: regress.console_failures("K", text, stdout, notes)   # noqa: E731
    check("the console text OpenSCAD wrote, after its two notes, passes", fails(ok) == [])
    check("the console text with no notes passes when none are expected", fails(STATISTICS, notes=()) == [])
    swapped = ok.replace("   Edges:        5948\n   Halffacets:   4724\n", "   Halffacets:   4724\n   Edges:        5948\n")
    bad = {
        "a line before the first": "WARNING: x\n" + ok,
        "a line between the notes and the statistics": ok.replace(STATISTICS, "WARNING: x\n" + STATISTICS),
        "a line between two statistics lines": ok.replace("   Simple:", "WARNING: x\n   Simple:"),
        "a line after the last": ok + "WARNING: x\n",
        "an empty line after the last": ok + "\n",
        "an empty line before the first": "\n" + ok,
        "no line feed at the end": ok[:-1],
        "a missing note": console(NOTES[:1]),
        "no notes at all": STATISTICS,
        "the notes in the other order": console(NOTES[::-1]),
        "a note twice": console(NOTES + NOTES[1:]),
        "one note more than expected": console(NOTES + ("NOTE: c",)),
        "text after a note on its line": ok.replace('channel."\n', 'channel." and more\n', 1),
        "spaces after a note": ok.replace('channel."\n', 'channel."   \n', 1),
        "a form feed after a note": ok.replace('channel."\n', 'channel."\f\n', 1),
        "spaces before a note": " " + ok,
        "a note with another character where it has a full stop": ok.replace("channel.", "channelX", 1),
        "a carriage return inside a line": ok.replace("Geometries", "\rGeometries"),
        "a statistics line twice": ok.replace("   Vertices:     3648\n", "   Vertices:     3648\n   Vertices:     9999\n"),
        "a statistics line missing": ok.replace("   Edges:        5948\n", ""),
        "two statistics lines in the other order": swapped,
        "words where a statistics line has its number": ok.replace("   Vertices:     3648", "   Vertices: WARNING thin shell"),
        "text after a statistics number": ok.replace("   Vertices:     3648", '   Vertices:     3648"'),
        "a number in digits of another script": ok.replace("3648", "\u0663\u0666\u0664\u0668"),
        "a result that is not simple": ok.replace("Simple:        yes", "Simple:        no"),
        "three volumes": ok.replace("Volumes:         2", "Volumes:         3"),
        "a second digit after the two volumes": ok.replace("Volumes:         2", "Volumes:        23"),
        "the nonplanar-face notice": "PolySet has nonplanar faces. Attempting alternate construction\n" + ok,
        "a rejected render's output": REJECTION,
        "nothing": "",
    }
    for label, text in bad.items():
        check(f"a console text with {label} fails", len(fails(text)) == 1 and "console output is not the expected text" in fails(text)[0])
    check("the notes of another configuration fail a render that expects none", len(fails(ok, notes=())) == 1)
    check("anything on standard output fails", fails(ok, stdout="x") == ["K: standard output is not empty: 'x'"])
    check("a wrong console text and standard output together give two failures", len(fails("x\n", stdout="y")) == 2)
    told = lambda text, notes=(): fails(text, notes=notes)[0].split("expected text: ", 1)[1]   # noqa: E731
    check("the failure quotes the first line that differs", told("WARNING: x\n" + STATISTICS) == "line 1 is 'WARNING: x'")
    check("the failure quotes an empty line where a line is expected",
          told(STATISTICS.replace("   Volumes:         2\n", "")) == "line 13 is ''")
    check("the failure says which line is missing when the text stops early", told("Geometries in cache: 297") == "line 2 is missing")
    check("the failure quotes what comes after the last line", told(STATISTICS + "more\n") == "after line 13 comes 'more\\n'")
    check("the failure says when the last line feed is missing", told(STATISTICS[:-1]) == "line 13 does not end with a line feed")


# ------------------------------------------------------------------ the measuring and mesh tools

def test_measure():
    m = cube()
    r, _ = compare.measure(m, m.copy(), n_samples=2000)
    check("identical meshes measure zero", max(compare.summary(r).values()) < 1e-9)
    check("measure reports the number of samples it drew in each direction", r["samples"] == [2000, 2000])
    drawn = iter((7, 2000))
    real = trimesh.sample.sample_surface
    trimesh.sample.sample_surface = lambda mesh, count, **kw: real(mesh, next(drawn), **kw)
    try:
        r, _ = compare.measure(m, m.copy(), n_samples=2000)
    finally:
        trimesh.sample.sample_surface = real
    check("measure reports each direction's own count, the reference's first", r["samples"] == [7, 2000])
    # a render 1.0 mm narrower and 1.5 mm shorter than its reference, with a 2 mm cube floating inside it, placed
    # elsewhere: every figure differs from the others, and the two directions differ
    gen = joined(trimesh.creation.box(extents=(9.0, 8.5, 10.0)), trimesh.creation.box(extents=(2, 2, 2)))
    r, spots = compare.measure(m, gen.apply_translation((5, -3, 2)))
    check("measure gives these figures for a fixed pair of meshes", close(r, {
        "bbox": 1.5, "vol": 22.7, "samples": [50000, 50000],
        "ref->gen": dict(mean=0.507024773, p95=1.5, p99=1.619601016, mx=1.80267777, vmax=1.802775638),
        "gen->ref": dict(mean=0.508892541, p95=1.5, p99=4.0, mx=4.75, vmax=4.0)}))
    check("measure returns the points and distances behind each direction's figures",
          all(len(p) == len(d) == 50000 + n and abs(d.max() - max(r[tag]["mx"], r[tag]["vmax"])) < 1e-12
              for tag, n, (p, d) in (("ref->gen", 8, spots["ref->gen"]), ("gen->ref", 16, spots["gen->ref"]))))
    taller = trimesh.creation.box(extents=(10, 10, 10.1))
    r, _ = compare.measure(m, taller, n_samples=20000)
    check("p99 sees a face 0.1 mm off", abs(compare.summary(r)["p99"] - 0.1) < 1e-3)
    pts = np.array([[0.0, 0, 0], [1, 0, 0], [2, 0, 0], [10, 0, 0], [20, 0, 0]])
    worst = compare.clusters(pts, np.array([0.1, 0.3, 0.3, 0.2, 0.05]), 2)
    check("the worst-spot listing keeps the first worst point of each 3 mm cell, largest first, up to the number asked",
          [(list(p), d) for p, d in worst] == [([1.0, 0.0, 0.0], 0.3), ([10.0, 0.0, 0.0], 0.2)])


def test_audit():
    m = cube()
    check("the audit of a 10 mm cube is this", compare.audit(stl("cube", m)) == dict(
        watertight=True, winding=True, bodies=1, bad_edges=0, dup_faces=0, crossing_depth=0.0,
        extents=[10.0, 10.0, 10.0], volume=1000.0,
        digest="87c21a82484e1f5d5435b571193f5c72ee78c422f73c2661ec06b4b1a7355ba1"))
    shifted = trimesh.creation.box(extents=(30, 20, 10)).apply_translation((100, 50, 7))
    check("the audit of a 30 x 20 x 10 box placed elsewhere is this", compare.audit(stl("shifted", shifted)) == dict(
        watertight=True, winding=True, bodies=1, bad_edges=0, dup_faces=0, crossing_depth=0.0,
        extents=[30.0, 20.0, 10.0], volume=6000.0,
        digest="a4a635557720871240a45d6558c6e898079bff6a85d3a64db2498ab421b3951e"))
    inside_out = compare.audit(stl("inside_out", trimesh.Trimesh(m.vertices, m.faces[:, ::-1], process=False)))
    check("a cube turned inside out has a negative volume and is not sound",
          inside_out["volume"] == -1000.0 and not compare.clean(inside_out))
    flipped = m.faces.copy()
    flipped[0] = flipped[0][::-1]
    check("a face wound the wrong way is caught",
          not compare.audit(stl("flipped", trimesh.Trimesh(m.vertices, flipped, process=False)))["winding"])
    with np.errstate(divide="ignore", invalid="ignore"):       # the bow-tie encloses no volume
        bow_audit = compare.audit(bowtie())
    check("faces crossing while sharing a vertex are caught", bow_audit["crossing_depth"] > policy.CROSSING_LIMIT)
    check("two cubes touching at one vertex are two bodies",
          compare.audit(stl("touch", joined(cube(), cube((10, 10, 10)))))["bodies"] == 2)
    check("two separate cubes are not sound", not compare.clean(compare.audit(stl("apart", joined(cube(), cube((20, 0, 0)))))))
    cross = compare.audit(stl("cross", joined(cube(), cube((3, 3, 3)))))
    check("crossing cubes exceed the crossing limit", cross["crossing_depth"] > policy.CROSSING_LIMIT
          and not compare.clean(cross))
    opened = compare.audit(stl("open", trimesh.Trimesh(m.vertices, m.faces[1:], process=False)))
    check("a cube missing a face is not watertight", not opened["watertight"])
    check("a cube missing a face has edges not shared by two faces", opened["bad_edges"] == 3)
    for label, extra in (("in the same corner order", m.faces[:1]), ("starting from another corner", np.roll(m.faces[:1], 1, axis=1)),
                         ("wound the other way", m.faces[:1, ::-1])):
        doubled = trimesh.Trimesh(m.vertices, np.vstack([m.faces, extra]), process=False)
        check(f"a facet written twice, {label}, is counted", compare.audit(stl("dup", doubled))["dup_faces"] == 1)
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
    for i, axis in itertools.product(range(len(m.vertices)), range(3)):
        moved = m.vertices.copy()
        moved[i, axis] += 1e-4
        if compare.audit(stl("moved", trimesh.Trimesh(moved, m.faces, process=False)))["digest"] == d0:
            unchanged.append((i, axis))
    check("digest changes when any one vertex moves 0.0001 mm along any axis", not unchanged)

    # crossings: a triangle whose edge passes through another, whichever comes first and whichever edge it is.
    # In the first case one edge of each triangle passes through the other, so every pairing of corner orders
    # puts those two edges in every position.
    face = [[0, 0, 0], [10, 0, 0], [0, 10, 0]]
    cases = (("through the middle", [[2, 2, -1], [2, 2, 1], [30, 30, 1]], 1, 1.0),
             ("by 0.0015 mm", [[2, 2, -1], [2, 2, 0.0015], [3, 3, -1]], 1, 0.0015),
             ("by 0.0005 mm", [[2, 2, -1], [2, 2, 0.0005], [3, 3, -1]], 1, 0.0005),
             ("not at all", [[2, 2, 0.5], [2, 2, 1], [3, 3, 1]], 0, 0.0))

    def orders(t):
        return [t[0], t[1], t[2]], [t[2], t[0], t[1]], [t[1], t[2], t[0]]
    for label, pts, count, depth in cases:
        v = np.array(face + pts, dtype=float)
        got = {export_check.crossings(v, np.array(faces))
               for one in orders([0, 1, 2]) for two in orders([3, 4, 5]) for faces in ([one, two], [two, one])}
        check(f"an edge passing through a triangle {label} is found the same from either triangle and any edge",
              len(got) == 1 and close(list(got)[0], (count, depth), 1e-12))
    small = np.array([[0, 0, 0], [0.01, 0, 0], [0, 0.01, 0], [0.002, 0.002, -1], [0.002, 0.002, 1], [0.5, 0.5, 1]])
    check("an edge through a triangle 0.01 mm across is found",
          close(export_check.crossings(small, np.array([[0, 1, 2], [3, 4, 5]])), (1, 0.0070710678118654745), 1e-12))
    tri = np.array(face, dtype=float)

    def through(x, y):
        """Whether a vertical edge through (x, y) crosses the face."""
        p0, p1 = np.array([[x, y, -1.0]]), np.array([[x, y, 1.0]])
        return bool(export_check.segment_crosses(p0, p1, tri[None, 0], tri[None, 1], tri[None, 2])[0])
    check("an edge through the inside of a face is a crossing", through(0.5, 0.5))
    check("an edge through a face's corner is a shared point", not through(policy.CORNER_TOL / 10, policy.CORNER_TOL / 10))
    check("an edge through a face's edge is a crossing", through(0.0, 3.0))
    check("an edge passing 0.005 mm outside a face is not a crossing", not through(-0.005, 3.0))


def test_3mf():
    for name, coords, groups in (("apart", [(0, 0, 0), (1, 0, 0)], 0),
                                 ("together", [(0, 0, 0), (1, 0, 0), (0, 0, 0)], 1),
                                 ("signed zero", [("0.000000", 0, 0), ("-0.000000", 0, 0)], 1)):
        check(f"3MF coincident vertices counted ({name})", export_check.coincident_3mf(threemf(name, model(coords))) == groups)
    single = threemf("single_quotes", "<model><mesh><vertices><vertex x='0' y='0' z='0'/><vertex x='1' y='0' z='0'/>"
                                      "<vertex x='0' y='0' z='0'/></vertices><triangles>"
                                      "<triangle v1='0' v2='1' v3='2'/></triangles></mesh></model>")
    check("a 3MF written with single quotes is read", export_check.coincident_3mf(single) == 1)
    for name, text in (("no mesh", "<model><mesh><vertices/><triangles/></mesh></model>"),
                       ("no triangles", model([(0, 0, 0), (1, 0, 0)], tris=())), ("no vertices", model([]))):
        try:
            export_check.read_3mf(threemf(name.replace(" ", "_"), text))
            refused = False
        except ValueError:
            refused = True
        check(f"a 3MF with {name} is an error, not a pass", refused)
    near = fin(0.000005)
    check("3MF merge folds a fin into an edge with four triangles", export_check.merge_faults(near, 1e-5) == 1)
    check("3MF merge leaves vertices farther apart than the distance", export_check.merge_faults(near, 1e-6) == 0)
    for tol in policy.MERGE_TOLS:
        check(f"3MF merge within {tol:g} mm folds vertices at 0.999 of the distance and leaves those at 1.001 of it",
              export_check.merge_faults(fin(0.999 * tol), tol) == 1 and export_check.merge_faults(fin(1.001 * tol), tol) == 0)


# ------------------------------------------------------------------ the render function and the real steps

STUB = [sys.executable, str(HERE / "fixtures" / "stub_openscad.py")]


@contextlib.contextmanager
def stand_in(write=True, console=b"", stdout=b""):
    """Point every render at the stand-in for OpenSCAD, which writes these bytes."""
    TMP.mkdir(parents=True, exist_ok=True)
    (TMP / "stub_console.bin").write_bytes(console)
    (TMP / "stub_stdout.bin").write_bytes(stdout)
    saved, compare.OPENSCAD_COMMAND = compare.OPENSCAD_COMMAND, STUB
    os.environ.update(STUB_WRITE="1" if write else "0", STUB_CONSOLE=str(TMP / "stub_console.bin"),
                      STUB_STDOUT=str(TMP / "stub_stdout.bin"))
    try:
        yield
    finally:
        compare.OPENSCAD_COMMAND = saved
        for name in ("STUB_WRITE", "STUB_CONSOLE", "STUB_STDOUT"):
            del os.environ[name]


def stub_args(out):
    """The arguments the stand-in received for an output file."""
    return json.loads(Path(str(out) + ".args.json").read_text(encoding="utf-8"))


def test_render():
    folder = TMP / "render"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "a.stl"
    with stand_in(console=b"one\r\ntwo\rthree\nfour\r\n", stdout=b"out\r\n"):
        r = compare.render(STUB, "gen.scad", dict(width_lu=2, front_wall='"topped"'), out)
    check("a render returns its file, and everything written to both streams with only CR LF pairs folded",
          sorted(r) == ["console", "path", "seconds", "stdout"] and r["path"] == out and out.is_file()
          and r["console"] == "one\ntwo\rthree\nfour\n" and r["stdout"] == "out\n" and r["seconds"] > 0)
    check("the render passes the output, the generator and every parameter",
          stub_args(out) == ["-o", str(out), "--export-format", "binstl", "gen.scad",
                             "-D", "width_lu=2", "-D", 'front_wall="topped"'])
    long_text = b"x" * 5000 + b"\r\nend\r\n"
    with stand_in(console=long_text):
        r = compare.render(STUB, "gen.scad", {}, folder / "a.3mf")
    check("a 3MF render does not ask for binary STL",
          "--export-format" not in stub_args(folder / "a.3mf") and r["path"] is not None)
    check("a long console text is returned whole", r["console"] == "x" * 5000 + "\nend\n")
    check("bytes that are not text do not stop a render",
          "\ufffd" in compare.as_written(b"\xff\xfe") and compare.as_written(b"a\r\n\r\nb") == "a\n\nb")
    out.write_text("left by an earlier run", encoding="utf-8")
    with stand_in(write=False):
        r = compare.render(STUB, "gen.scad", {}, out)
    check("a render that wrote no file returns no path, and nothing where nothing was printed",
          r["path"] is None and r["console"] == "" and r["stdout"] == "")
    check("a file left by an earlier run is deleted before the render", not out.exists())
    with stand_in():
        r = compare.render(STUB, "gen.scad", {}, folder / "new" / "b.stl")
    check("a render makes its output folder", r["path"] == folder / "new" / "b.stl")

    # a render stopped at the time limit: a stand-in for subprocess.run writes half a file and then runs out of time
    asked = {}

    def late(args, **kw):
        asked.update(kw)
        Path(args[args.index("-o") + 1]).write_text("half a file", encoding="utf-8")
        raise subprocess.TimeoutExpired(args, kw.get("timeout", 0), output=b"some out\r\n", stderr=b"some text\r\n")

    def silent(args, **kw):
        raise subprocess.TimeoutExpired(args, kw.get("timeout", 0))

    def finished_printing(args, **kw):
        raise subprocess.TimeoutExpired(args, kw.get("timeout", 0), stderr=STATISTICS.replace("\n", "\r\n").encode())

    def broken(args, **kw):
        raise OSError("no such program")
    said = f"render stopped after {policy.RENDER_LIMIT} s\n"
    r = compare.render(STUB, "gen.scad", {}, out, run=late)
    check("a render stopped at the time limit returns no path and deletes what it had written",
          r["path"] is None and not out.exists())
    check("a stopped render says so after what it had printed, and keeps what it wrote to standard output",
          r["console"] == "some text\n\n" + said and r["stdout"] == "some out\n")
    check("every render runs under the policy's time limit, with both streams captured",
          asked == dict(capture_output=True, timeout=policy.RENDER_LIMIT))
    r = compare.render(STUB, "gen.scad", {}, out, run=silent)
    check("a stopped render that printed nothing still says it was stopped",
          r["path"] is None and r["console"] == "\n" + said and r["stdout"] == "")
    r = compare.render(STUB, "gen.scad", {}, out, run=finished_printing)
    check("a render stopped after printing a whole clean console text still fails the console comparison",
          r["console"] == STATISTICS + "\n" + said and regress.console_failures("K", r["console"], r["stdout"], ()))
    try:
        compare.render(STUB, "gen.scad", {}, out, run=broken)
        kept = False
    except OSError:
        kept = True
    except Exception:
        kept = False
    check("an error that is not the time limit is not taken for a stopped render", kept)

    # the path of OpenSCAD: its Windows console wrapper, openscad.com, is replaced by the program beside it.
    # shutil.which is replaced here by a lookup that knows only this folder, so the machine's own PATH plays no part
    tools = folder / "tools"
    tools.mkdir(exist_ok=True)
    for name in ("openscad.com", "openscad.exe", "alone.com"):
        (tools / name).write_text("", encoding="utf-8")
    wrapper, exe = str(tools / "openscad.com"), str(tools / "openscad.exe")
    on_path = {"openscad": str(tools / "openscad.COM"), "openscad.com": wrapper, "elsewhere": exe}
    paths = compare.mbpaths
    program = paths.program_not_wrapper
    saved = paths._local, paths.shutil.which, os.environ.pop("OPENSCAD", None)
    try:
        paths._local = lambda: {}
        paths.shutil.which = lambda name: on_path.get(str(name)) or (str(name) if Path(str(name)).is_file() else None)
        check("a path to OpenSCAD's console wrapper becomes the program beside it",
              program(tools / "openscad.com") == exe and program(str(tools / "openscad.COM")) == exe)
        check("a bare wrapper name, and a bare name that PATH resolves to the wrapper, become the program",
              program("openscad.com") == exe and program("openscad") == exe)
        check("a wrapper with no program beside it, the program itself and a name PATH does not know are kept as given",
              program(tools / "alone.com") == str(tools / "alone.com") and program(exe) == exe
              and program("nowhere.com") == "nowhere.com" and program("other") == "other")
        check("a name that PATH resolves to something that is not a wrapper is kept as given, not as its looked-up path",
              program("elsewhere") == "elsewhere")
        check("a console wrapper found on PATH is replaced by the program", paths._openscad() == exe)
        on_path.clear()
        paths._local = lambda: dict(openscad=wrapper)
        check("a console wrapper named in local-paths.json is replaced by the program", paths._openscad() == exe)
        paths._local = lambda: {}
        os.environ["OPENSCAD"] = wrapper
        check("a console wrapper named in the OPENSCAD variable is replaced by the program", paths._openscad() == exe)
    finally:
        paths._local, paths.shutil.which = saved[0], saved[1]
        os.environ.pop("OPENSCAD", None)
        if saved[2] is not None:
            os.environ["OPENSCAD"] = saved[2]


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
    with stand_in(console=b"WARNING: y\r\n"):
        r = steps.render(OTHER_SCAD, "soundness/a.stl", dict(width_lu=3))
        version = steps.renderer()
    args = stub_args(target)
    check("the real render step writes under the SCAD file's own output folder and returns the console text",
          r["path"] == target and r["console"] == "WARNING: y\n" and r["stdout"] == "")
    check("the real render step passes the SCAD file, the parameters and the binary STL format",
          str(OTHER_SCAD) in args and "width_lu=3" in args and "binstl" in args)
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
    ref = REFERENCES[0]
    folder = TMP / "refs"
    folder.mkdir(parents=True, exist_ok=True)
    cube().export(folder / refs.fname(ref))
    saved, refs.STL_DIR = refs.STL_DIR, folder
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            m = steps.measure(ref, stl("scaled", cube().apply_scale(1.01)))
        missing = steps.missing_refs()
    finally:
        refs.STL_DIR = saved
    check("the real measure step measures volume", abs(m["vol"] - (1.01 ** 3 - 1) * 100) < 1e-3)   # STL keeps 32-bit floats
    check("the real measure step measures the bounding box", abs(m["bbox"] - 0.1) < 1e-6)
    check("the real measure step measures both directions", m["ref->gen"]["vmax"] > 0.04 and m["gen->ref"]["vmax"] > 0.04)
    check("the real measure step draws the required number of samples in each direction",
          m["samples"] == [policy.N_SAMPLES, policy.N_SAMPLES])
    check("the real coverage step finds missing references", missing == list(REFERENCES[1:]))
    check("the generator digest folds CR LF pairs and nothing else",
          steps.digest(OTHER_SCAD) == hashlib.sha256(b"cube(1);\n").hexdigest().upper()
          and compare.scad_digest(OTHER_SCAD) != hashlib.sha256(b"cube(1);\r").hexdigest().upper())
    # the real file steps, pointed at scratch files
    saved = regress.BASELINE, regress.REPORT, regress.UNIT_TESTS
    regress.BASELINE, regress.REPORT = TMP / "baseline.json", TMP / "REPORT.md"
    rows = [dict(row(key="K1", bbox=0.001, vol=0.02, p99=(0.03, 0.01), mx=(0.02, 0.04), vmax=(0.05, 0.03)), seconds=12.4),
            dict(row(key="K2", bbox=0.006, vol=0.07, p99=(0.02, 0.08), mx=(0.09, 0.01), vmax=(0.02, 0.1)), seconds=99.6)]
    try:
        check("no baseline file loads as none", steps.load_baseline() is None)
        steps.write_baseline(dict(models={}, soundness={}, scad_digest="X"))
        check("the real baseline steps read back what they wrote",
              steps.load_baseline() == dict(models={}, soundness={}, scad_digest="X"))
        check("no report has no digest", steps.report_digest() is None)
        steps.write_report(regress.report_text(rows, "2026-01-01 00:00", "2026-01-01 00:30", "A" * 64, "OpenSCAD test"))
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
    lines = report.splitlines()
    check("the report's table has these two rows for two fixed measurements, the worse direction in each column",
          lines[-3:] == ["|---|---|---|---|---|---|---|",
                         "| K1 | 0.0010 | 0.020 | 0.0300 | 0.0400 | 0.0500 | 12 |",
                         "| K2 | 0.0060 | 0.070 | 0.0800 | 0.0900 | 0.1000 | 100 |"])
    check("the report names the run, the generator's digest, the renderer, the sample count and the limits",
          "from 2026-01-01 00:00 to 2026-01-01 00:30 UTC" in report and f"SHA-256 {'A' * 64}," in report
          and "Renderer: OpenSCAD test." in report and f"{policy.N_SAMPLES} points" in report
          and (f"bounding box <= {policy.LIMITS['bbox']} mm per axis, volume <= {policy.LIMITS['vol']} %, p99 <= "
               f"{policy.LIMITS['p99']} mm, and both maxima <= {policy.LIMITS['mx']} mm") in report)


# ------------------------------------------------------------------ the gate's run

def notes_for(name):
    """The notes the policy expects of the render with this output name."""
    stem = name.split("/")[-1].rsplit(".", 1)[0]
    return policy.EXPECTED_MESSAGES.get(stem, ())


class FakeSteps:
    """Stands in for OpenSCAD, the mesh tools and the files, so run() can be
    driven through each check in a fraction of a second. It records every call
    with its arguments, so a test can see what a run rendered and examined."""

    def __init__(self, baseline=None, **faults):
        self.baseline, self.written, self.report, self.calls = baseline, None, None, []
        self.scads = set()          # (step, SCAD file) for every step that is handed the file
        self.faults = faults
        self.digests = iter(faults.get("digests", []))
        self.errors = {f"soundness/{name}.stl": error for name, _, error in policy.REJECTED}

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

    def missing_refs(self):
        return list(self.faults.get("missing", []))

    def render(self, scad, name, params):
        self.calls.append(("render", name, dict(params)))
        self.scads.add((f"render {name}", scad))
        if name in self.errors:
            said = "" if name in self.faults.get("reject_silent", ()) else REJECTION.replace(
                "width_lu must be a multiple of 0.5 from 1 to 12, not 1.25", self.errors[name])
            return dict(path=name if name in self.faults.get("reject_writes", ()) else None, seconds=0.1,
                        console=said, stdout="")
        return dict(path=None if name in self.faults.get("no_file", ()) else name, seconds=1.0,
                    console=self.fault("console", name, console(notes_for(name))), stdout=self.fault("stdout", name, ""))

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
        return self.fault("coincident", path, 0)

    def merge_faults(self, path):
        self.calls.append(("merge_faults", path))
        return {tol: self.fault("merged", (path, tol), 0) for tol in policy.MERGE_TOLS}

    def renderer(self):
        return "OpenSCAD test"

    def load_baseline(self):
        return self.baseline

    def write_baseline(self, data):
        self.written = data

    def write_report(self, text):
        self.report = text


def gate_run(baseline, log=None, **kw):
    faults = {k: kw.pop(k) for k in list(kw) if k not in ("update", "accept", "alternate")}
    steps = FakeSteps(baseline, **faults)
    code, failures = regress.run(steps, "fake.scad", log=(lambda *a: None) if log is None else log.append, **kw)
    return code, failures, steps


def faults_table():
    """Every fault the gate is meant to report, each on a render, reference or
    baseline entry of its own so that any two can be present in one run. Each
    row: the check it belongs to, what it is, text that must be in the failure
    list, whether it must stop a relock even with --accept-drift, how the fault
    is put into the stand-in steps, and how it changes the baseline."""
    r = REFERENCES
    listed = {n for n, _ in policy.SOUNDNESS}

    def conf(name):
        assert name in listed, name
        return f"soundness/{name}"

    def tmf(name):
        assert name in THREEMF_CHECK, name
        return f"soundness/{name}.3mf"
    lacking = lambda kind, name: (lambda b: dict(b, **{kind: {k: v for k, v in b[kind].items() if k != name}}))  # noqa: E731
    holding = lambda kind, name, entry: (lambda b: dict(b, **{kind: dict(b[kind], **{name: entry})}))            # noqa: E731
    without = lambda kind, name, key: (lambda b: holding(kind, name, {k: v for k, v in b[kind][name].items() if k != key})(b))  # noqa: E731
    having = lambda kind, name, key, value: (lambda b: holding(kind, name, dict(b[kind][name], **{key: value}))(b))            # noqa: E731
    nan = float("nan")
    return [
        # check, label, texts, blocks a relock, step faults, baseline change
        ("locked generator", "a baseline locked on another generator", ["the baseline was locked on another version"],
         False, {}, lambda b: dict(b, scad_digest="OTHER")),
        ("locked generator", "a VERIFICATION.md for another generator", ["VERIFICATION.md is for another version"],
         False, dict(report_digest="OTHER"), None),
        ("generator unchanged", "a generator edited during the run", ["the file changed during the run"],
         True, dict(digests=["D", "E"]), None),
        ("reference coverage", "a missing reference file", [f"{r[0]}: reference file missing"],
         True, dict(missing=[r[0]]), None),
        ("reference coverage", "a listed reference the baseline lacks", [f"{r[1]}: absent from baseline"],
         False, {}, lacking("models", r[1])),
        ("reference coverage", "a baseline reference the policy does not list", ["X999: in the baseline but not in"],
         False, {}, holding("models", "X999", {})),
        ("configuration coverage", "a listed configuration the baseline lacks", [f"{conf('wide_12x1x1')}: absent from baseline"],
         False, {}, lacking("soundness", "wide_12x1x1")),
        ("configuration coverage", "a baseline configuration the policy does not list",
         ["soundness/extra: in the baseline but no longer checked"], False, {}, holding("soundness", "extra", {})),
        ("render success", "a failed reference render", [f"{r[2]}: render failed"],
         True, dict(no_file=[f"{r[2]}.stl"]), None),
        ("render success", "a failed configuration render", [f"{conf('defaults')}: render failed"],
         True, dict(no_file=[f"{conf('defaults')}.stl"]), None),
        ("render success", "a failed 3MF render", [f"{conf('half_both_2.5x1.5x1.5')}: 3MF render failed"],
         True, dict(no_file=[tmf("half_both_2.5x1.5x1.5")]), None),
        ("console output", "a reference render with another line", [f"{r[3]}: console output is not the expected text: line 1 is 'WARNING: x'"],
         True, dict(console={f"{r[3]}.stl": "WARNING: x\n" + STATISTICS}), None),
        ("console output", "a reference render that writes to standard output", [f"{r[4]}: standard output is not empty"],
         True, dict(stdout={f"{r[4]}.stl": "x"}), None),
        ("console output", "a configuration render with another line", [f"{conf('half_w_1.5x1x1')}: console output is not the expected text"],
         True, dict(console={f"{conf('half_w_1.5x1x1')}.stl": STATISTICS + "ECHO: x\n"}), None),
        ("console output", "a configuration render without one of its notes",
         [f"{conf('thin_1.5x0.5x1')}: console output is not the expected text: line 2 is"],
         True, dict(console={f"{conf('thin_1.5x0.5x1')}.stl": console(NOTES[:1])}), None),
        ("console output", "a 3MF render with another line", [f"{conf('thin_1.5x0.5x1')} 3MF: console output is not the expected text"],
         True, dict(console={tmf("thin_1.5x0.5x1"): console(NOTES) + "WARNING: x\n"}), None),
        ("hard limits", "a reference over a limit", [f"{r[5]}: HARD mx=0.3000"],
         True, dict(measure={r[5]: dict(mx=(0.3, 0.0))}), None),
        ("hard limits", "a reference metric that is not a number", [f"{r[6]}: HARD p99"],
         True, dict(measure={r[6]: dict(p99=(nan, 0.0))}), None),
        ("hard limits", "a reference measured from too few samples on the render",
         [f"{r[7]}: HARD measured from [50000, 500] sampled points"],
         True, dict(measure={r[7]: dict(samples=[policy.N_SAMPLES, 500])}), None),
        ("drift", "a reference worse than its locked value", [f"{r[8]}: DRIFT mx"],
         False, dict(measure={r[8]: dict(mx=(0.003, 0.0))}), None),
        # these two share a reference with a shape fault further down: a locked measure and a locked shape are judged apart
        ("drift", "a reference whose locked measure is null", [f"{r[11]}: DRIFT p99: no locked value"],
         False, {}, having("models", r[11], "p99", None)),
        ("drift", "a reference whose locked measure is a text", [f"{r[12]}: DRIFT bbox: no locked value"],
         False, {}, having("models", r[12], "bbox", "0.0")),
        ("mesh soundness", "an unsound reference", [f"{r[9]}: mesh not a clean single shell: not watertight"],
         True, dict(audit={f"{r[9]}.stl": dict(watertight=False)}), None),
        ("mesh soundness", "an unsound configuration", [f"{conf('half_h_2x1.5x2')}: mesh not a clean single shell: 2 bodies"],
         True, dict(audit={f"{conf('half_h_2x1.5x2')}.stl": dict(bodies=2)}), None),
        ("crossings", "crossing triangles in a reference", [f"{r[10]}: mesh not a clean single shell: triangles crossing 0.01 mm deep"],
         True, dict(audit={f"{r[10]}.stl": dict(crossing_depth=0.01)}), None),
        ("crossings", "crossing triangles in a configuration", [f"{conf('deep_1x1x4')}: mesh not a clean single shell: triangles crossing"],
         True, dict(audit={f"{conf('deep_1x1x4')}.stl": dict(crossing_depth=0.5)}), None),
        ("shape lock", "a reference's changed vertices", [f"{r[11]}: geometry changed vs baseline (vertices;"],
         False, dict(audit={f"{r[11]}.stl": dict(digest="x")}), None),
        ("shape lock", "a reference's changed volume", [f"{r[12]}: geometry changed vs baseline (volume;"],
         False, dict(audit={f"{r[12]}.stl": dict(volume=1.0 + policy.SOUND_VOL + 1e-6)}), None),
        ("shape lock", "a reference whose baseline entry is null", [f"{r[13]}: absent from baseline", f"{r[13]}: DRIFT bbox: no locked value"],
         False, {}, holding("models", r[13], None)),
        ("shape lock", "a configuration whose baseline entry is null", [f"{conf('mixed_walls_2x2x1')}: absent from baseline"],
         False, {}, holding("soundness", "mixed_walls_2x2x1", None)),
        ("shape lock", "a configuration whose baseline entry is empty", [f"{conf('simple_2x1x2')}: absent from baseline"],
         False, {}, holding("soundness", "simple_2x1x2", {})),
        ("shape lock", "a configuration whose baseline entry has no volume",
         [f"{conf('long_1x12x1')}: baseline entry has no usable volume"],
         False, {}, without("soundness", "long_1x12x1", "volume")),
        ("shape lock", "a configuration whose baseline entry has no extents",
         [f"{conf('topless_half_2.5x1.5x1.5')}: baseline entry has no usable extents"],
         False, {}, without("soundness", "topless_half_2.5x1.5x1.5", "extents")),
        ("shape lock", "a configuration's changed vertices", [f"{conf('tall_1x1x12')}: geometry changed vs baseline (vertices;"],
         False, dict(audit={f"{conf('tall_1x1x12')}.stl": dict(digest="x")}), None),
        ("shape lock", "a configuration whose vertices and volume both changed",
         [f"{conf('long_1x7x1')}: geometry changed vs baseline (vertices and volume;"],
         False, dict(audit={f"{conf('long_1x7x1')}.stl": dict(digest="x", volume=3.0)}), None),
        ("3MF coincident vertices", "coincident 3MF vertices", [f"{conf('wide_4x1x1')}: 3MF has 2 group(s)"],
         True, dict(coincident={tmf("wide_4x1x1"): 2}), None),
        ("3MF merges", "a 3MF that the smaller merge folds", [f"{conf('thin_1.5x0.5x1')}: 3MF merged within 1e-05 mm leaves 2 edge(s)"],
         True, dict(merged={(tmf("thin_1.5x0.5x1"), 1e-5): 2}), None),
        ("3MF merges", "a 3MF that the larger merge folds", [f"{conf('wide_4x1x1')}: 3MF merged within 0.0001 mm leaves 3 edge(s)"],
         True, dict(merged={(tmf("wide_4x1x1"), 1e-4): 3}), None),
        ("rejected sizes", "a size that stops without its error", ["rejected/height_below: expected the render to stop with"],
         True, dict(reject_silent=["soundness/height_below.stl"]), None),
        ("rejected sizes", "a rejected size that still writes a file", ["rejected/depth_above: expected the render to stop, and it wrote a file"],
         True, dict(reject_writes=["soundness/depth_above.stl"]), None),
        ("rejected sizes", "a size the generator builds instead of refusing",
         ["rejected/width_between_steps: expected the render to stop, and it wrote a file",
          "rejected/width_between_steps: expected the render to stop with"],
         True, dict(reject_silent=["soundness/width_between_steps.stl"], reject_writes=["soundness/width_between_steps.stl"]), None),
    ]


def together(*rows):
    """The step faults and the baseline change of several table rows at once."""
    faults, changes = {}, []
    for _, _, _, _, step, change in rows:
        for kind, value in step.items():
            if isinstance(value, dict):
                faults.setdefault(kind, {}).update(value)
            elif kind in ("digests", "report_digest"):
                faults[kind] = value
            else:
                faults.setdefault(kind, []).extend(value)
        if change:
            changes.append(change)

    def baseline(b):
        for change in changes:
            b = change(b)
        return b
    return faults, baseline


def has(failures, texts):
    return all(any(text in f for f in failures) for text in texts)


def test_checks():
    """Every check in regress.CHECKS, through run()."""
    code, failures, first = gate_run(None, update=True)
    locked = first.written
    check("a clean relock writes the baseline", code == 0 and locked is not None
          and list(locked["models"]) == list(REFERENCES)
          and list(locked["soundness"]) == [n for n, _ in policy.SOUNDNESS])
    lines = []
    code, failures, clean_run = gate_run(locked, log=lines)
    check("a clean run passes and says so", code == 0 and not failures and lines[-1].startswith("PASS - no failure in "))

    table = faults_table()
    for row_ in table:
        name, label, texts, blocks, _, _ = row_
        faults, change = together(row_)
        code, failures, _ = gate_run(change(locked), **faults)
        check(f"[{name}] a run fails on {label}", code == 1 and has(failures, texts))
        covered.add(name)
        code, failures, steps = gate_run(change(locked), update=True, accept=True, **faults)
        if blocks:
            check(f"[{name}] a relock is not written over {label}, even with --accept-drift",
                  code == 1 and steps.written is None and steps.report is None and has(failures, texts))
        else:
            check(f"[{name}] a relock with --accept-drift replaces {label}", code == 0 and steps.written is not None)
    missed = []
    for one, two in itertools.combinations(table, 2):
        faults, change = together(one, two)
        code, failures, _ = gate_run(change(locked), **faults)
        if not (code == 1 and has(failures, one[2] + two[2])):
            missed.append(f"{one[1]} with {two[1]}")
    check(f"a run with any two of the {len(table)} faults reports both ({'; '.join(missed[:3]) or 'none missed'})", not missed)
    report_missing = gate_run(locked, report_digest=None)
    check("[locked generator] a run fails without a VERIFICATION.md",
          report_missing[0] == 1 and has(report_missing[1], ["VERIFICATION.md is for another version"]))

    code, failures, steps = gate_run(locked, unit_tests=False)
    check("[unit tests] a run stops before rendering when gate_test.py fails", code == 2 and not steps.calls)
    covered.add("unit tests")

    # a clean run renders, measures and examines exactly what the policy lists
    def renders(names_params):
        return sorted((n, sorted(p.items())) for n, p in names_params)
    want = [(f"{k}.stl", compare.params(k)) for k in REFERENCES]
    for n, p in policy.SOUNDNESS:
        want.append((f"soundness/{n}.stl", p))
        if n in THREEMF_CHECK:
            want.append((f"soundness/{n}.3mf", p))
    want += [(f"soundness/{n}.stl", p) for n, p, _ in policy.REJECTED]
    done = lambda kind: [c[1:] for c in clean_run.calls if c[0] == kind]     # noqa: E731
    stls = [f"{k}.stl" for k in REFERENCES] + [f"soundness/{n}.stl" for n, _ in policy.SOUNDNESS]
    tmfs = [f"soundness/{n}.3mf" for n in THREEMF_CHECK]
    check("a clean run renders every reference, configuration, 3MF export and rejected size once, each with its own "
          "parameters", renders(done("render")) == renders(want))
    check("a clean run renders and digests the SCAD file it was given, and no other",
          clean_run.scads == {(f"render {n}", "fake.scad") for n, _ in want} | {("digest", "fake.scad")})
    check("a clean run measures every reference's own render", done("measure") == [(k, f"{k}.stl") for k in REFERENCES])
    check("a clean run audits every STL it rendered", sorted(c[0] for c in done("audit")) == sorted(stls))
    check("a clean run checks every 3MF export both ways",
          sorted(c[0] for c in done("coincident_3mf")) == sorted(tmfs)
          and sorted(c[0] for c in done("merge_faults")) == sorted(tmfs))
    check("a plain run writes neither the baseline nor the report", clean_run.written is None and clean_run.report is None)

    # the run's log, which is what a person reads
    changed, broken = "soundness/half_w_1.5x1x1.stl", "soundness/thin_1.5x0.5x1.stl"
    lines = []
    gate_run(locked, log=lines, audit={changed: dict(digest="x"), broken: dict(bodies=2)})
    state = {n: next(ln.split()[1] for ln in lines if ln.split()[:1] == [n]) for n, _ in policy.SOUNDNESS}
    check("the log marks a changed configuration, a broken one and the rest",
          state["half_w_1.5x1x1"] == "CHANGED" and state["thin_1.5x0.5x1"] == "BROKEN"
          and sorted(state.values()) == ["BROKEN", "CHANGED"] + ["ok"] * (len(state) - 2))
    lines = []
    gate_run(locked, log=lines, reject_writes=["soundness/depth_above.stl"])
    said = {ln.split()[0]: ln.split(None, 1)[1] for ln in lines if ln.split()[:1] and ln.split()[0] in {n for n, _, _ in policy.REJECTED}}
    check("the log marks a size that was not rejected, and the rest as rejected",
          said.pop("depth_above") == "NOT REJECTED" and set(said.values()) == {"rejected"} and len(said) == len(policy.REJECTED) - 1)

    # relock rules
    ref = REFERENCES[0]
    check("[relock rules] a relock records the generator's digest and writes the report naming it",
          locked.get("scad_digest") == "D" and first.report and "SHA-256 D," in first.report)
    check("[relock rules] the report a relock writes has a row for every reference, with its measurements",
          all(f"| {k} | 0.0000 | 0.000 |" in first.report for k in REFERENCES))
    check("[relock rules] a relock locks every render's shape",
          all("digest" in m and "volume" in m for m in locked["models"].values())
          and all("digest" in a for a in locked["soundness"].values()))
    check("[relock rules] a relock from another SCAD is refused", gate_run(locked, update=True, alternate=True)[0] == 2)
    check("[relock rules] a run without a baseline stops", gate_run(None)[0] == 2)
    drift = dict(measure={ref: dict(mx=(0.003, 0.0))})
    code, failures, steps = gate_run(locked, update=True, **drift)
    check("[relock rules] a relock refuses drift without --accept-drift",
          code == 1 and steps.written is None and steps.report is None and has(failures, ["--accept-drift", f"{ref}: DRIFT mx"]))
    lines = []
    code, failures, steps = gate_run(locked, log=lines, update=True, accept=True, **drift)
    check("[relock rules] a relock with --accept-drift writes the baseline and logs each change it accepts",
          code == 0 and steps.written is not None and any(ln.startswith("accepting 1 change(s)") for ln in lines)
          and any(f"- {ref}: DRIFT mx" in ln for ln in lines))
    lines = []
    gate_run(locked, log=lines, update=True)
    check("[relock rules] a relock that changes nothing logs no accepted change",
          not any(ln.startswith("accepting") for ln in lines))
    for label, path in (("configuration", "soundness/half_w_1.5x1x1.stl"), ("reference", f"{ref}.stl")):
        code, failures, steps = gate_run(locked, update=True, audit={path: dict(digest="x")})
        check(f"[relock rules] a relock refuses a {label}'s changed shape without --accept-drift",
              code == 1 and steps.written is None and has(failures, ["geometry changed vs baseline"]))
    code, failures, steps = gate_run(dict(locked, soundness=dict(locked["soundness"], extra={})), update=True)
    check("[relock rules] a relock refuses to drop a locked configuration without --accept-drift",
          code == 1 and steps.written is None and has(failures, ["soundness/extra: locked configuration no longer checked"]))
    code, failures, steps = gate_run(dict(locked, models=dict(locked["models"], X999=locked["models"][ref])), update=True)
    check("[relock rules] a relock refuses to drop a locked reference without --accept-drift",
          code == 1 and steps.written is None and has(failures, ["X999: locked reference no longer measured"]))
    for kind, name, label in (("models", ref, ref), ("soundness", "half_w_1.5x1x1", "soundness/half_w_1.5x1x1")):
        for entry in (None, {}):
            old = dict(locked, **{kind: dict(locked[kind], **{name: entry})})
            code, failures, steps = gate_run(old, update=True)
            check(f"[relock rules] a relock refuses to replace a {kind} entry that is {entry} without --accept-drift",
                  code == 1 and steps.written is None and has(failures, [f"{label}: absent from baseline", "--accept-drift"]))
        for gone in ("volume", "extents"):
            part = {k: v for k, v in locked[kind][name].items() if k != gone}
            old = dict(locked, **{kind: dict(locked[kind], **{name: part})})
            code, failures, steps = gate_run(old, update=True)
            check(f"[relock rules] a relock refuses to replace a {kind} entry without its {gone} without --accept-drift",
                  code == 1 and steps.written is None
                  and has(failures, [f"{label}: baseline entry has no usable {gone}", "--accept-drift"]))
            code, failures, steps = gate_run(old, update=True, accept=True)
            check(f"[relock rules] a relock with --accept-drift replaces a {kind} entry without its {gone}",
                  code == 0 and steps.written is not None and gone in steps.written[kind][name])
    for bad in (None, "0.0", 10 ** 400):
        old = dict(locked, models=dict(locked["models"], **{ref: dict(locked["models"][ref], mx=bad)}))
        lines = []
        code, failures, steps = gate_run(old, log=lines)
        check(f"[drift] a plain run fails, without stopping, on a locked measure of {str(bad)[:8]!r}, and its log shows no difference for it",
              code == 1 and has(failures, [f"{ref}: DRIFT mx: no locked value"]) and len(steps.calls) == len(clean_run.calls)
              and any(ln.startswith(ref) and "mx=0.0000(+nan)" in ln for ln in lines))
        code, failures, steps = gate_run(old, update=True)
        check(f"[relock rules] a relock refuses to replace a locked measure of {str(bad)[:8]!r} without --accept-drift",
              code == 1 and steps.written is None and has(failures, [f"{ref}: DRIFT mx: no locked value", "--accept-drift"]))
        code, failures, steps = gate_run(old, update=True, accept=True)
        check(f"[relock rules] a relock with --accept-drift replaces a locked measure of {str(bad)[:8]!r}",
              code == 0 and steps.written is not None and steps.written["models"][ref]["mx"] == 0.0)
    covered.add("relock rules")

    check("every check in regress.CHECKS has a test through run()", covered == set(regress.CHECKS))
    return locked


def test_command_line(locked):
    """What each flag asks of the run, and that main() passes it on."""
    plain = dict(scad=compare.SCAD, update=False, accept=False, alternate=False)
    check("no flag asks for a plain run of the generator", regress.options([]) == plain)
    check("--update-baseline asks for a relock only", regress.options(["--update-baseline"]) == dict(plain, update=True))
    check("--accept-drift alone accepts drift only", regress.options(["--accept-drift"]) == dict(plain, accept=True))
    check("--scad names another file and marks the run as alternate",
          regress.options(["--scad", str(OTHER_SCAD)]) == dict(plain, scad=OTHER_SCAD.resolve(), alternate=True))

    def main(*argv, **faults):
        steps, out = FakeSteps(locked, **faults), io.StringIO()
        with contextlib.redirect_stdout(out):
            code = regress.main(list(argv), steps=steps)
        return code, steps, out.getvalue()
    code, steps, said = main()
    check("main with no flag runs the gate on the generator and writes nothing",
          code == 0 and steps.written is None and ("digest", compare.SCAD) in steps.scads and "ALTERNATE" not in said)
    code, steps, said = main("--scad", str(OTHER_SCAD))
    check("main --scad runs the gate on that file and says so",
          ("digest", OTHER_SCAD.resolve()) in steps.scads and f"ALTERNATE SCAD: {OTHER_SCAD.name}" in said)
    code, steps, _ = main("--update-baseline")
    check("main --update-baseline relocks", code == 0 and steps.written is not None)
    code, steps, _ = main("--scad", str(OTHER_SCAD), "--update-baseline")
    check("main refuses a relock from another SCAD", code == 2 and steps.written is None)
    drift = dict(measure={REFERENCES[0]: dict(mx=(0.003, 0.0))})
    code, steps, _ = main("--update-baseline", **drift)
    check("main without --accept-drift refuses a relock over drift", code == 1 and steps.written is None)
    code, steps, _ = main("--update-baseline", "--accept-drift", **drift)
    check("main --accept-drift relocks over drift", code == 0 and steps.written is not None)
    code, steps, _ = main(**drift)
    check("main returns 1 when the run fails", code == 1 and steps.written is None)


def main():
    try:
        for test in (test_policy, test_decisions, test_console, test_measure, test_audit, test_3mf, test_render,
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
