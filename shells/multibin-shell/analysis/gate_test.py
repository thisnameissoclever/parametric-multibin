"""Unit tests for the shell's regression gate, run in seconds without OpenSCAD.

- The policy (every limit and list the gate decides by) is compared with a
  literal copy, so no value changes without this file changing.
- Every decision is tested at its boundary.
- The mesh tools run on small synthetic meshes written to
  .local-build/out/shell/gate_test/.
- The one render function runs against a stand-in for OpenSCAD.
- Every check in regress.CHECKS is driven through regress.run() with stand-in
  steps, and a clean run is checked to have rendered and examined everything
  the policy lists. The real steps are tested separately on small inputs.

Usage: python gate_test.py     (exits 1 if any test fails)
"""

import contextlib
import hashlib
import io
import json
import os
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
TMP = compare.OUT / "gate_test"
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
    check("the rules are the documented ones", policy.RULES == dict(
        LIMITS=dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2),
        DRIFT=dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002),
        N_SAMPLES=50000, SOUND_VOL=0.01, CROSSING_LIMIT=1e-3, CORNER_TOL=1e-7, MERGE_TOLS=(1e-5, 1e-4),
        EXPORT_FORMAT=("--export-format", "binstl")))
    check("the shell's coverage is the documented one", policy.SHELL == dict(
        REFERENCES=("T111", "T212", "T313", "T3135", "T323", "T1215", "O111", "O212", "O323", "O1215",
                    "S111", "S212", "S323", "S1215"),
        SOUNDNESS=(
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
            ("offstep_width_1.3", dict(width_lu=1.3), "width_lu must be a multiple of 0.5 from 1 to 12, not 1.3"),
            ("zero_height", dict(height_lu=0), "height_lu must be a multiple of 0.5 from 0.5 to 12, not 0"),
            ("deep_12.5", dict(depth_lu=12.5), "depth_lu must be a multiple of 0.5 from 1 to 12, not 12.5")),
        EXPECTED_MESSAGES={"thin_1.5x0.5x1": (
            "NOTE: left_wall = topped has no effect: the side is shorter than 1 LU, so it has no rail channel.",
            "NOTE: right_wall = topped has no effect: the side is shorter than 1 LU, so it has no rail channel.")}))
    check("every 3MF configuration is a listed configuration",
          set(THREEMF_CHECK) <= {n for n, _ in policy.SOUNDNESS})
    check("the reference list in refs.py is the policy's", refs.EXPECTED == list(REFERENCES))


def test_decisions():
    lim, drift, nan = policy.LIMITS, policy.DRIFT, float("nan")
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
    check("any other number of samples fails", regress.sample_failures("K", row(samples=policy.N_SAMPLES - 1)))
    zero = dict.fromkeys(drift, 0.0)
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
    check("a configuration absent from the baseline fails", regress.lock_failures("n", a, "absent"))
    check("relocking ignores the baseline", not regress.lock_failures("n", a, None))
    check("a crossing at the limit is sound", compare.clean(dict(a, crossing_depth=policy.CROSSING_LIMIT)))
    check("a crossing just over the limit is not", not compare.clean(dict(a, crossing_depth=policy.CROSSING_LIMIT + 1e-9)))
    check("a crossing depth that is not a number is not sound", not compare.clean(dict(a, crossing_depth=nan)))


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
                 "WARNING: Vertices: 3", "Simple: no", "Volumes: 3"]:
        check(f"'{line[:24]}' is a message", compare.render_problems(normal + line) == [line])
    check("an expected text is not a message", compare.render_problems('ECHO: "NOTE: a"', ["NOTE: a"]) == [])
    check("a message beside an expected text is still a message",
          compare.render_problems('WARNING: x\nECHO: "NOTE: a"', ["NOTE: a"]) == ["WARNING: x"])
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


def test_audit():
    a = compare.audit(stl("cube", cube()))
    check("a cube is sound", compare.clean(a) and a["bodies"] == 1)
    for field, bad in (("watertight", False), ("winding", False), ("volume", -1.0), ("bodies", 2),
                       ("bad_edges", 1), ("dup_faces", 1), ("crossing_depth", policy.CROSSING_LIMIT + 1e-9)):
        check(f"clean rejects {field} = {bad}", not compare.clean(dict(a, **{field: bad})))
        check(f"the failure names {field} = {bad}", len(compare.unsound_reasons(dict(a, **{field: bad}))) == 1)
    check("a sound mesh has no failure reasons", compare.unsound_reasons(a) == [])
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
    # an edge passing through a face 0.5 from its corner: a crossing; at the corner itself: a shared point
    for d, crosses in ((0.5, True), (policy.CORNER_TOL / 10, False)):
        p0, p1 = np.array([[d, d, -1.0]]), np.array([[d, d, 1.0]])
        hit = export_check.segment_crosses(p0, p1, face[None, 0], face[None, 1], face[None, 2])[0]
        check(f"an edge through a face {d:g} from its corner {'is' if crosses else 'is not'} a crossing", hit == crosses)
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
    near = fin(0.000005)
    check("3MF merge folds a fin into an edge with four triangles", export_check.merge_faults(near, 1e-5) == 1)
    check("3MF merge leaves vertices farther apart than the distance", export_check.merge_faults(near, 1e-6) == 0)


# ------------------------------------------------------------------ the render function and the real steps

def stub_render(out, write=True, console="", expected=(), stale=False, render=None):
    """Run compare.render (or the given render call) against the stand-in
    OpenSCAD; returns its result and the arguments the stand-in received."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if stale:
        out.write_text("left by an earlier run", encoding="utf-8")
    text = TMP / "stub_console.txt"
    text.write_text(console, encoding="utf-8")
    os.environ["STUB_WRITE"], os.environ["STUB_CONSOLE"] = ("1" if write else "0"), str(text)
    command = [sys.executable, str(HERE / "fixtures" / "stub_openscad.py")]
    try:
        if render is None:
            r = compare.render(command, "gen.scad", dict(width_lu=2, front_wall='"topped"'), out, expected)
        else:
            saved, compare.OPENSCAD_COMMAND = compare.OPENSCAD_COMMAND, command
            try:
                r = render()
            finally:
                compare.OPENSCAD_COMMAND = saved
    finally:
        del os.environ["STUB_WRITE"], os.environ["STUB_CONSOLE"]
    return r, json.loads(Path(str(out) + ".args.json").read_text(encoding="utf-8"))


def test_render():
    out = TMP / "render" / "a.stl"
    r, args = stub_render(out)
    check("a render that wrote its file returns the path", r["path"] == out and out.is_file())
    check("the render passes the output, the generator and every parameter",
          args == ["-o", str(out), "--export-format", "binstl", "gen.scad", "-D", "width_lu=2", "-D", 'front_wall="topped"'])
    r, args = stub_render(TMP / "render" / "a.3mf")
    check("a 3MF render does not ask for binary STL", "--export-format" not in args and r["path"] is not None)
    r, _ = stub_render(out, write=False, stale=True)
    check("a render that wrote no file returns no path", r["path"] is None)
    check("a file left by an earlier run is deleted before the render", not out.exists())
    r, _ = stub_render(out, console='WARNING: x\nECHO: "NOTE: a"\n', expected=["NOTE: a", "NOTE: b"])
    check("a render's messages beside its expected texts are reported", r["problems"] == ["WARNING: x"])
    check("only the expected texts that appeared count as seen", r["seen"] == ["NOTE: a"])
    check("the console text is returned", "WARNING: x" in r["console"])


def test_real_steps():
    """The real run's own steps, on small inputs: the stand-ins in FakeSteps
    cannot show that the real ones apply every check. Steps.unit_tests runs
    this file, so it cannot be tested from here."""
    steps = regress.Steps()
    scad = TMP / "other.scad"
    scad.write_bytes(b"cube(1);\r\n")
    target = compare.out_for(scad) / "soundness" / "a.stl"
    r, args = stub_render(target, console="WARNING: y\n", stale=True,
                          render=lambda: steps.render(scad, "soundness/a.stl", dict(width_lu=3), ()))
    check("the real render step writes under the generator's own output folder", r["path"] == target)
    check("the real render step renders STL in binary and reports messages",
          "binstl" in args and "width_lu=3" in args and r["problems"] == ["WARNING: y"])
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
          steps.digest(scad) == hashlib.sha256(b"cube(1);\n").hexdigest().upper())
    report = TMP / "VERIFICATION.md"
    report.write_text(regress.report_text([dict(row(key=k), seconds=12.0) for k in REFERENCES],
                                          "2026-01-01 00:00", "2026-01-01 00:30", "A" * 64, "OpenSCAD test"),
                      encoding="utf-8")
    text = report.read_text(encoding="utf-8")
    check("the report names the generator's digest where the gate reads it back", regress.report_digest(report) == "A" * 64)
    check("the report has a row for every reference", all(f"| {k} |" in text for k in REFERENCES))
    check("the report states the sample count and the limits",
          f"{policy.N_SAMPLES} points" in text and f"maxima <= {policy.LIMITS['mx']} mm" in text)
    check("a missing report has no digest", regress.report_digest(TMP / "no_such_report.md") is None)


# ------------------------------------------------------------------ the gate's run

class FakeSteps:
    """Stands in for OpenSCAD, the mesh tools and the files, so run() can be
    driven through each check in a fraction of a second. It records every call,
    so a test can see what a run rendered and examined."""

    def __init__(self, baseline=None, **faults):
        self.baseline, self.written, self.report, self.calls = baseline, None, None, []
        self.faults = faults
        self.digests = iter(faults.get("digests", []))

    def fault(self, kind, key, default):
        return self.faults.get(kind, {}).get(key, default)

    def unit_tests(self):
        return self.faults.get("unit_tests", True)

    def now(self):
        return "2026-01-01 00:00"

    def digest(self, scad):
        return next(self.digests, "D")

    def report_digest(self):
        return self.faults.get("report_digest", "D")

    def missing_refs(self):
        return list(self.faults.get("missing", []))

    def render(self, scad, name, params, expected):
        self.calls.append(("render", name))
        if name in self.faults.get("no_file", []):
            return dict(path=None, seconds=1.0, console="render failed", problems=[], seen=[])
        if any(name == f"soundness/{r[0]}.stl" for r in policy.REJECTED):
            return dict(path=name if self.faults.get("reject_writes") else None, seconds=0.1, console="",
                        problems=[], seen=list(expected) if self.faults.get("rejects", True) else [])
        return dict(path=name, seconds=1.0, console="", problems=list(self.fault("messages", name, [])),
                    seen=[e for e in expected if e not in self.fault("unseen", name, [])])

    def measure(self, key, path):
        self.calls.append(("measure", key))
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


def gate_run(baseline, **kw):
    faults = {k: kw.pop(k) for k in list(kw) if k not in ("update", "accept", "quick", "alternate")}
    steps = FakeSteps(baseline, **faults)
    code, failures = regress.run(steps, "fake.scad", log=lambda *a: None, **kw)
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
    fails("shape lock", "a changed vertex digest", f"soundness/{CONF}: geometry changed vs baseline",
          audit={CONF_STL: dict(digest="x")})
    fails("shape lock", "a changed volume with the same vertices", f"soundness/{CONF}: geometry changed vs baseline",
          audit={CONF_STL: dict(volume=1.0 + policy.SOUND_VOL + 1e-6)})

    fails("3MF coincident vertices", "coincident 3MF vertices", "3MF has 2 group(s)", coincident=2)
    for tol, text in ((1e-5, "3MF merged within 1e-05 mm leaves 2 edge(s)"),
                      (1e-4, "3MF merged within 0.0001 mm leaves 2 edge(s)")):
        fails("3MF merges", f"a 3MF that a merge within {tol:g} mm folds", text, merged={tol: 2})
    fails("rejected sizes", "a size that is not rejected", "rejected/zero_height: expected the render to stop",
          rejects=False)
    fails("rejected sizes", "a rejected size that still writes a file", "rejected/deep_12.5: expected the render to stop",
          reject_writes=True)

    # a clean run renders and examines everything the policy lists
    stls = ([f"{k}.stl" for k in REFERENCES] + [f"soundness/{n}.stl" for n, _ in policy.SOUNDNESS])
    tmfs = [f"soundness/{n}.3mf" for n in THREEMF_CHECK]
    done = lambda kind: sorted(c[1] for c in clean_run.calls if c[0] == kind)     # noqa: E731
    check("a clean run renders every reference, configuration, 3MF export and rejected size",
          done("render") == sorted(stls + tmfs + [f"soundness/{r[0]}.stl" for r in policy.REJECTED]))
    check("a clean run measures every reference", done("measure") == sorted(REFERENCES))
    check("a clean run audits every STL it rendered", done("audit") == sorted(stls))
    check("a clean run checks every 3MF export both ways",
          done("coincident_3mf") == sorted(tmfs) and done("merge_faults") == sorted(tmfs))
    code, _, quick_run = gate_run(locked, quick=True)
    check("--quick renders only the references",
          code == 0 and sorted(c[1] for c in quick_run.calls if c[0] == "render") == sorted(f"{k}.stl" for k in REFERENCES))

    # relock rules
    check("[relock rules] a relock records the generator's digest and writes the report naming it",
          locked.get("scad_digest") == "D" and first.report and "SHA-256 D," in first.report)
    check("[relock rules] a plain run writes neither the baseline nor the report",
          clean_run.written is None and clean_run.report is None)
    check("[relock rules] a relock without the configurations is refused", gate_run(locked, update=True, quick=True)[0] == 2)
    check("[relock rules] a relock from another SCAD is refused", gate_run(locked, update=True, alternate=True)[0] == 2)
    check("[relock rules] a run without a baseline stops", gate_run(None)[0] == 2)
    drift = dict(measure={REF: dict(mx=(0.003, 0.0))})
    code, failures, steps = gate_run(locked, update=True, **drift)
    check("[relock rules] a relock refuses drift without --accept-drift",
          code == 1 and steps.written is None and steps.report is None and has(failures, "--accept-drift"))
    code, failures, steps = gate_run(locked, update=True, accept=True, **drift)
    check("[relock rules] a relock with --accept-drift writes the baseline", code == 0 and steps.written is not None)
    code, failures, steps = gate_run(locked, update=True, audit={CONF_STL: dict(digest="x")})
    check("[relock rules] a relock refuses a changed shape without --accept-drift",
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


def main():
    for test in (test_policy, test_decisions, test_messages, test_measure, test_audit, test_3mf, test_render,
                 test_real_steps, test_checks):
        test()
    bad = [name for name, ok in results if not ok]
    for name, ok in results:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print(f"{len(results) - len(bad)} of {len(results)} gate tests passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
