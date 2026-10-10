"""Unit tests for the regression gate's decisions, run in seconds without
OpenSCAD: every limit is tested at its boundary, so a loosened or broken check
fails here even when the slow end-to-end self-test (selftest.py) would not
notice. The mesh checks run on small synthetic meshes written to
.local-build/out/shell/gate_test/.

Usage: python gate_test.py     (exits 1 if any test fails)
"""

import contextlib
import io
import sys
import zipfile

import numpy as np
import trimesh

import compare
import export_check
import regress
from refs import EXPECTED

TMP = compare.OUT / "gate_test"
results = []


def check(name, condition):
    results.append((name, bool(condition)))


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


def row(bbox=0.0, vol=0.0, p99=(0.0, 0.0), mx=(0.0, 0.0), vmax=(0.0, 0.0), key="K"):
    """A compare.measure row with chosen values, for the gate's decisions."""
    return dict(key=key, bbox=bbox, vol=vol,
                **{tag: dict(mean=0.0, p95=0.0, p99=p99[i], mx=mx[i], vmax=vmax[i])
                   for i, tag in enumerate(("ref->gen", "gen->ref"))})


def test_limits():
    check("HARD limits are the Gate 1 limits", regress.HARD == dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2))
    check("regress and compare share one copy of the limits", regress.HARD is compare.LIMITS)
    check("DRIFT tolerances", regress.DRIFT == dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002))
    check("crossing limit", compare.CROSSING_LIMIT == 1e-3)
    check("renders are exported as binary STL", compare.EXPORT_FORMAT == ["--export-format", "binstl"])
    for field, limit in regress.HARD.items():
        at = dict(regress.HARD)
        over = dict(regress.HARD, **{field: limit + 1e-9})
        check(f"HARD {field} at the limit passes", not regress.hard_failures("K", at))
        check(f"HARD {field} just over the limit fails", regress.hard_failures("K", over))
    s = compare.summary(row(p99=(0.01, 0.03), mx=(0.02, 0.01), vmax=(0.04, 0.05)))
    check("summary takes p99 from the worse direction", s["p99"] == 0.03)
    check("summary takes the maximum over samples and vertices, both directions", s["mx"] == 0.05)
    lim = compare.LIMITS
    at = row(bbox=lim["bbox"], vol=lim["vol"], p99=(lim["p99"],) * 2, mx=(lim["mx"],) * 2, vmax=(lim["mx"],) * 2)
    check("report gate passes at every limit", compare.gate(at, {"K": []}, {"K": True}) == "PASS")
    for field, kw in (("bbox", dict(bbox=lim["bbox"] + 1e-9)), ("vol", dict(vol=lim["vol"] + 1e-9)),
                      ("p99", dict(p99=(0.0, lim["p99"] + 1e-9))), ("mx", dict(mx=(lim["mx"] + 1e-9, 0.0))),
                      ("vertex max", dict(vmax=(0.0, lim["mx"] + 1e-9)))):
        check(f"report gate fails just over the {field} limit", compare.gate(row(**kw), {"K": []}, {"K": True}) == "FAIL")
    check("report gate fails an unsound render", compare.gate(row(), {"K": []}, {"K": False}) == "FAIL")
    nan = float("nan")
    check("report gate fails a NaN measurement, wherever it falls",
          compare.gate(row(vmax=(0.0, nan)), {"K": []}, {"K": True}) == "FAIL"
          and compare.gate(row(p99=(0.0, nan)), {"K": []}, {"K": True}) == "FAIL")
    check("HARD fails a NaN metric", regress.hard_failures("K", dict(regress.HARD, mx=nan)))
    check("DRIFT fails a NaN metric",
          regress.drift_failures("K", dict.fromkeys(regress.DRIFT, nan), dict.fromkeys(regress.DRIFT, 0.0)))
    check("report gate fails a render message", compare.gate(row(), {"K": ["WARNING: x"]}, {"K": True}) == "FAIL")
    zero = dict.fromkeys(regress.DRIFT, 0.0)
    for field, tol in regress.DRIFT.items():
        check(f"DRIFT {field} at the tolerance passes", not regress.drift_failures("K", dict(zero, **{field: tol}), zero))
        check(f"DRIFT {field} just over fails", regress.drift_failures("K", dict(zero, **{field: tol + 1e-9}), zero))
        check(f"DRIFT {field} improvement passes", not regress.drift_failures("K", zero, dict(zero, **{field: 1.0})))


def test_messages():
    normal = "\n".join(["Geometries in cache: 315", "Geometry cache size in bytes: 511888",
                        "CGAL Polyhedrons in cache: 152", "CGAL cache size in bytes: 73485696",
                        "Total rendering time: 0:00:22.030", "   Top level object is a 3D object:",
                        "   Simple:        yes", "   Vertices:     6372", "   Halfedges:   20758",
                        "   Edges:       10379", "   Halffacets:   8156", "   Facets:       4078",
                        "   Volumes:         2", ""])
    check("normal OpenSCAD output is no message", compare.render_problems(normal) == [])
    for line in ["WARNING: x", "ERROR: x", "DEPRECATED: x", 'ECHO: "x"', "TRACE: x",
                 "PolySet has nonplanar faces. Attempting alternate construction", "anything else"]:
        check(f"'{line[:20]}' is a message", compare.render_problems(normal + line) == [line])
    check("an expected text is not a message", compare.render_problems('ECHO: "NOTE: a"', ["NOTE: a"]) == [])
    check("a message beside an expected text is still a message",
          compare.render_problems('WARNING: x\nECHO: "NOTE: a"', ["NOTE: a"]) == ["WARNING: x"])
    out, _, problems, seen = regress.render_result(TMP / "never_written.stl", 'WARNING: x\nECHO: "NOTE: a"',
                                                   ["NOTE: a", "NOTE: b"])
    check("a render that wrote no file returns no path", out is None)
    check("a render's messages beside its expected texts are reported", problems == ["WARNING: x"])
    check("only the expected texts that appeared count as seen", seen == ["NOTE: a"])
    written = stl("written", cube())
    check("a render that wrote its file returns the path", regress.render_result(written, "", [])[0] == written)
    check("a render that is not simple is a message", compare.render_problems("Simple: no") == ["Simple: no"])
    check("more than one solid is a message", compare.render_problems("Volumes: 3") == ["Volumes: 3"])
    check("an unexpected message fails", regress.message_failures("K", ["WARNING: x"], [], []))
    check("a missing expected message fails", regress.message_failures("K", [], ["NOTE: a"], []))
    check("an expected message seen passes", not regress.message_failures("K", [], ["NOTE: a"], ["NOTE: a"]))


def test_measure():
    m = cube()
    r, _ = compare.measure(m, m.copy(), n_samples=2000)
    check("identical meshes measure zero", max(compare.summary(r).values()) < 1e-9)
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
                       ("bad_edges", 1), ("dup_faces", 1), ("crossing_depth", compare.CROSSING_LIMIT + 1e-9)):
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
    check("faces crossing while sharing a vertex are caught", bow_audit["crossing_depth"] > compare.CROSSING_LIMIT)
    face = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0]], dtype=float)
    needle = np.array([[2, 2, -1], [2, 2, 1], [2, 2, 0.5]], dtype=float)   # a flat sliver through the face
    check("a zero-area triangle piercing a face is measured",
          export_check.pair_depth(face, needle) >= 1.0 - 1e-9 and export_check.pair_depth(needle, face) >= 1.0 - 1e-9)
    check("two cubes touching at one vertex are two bodies",
          compare.audit(stl("touch", joined(cube(), cube((10, 10, 10)))))["bodies"] == 2)
    check("two separate cubes are not sound", not compare.clean(compare.audit(stl("apart", joined(cube(), cube((20, 0, 0)))))))
    cross = compare.audit(stl("cross", joined(cube(), cube((3, 3, 3)))))
    check("crossing cubes exceed the crossing limit", cross["crossing_depth"] > compare.CROSSING_LIMIT
          and not compare.clean(cross))
    m = cube()
    check("a cube missing a face is not watertight",
          not compare.audit(stl("open", trimesh.Trimesh(m.vertices, m.faces[1:], process=False)))["watertight"])
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
    check("3MF merge distances are 0.00001 and 0.0001 mm", export_check.MERGE_TOLS == (1e-5, 1e-4))


def test_real_steps():
    """The real run's own steps, on small files: the stand-ins in FakeSteps
    cannot show that the real ones apply every check."""
    steps = regress.Steps()
    with np.errstate(divide="ignore", invalid="ignore"):
        check("the real audit measures crossings", steps.audit(bowtie())["crossing_depth"] > compare.CROSSING_LIMIT)
    check("the real audit passes a sound mesh", compare.clean(steps.audit(stl("cube", cube()))))
    check("the real 3MF step counts coincident vertices",
          steps.coincident_3mf(threemf("together", model([(0, 0, 0), (1, 0, 0), (0, 0, 0)]))) == 1)
    check("the real merge step applies both distances", steps.merge_faults(fin(0.00005)) == {1e-5: 0, 1e-4: 1})
    check("the real merge step finds a fin at either distance", steps.merge_faults(fin(0.000005)) == {1e-5: 1, 1e-4: 1})
    # the real measuring and coverage steps, with the reference folder pointed
    # at a synthetic reference for the first key
    refs = TMP / "refs"
    refs.mkdir(parents=True, exist_ok=True)
    cube().export(refs / regress.fname(EXPECTED[0]))
    saved = compare.STL_DIR, regress.STL_DIR
    compare.STL_DIR = regress.STL_DIR = refs
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            m = steps.measure(EXPECTED[0], stl("scaled", cube().apply_scale(1.01)))
        missing = steps.missing_refs()
    finally:
        compare.STL_DIR, regress.STL_DIR = saved
    check("the real measure step measures volume", abs(m["vol"] - (1.01 ** 3 - 1) * 100) < 1e-3)   # STL keeps 32-bit floats
    check("the real measure step measures the bounding box", abs(m["bbox"] - 0.1) < 1e-6)
    check("the real measure step measures the maximum", m["mx"] > 0.04)
    check("the real coverage step finds missing references", missing == EXPECTED[1:])
    scad = TMP / "digest.scad"
    scad.write_bytes(b"cube(1);\r\n")
    check("the generator digest ignores line endings", steps.digest(scad) == compare.scad_digest(TMP / "digest.scad")
          and steps.digest(scad) == __import__("hashlib").sha256(b"cube(1);\n").hexdigest().upper())
    check("the report refuses when the generator changed during its run",
          compare.report_refusal([], len(EXPECTED), "A", "B") == "the generator changed during the run")
    check("the report refuses a missing reference", compare.report_refusal(["K"], len(EXPECTED), "A", "A"))
    check("the report refuses a failed render", compare.report_refusal([], len(EXPECTED) - 1, "A", "A"))
    check("the report is written when nothing is wrong", compare.report_refusal([], len(EXPECTED), "A", "A") is None)


class FakeSteps:
    """Stands in for OpenSCAD, the meshes and the baseline file, so run() can be
    driven through each kind of failure in a fraction of a second."""

    def __init__(self, baseline=None, **faults):
        self.baseline, self.written = baseline, None
        self.missing = faults.get("missing", [])
        self.ref_messages = faults.get("ref_messages", {})
        self.measure_over = faults.get("measure_over", {})
        self.audit_over = faults.get("audit_over", {})
        self.sound_messages = faults.get("sound_messages", {})
        self.unseen = faults.get("unseen", [])
        self.unseen_fmt = faults.get("unseen_fmt", "stl")
        self.threemf = faults.get("threemf", 0)
        self.merged = faults.get("merged", {})
        self.rejects = faults.get("rejects", True)
        self.reject_writes = faults.get("reject_writes", False)
        self.fail_refs = faults.get("fail_refs", [])
        self.fail_renders = faults.get("fail_renders", [])
        self.sound_messages_fmt = faults.get("sound_messages_fmt")
        self.digests = iter(faults.get("digests", []))

    def missing_refs(self):
        return list(self.missing)

    def generate(self, key, scad):
        return (None if key in self.fail_refs else f"ref/{key}"), 1.0, list(self.ref_messages.get(key, []))

    def measure(self, key, path):
        return dict(dict.fromkeys(regress.DRIFT, 0.0), **self.measure_over.get(key, {}))

    def audit(self, path):
        a = dict(watertight=True, winding=True, bodies=1, bad_edges=0, dup_faces=0, crossing_depth=0.0,
                 extents=[1.0, 1.0, 1.0], volume=1.0, digest=path)
        return dict(a, **self.audit_over.get(path, {}))

    def render(self, name, params, scad, expected, fmt="stl"):
        if any(name == r[0] for r in regress.REJECTED):
            out = f"sound/{name}.{fmt}" if self.reject_writes else None
            return out, (expected[0] if self.rejects else ""), [], []
        if (name, fmt) in self.fail_renders:
            return None, "render failed", [], []
        messages = self.sound_messages.get(name, []) if self.sound_messages_fmt in (None, fmt) else []
        return f"sound/{name}.{fmt}", "", list(messages),             [e for e in expected if not (fmt == self.unseen_fmt and e in self.unseen)]

    def coincident_3mf(self, path):
        return self.threemf

    def digest(self, scad):
        return next(self.digests, "D")

    def merge_faults(self, path):
        return {tol: self.merged.get(tol, 0) for tol in regress.MERGE_TOLS}

    def load_baseline(self):
        return self.baseline

    def write_baseline(self, data):
        self.written = data


def gate_run(baseline, quiet=True, **kw):
    faults = {k: kw.pop(k) for k in list(kw) if k not in ("update", "accept", "quick", "alternate")}
    steps = FakeSteps(baseline, **faults)
    code, failures = regress.run(steps, "fake.scad", log=(lambda *a: None) if quiet else print, **kw)
    return code, failures, steps.written


def has(failures, text):
    return any(text in f for f in failures)


def test_run():
    code, failures, locked = gate_run(None, update=True)
    check("a relock records the generator's digest", locked is not None and locked.get("scad_digest") == "D")
    check("a clean relock writes the baseline", code == 0 and locked is not None
          and len(locked["models"]) == len(EXPECTED) and len(locked["soundness"]) == len(regress.SOUNDNESS))
    code, failures, _ = gate_run(locked)
    check("a clean run passes", code == 0 and not failures)
    note = regress.EXPECTED_MESSAGES["thin_1.5x0.5x1"][0]
    for label, kw, text in (
            ("a missing reference", dict(missing=[EXPECTED[0]]), "reference file missing"),
            ("an unsound reference", dict(audit_over={f"ref/{EXPECTED[0]}": dict(watertight=False)}),
             "mesh not a clean single shell"),
            ("a reference render message", dict(ref_messages={EXPECTED[0]: ["WARNING: x"]}), "render message"),
            ("a reference over a HARD limit", dict(measure_over={EXPECTED[0]: dict(mx=0.3)}), "HARD mx"),
            ("reference drift", dict(measure_over={EXPECTED[0]: dict(mx=0.003)}), "DRIFT mx"),
            ("a missing expected note", dict(unseen=[note]), "expected render message missing"),
            ("a missing expected note in the 3MF export", dict(unseen=[note], unseen_fmt="3mf"),
             "3MF: expected render message missing"),
            ("an unexpected soundness message", dict(sound_messages={"half_w_1.5x1x1": ["ECHO: x"]}), "render message"),
            ("a changed shape", dict(audit_over={"sound/half_w_1.5x1x1.stl": dict(digest="x")}), "geometry changed"),
            ("an unsound configuration", dict(audit_over={"sound/half_w_1.5x1x1.stl": dict(bodies=2)}),
             "mesh not a clean single shell"),
            ("crossing triangles in a reference", dict(audit_over={f"ref/{EXPECTED[0]}": dict(crossing_depth=0.01)}),
             f"{EXPECTED[0]}: mesh not a clean single shell: triangles crossing 0.01 mm deep"),
            ("coincident 3MF vertices", dict(threemf=2), "3MF has 2"),
            ("a render message in a 3MF export only",
             dict(sound_messages={regress.THREEMF_CHECK[0]: ["WARNING: x"]}, sound_messages_fmt="3mf"),
             f"soundness/{regress.THREEMF_CHECK[0]} 3MF: render message: WARNING: x"),
            ("a generator changed during the run", dict(digests=["A", "B"]), "generator changed during the run"),
            ("a 3MF that a merge within 0.00001 mm folds", dict(merged={1e-5: 2}),
             "3MF merged within 1e-05 mm leaves 2 edge(s)"),
            ("a 3MF that a merge within 0.0001 mm folds", dict(merged={1e-4: 3}),
             "3MF merged within 0.0001 mm leaves 3 edge(s)"),
            ("a size that is not rejected", dict(rejects=False), "rejected/"),
            ("a rejected size that still writes a file", dict(reject_writes=True), "rejected/"),
            ("a failed reference render", dict(fail_refs=[EXPECTED[0]]), f"{EXPECTED[0]}: render failed"),
            ("a failed soundness render", dict(fail_renders=[("half_w_1.5x1x1", "stl")]),
             "soundness/half_w_1.5x1x1: render failed"),
            ("a failed 3MF render", dict(fail_renders=[(regress.THREEMF_CHECK[0], "3mf")]), "3MF render failed")):
        code, failures, _ = gate_run(locked, **kw)
        check(f"a run fails on {label}", code == 1 and has(failures, text))
    dropped = dict(locked, soundness=dict(locked["soundness"], extra_config={}))
    code, failures, _ = gate_run(dropped)
    check("a run fails when a locked configuration is no longer checked", code == 1 and has(failures, "no longer checked"))
    drift = dict(measure_over={EXPECTED[0]: dict(mx=0.003)})
    code, failures, written = gate_run(locked, update=True, **drift)
    check("a relock refuses drift without --accept-drift", code == 1 and written is None
          and has(failures, "--accept-drift"))
    code, failures, written = gate_run(locked, update=True, accept=True, **drift)
    check("a relock with --accept-drift writes the baseline", code == 0 and written is not None)
    code, failures, written = gate_run(locked, update=True, accept=True,
                                       audit_over={f"ref/{EXPECTED[0]}": dict(watertight=False)})
    check("a relock never writes over a failure", code == 1 and written is None)
    smaller = dict(locked, soundness=dict(locked["soundness"], extra_config={}))
    code, failures, written = gate_run(smaller, update=True)
    check("a relock refuses to drop a locked configuration without --accept-drift",
          code == 1 and written is None and has(failures, "locked configuration no longer checked"))
    dropped = dict(locked, models=dict(locked["models"], EXTRA_REF=locked["models"][EXPECTED[0]]))
    code, failures, written = gate_run(dropped, update=True)
    check("a relock refuses to drop a locked reference without --accept-drift",
          code == 1 and written is None and has(failures, "EXTRA_REF: locked reference no longer measured"))
    check("the gate rejects all three sizes the sliders cannot produce",
          [r[0] for r in regress.REJECTED] == ["offstep_width_1.3", "zero_height", "deep_12.5"])
    check("the 3MF check covers both half-LU sizes and the 4 x 1 x 1 seams",
          regress.THREEMF_CHECK == ["thin_1.5x0.5x1", "half_both_2.5x1.5x1.5", "wide_4x1x1"])
    check("a relock without the soundness section is refused", gate_run(locked, update=True, quick=True)[0] == 2)
    check("a relock from another SCAD is refused", gate_run(locked, update=True, alternate=True)[0] == 2)
    check("a run without a baseline stops", gate_run(None)[0] == 2)


def test_soundness_and_coverage():
    a = compare.audit(stl("cube", cube()))
    check("unchanged digest passes", not regress.sound_failures("n", a, dict(a)))
    check("changed digest fails", regress.sound_failures("n", a, dict(a, digest="0")))
    check("a configuration absent from the baseline fails", regress.sound_failures("n", a, "absent"))
    check("relocking ignores the baseline", not regress.sound_failures("n", a, None))
    check("a volume change with the same vertices fails",
          regress.sound_failures("n", a, dict(a, volume=a["volume"] + regress.SOUND_VOL + 1e-6)))
    check("a volume change within the tolerance passes",
          not regress.sound_failures("n", a, dict(a, volume=a["volume"] + regress.SOUND_VOL)))
    m0 = dict.fromkeys(regress.DRIFT, 0.0)
    old = dict(models={"K": m0}, soundness={"n": dict(a)})
    check("a relock with nothing changed lists nothing", not regress.relock_changes({"K": m0}, {"n": a}, old))
    check("a relock lists reference drift",
          regress.relock_changes({"K": dict(m0, mx=regress.DRIFT["mx"] + 1e-6)}, {"n": a}, old))
    check("a relock lists a changed shape", regress.relock_changes({"K": m0}, {"n": dict(a, digest="0")}, old))
    check("an unsound configuration fails even when relocking", regress.sound_failures("n", dict(a, bodies=2), None))
    full = dict(models=dict.fromkeys(EXPECTED, {}), soundness={"s": {}})
    check("full coverage passes", not regress.coverage_failures([], full, False, False, ["s"]))
    check("a missing reference fails", regress.coverage_failures([EXPECTED[0]], full, False, False, ["s"]))
    check("a missing reference fails when relocking", regress.coverage_failures([EXPECTED[0]], {}, True, False, []))
    extra = dict(full, models=dict(full["models"], X999={}))
    check("a baseline reference outside refs.EXPECTED fails", regress.coverage_failures([], extra, False, False, ["s"]))
    short = dict(full, models={k: {} for k in EXPECTED[1:]})
    check("an expected reference absent from the baseline fails", regress.coverage_failures([], short, False, False, ["s"]))
    check("a dropped soundness configuration fails", regress.coverage_failures([], full, False, False, []))
    check("--quick skips the soundness coverage check", not regress.coverage_failures([], full, False, True, []))


def main():
    for test in (test_limits, test_messages, test_measure, test_audit, test_3mf, test_real_steps,
                 test_soundness_and_coverage, test_run):
        test()
    bad = [name for name, ok in results if not ok]
    for name, ok in results:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print(f"{len(results) - len(bad)} of {len(results)} gate tests passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
