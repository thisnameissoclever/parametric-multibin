"""Unit tests for the regression gate's decisions, run in seconds without
OpenSCAD: every limit is tested at its boundary, so a loosened or broken check
fails here even when the slow end-to-end self-test (selftest.py) would not
notice. The mesh checks run on small synthetic meshes written to
.local-build/out/shell/gate_test/.

Usage: python gate_test.py     (exits 1 if any test fails)
"""

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


def test_audit():
    a = compare.audit(stl("cube", cube()))
    check("a cube is sound", compare.clean(a) and a["bodies"] == 1)
    for field, bad in (("watertight", False), ("winding", False), ("volume", -1.0), ("bodies", 2),
                       ("bad_edges", 1), ("dup_faces", 1), ("crossing_depth", compare.CROSSING_LIMIT + 1e-9)):
        check(f"clean rejects {field} = {bad}", not compare.clean(dict(a, **{field: bad})))
    flipped = cube()
    faces = flipped.faces.copy()
    faces[0] = faces[0][::-1]
    check("a face wound the wrong way is caught",
          not compare.audit(stl("flipped", trimesh.Trimesh(flipped.vertices, faces, process=False)))["winding"])
    v = np.array([[0, 0, 10], [-5, -5, 0], [5, -5, 0], [5, 5, 0], [-5, 5, 0]], dtype=float)
    bow = trimesh.Trimesh(v, np.array([[0, 1, 3], [0, 3, 2], [0, 2, 4], [0, 4, 1], [1, 2, 3], [2, 1, 4]]),
                          process=False)
    with np.errstate(divide="ignore", invalid="ignore"):       # the bow-tie encloses no volume
        bow_audit = compare.audit(stl("bowtie", bow))
    check("faces crossing while sharing a vertex are caught", bow_audit["crossing_depth"] > compare.CROSSING_LIMIT)
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
    TMP.mkdir(parents=True, exist_ok=True)
    def model(coords):
        verts = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in coords)
        return f'<model><mesh><vertices>{verts}</vertices><triangles></triangles></mesh></model>'
    for name, coords, groups in (("apart", [(0, 0, 0), (1, 0, 0)], 0),
                                 ("together", [(0, 0, 0), (1, 0, 0), (0, 0, 0)], 1),
                                 ("signed zero", [("0.000000", 0, 0), ("-0.000000", 0, 0)], 1)):
        path = TMP / f"{name}.3mf"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("3D/3dmodel.model", model(coords))
        check(f"3MF coincident vertices counted ({name})", export_check.coincident_3mf(path) == groups)


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
        self.rejects = faults.get("rejects", True)

    def missing_refs(self):
        return list(self.missing)

    def generate(self, key, scad):
        return f"ref/{key}", 1.0, list(self.ref_messages.get(key, []))

    def measure(self, key, path):
        return dict(dict.fromkeys(regress.DRIFT, 0.0), **self.measure_over.get(key, {}))

    def audit(self, path):
        a = dict(watertight=True, winding=True, bodies=1, bad_edges=0, dup_faces=0, crossing_depth=0.0,
                 extents=[1.0, 1.0, 1.0], volume=1.0, digest=path)
        return dict(a, **self.audit_over.get(path, {}))

    def render(self, name, params, scad, expected, fmt="stl"):
        if any(name == r[0] for r in regress.REJECTED):
            return None, (expected[0] if self.rejects else ""), [], []
        return f"sound/{name}.{fmt}", "", list(self.sound_messages.get(name, [])),             [e for e in expected if not (fmt == self.unseen_fmt and e in self.unseen)]

    def coincident_3mf(self, path):
        return self.threemf

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
            ("coincident 3MF vertices", dict(threemf=2), "3MF has 2"),
            ("a size that is not rejected", dict(rejects=False), "rejected/")):
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
    for test in (test_limits, test_messages, test_measure, test_audit, test_3mf, test_soundness_and_coverage,
                 test_run):
        test()
    bad = [name for name, ok in results if not ok]
    for name, ok in results:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print(f"{len(results) - len(bad)} of {len(results)} gate tests passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
