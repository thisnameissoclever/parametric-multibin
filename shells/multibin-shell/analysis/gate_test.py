"""Unit tests for the regression gate's decisions, run in seconds without
OpenSCAD: every limit is tested at its boundary, so a loosened or broken check
fails here even when the slow end-to-end self-test (selftest.py) would not
notice. The mesh checks run on small synthetic meshes written to
.local-build/out/shell/gate_test/.

Usage: python gate_test.py     (exits 1 if any test fails)
"""

import sys

import numpy as np
import trimesh

import compare
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


def test_limits():
    check("HARD limits are the Gate 1 limits", regress.HARD == dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2))
    check("DRIFT tolerances", regress.DRIFT == dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002))
    check("crossing limit", compare.CROSSING_LIMIT == 1e-3)
    check("renders are exported as binary STL", compare.EXPORT_FORMAT == ["--export-format", "binstl"])
    for field, limit in regress.HARD.items():
        at = dict(regress.HARD)
        over = dict(regress.HARD, **{field: limit + 1e-9})
        check(f"HARD {field} at the limit passes", not regress.hard_failures("K", at))
        check(f"HARD {field} just over the limit fails", regress.hard_failures("K", over))
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


def test_audit():
    a = compare.audit(stl("cube", cube()))
    check("a cube is sound", compare.clean(a) and a["bodies"] == 1)
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
    moved = m.vertices.copy()
    moved[0, 0] += 1e-4
    check("digest changes when a vertex moves 0.0001 mm",
          compare.audit(stl("moved", trimesh.Trimesh(moved, m.faces, process=False)))["digest"] != d0)


def test_soundness_and_coverage():
    a = compare.audit(stl("cube", cube()))
    check("unchanged digest passes", not regress.sound_failures("n", a, dict(a)))
    check("changed digest fails", regress.sound_failures("n", a, dict(a, digest="0")))
    check("a configuration absent from the baseline fails", regress.sound_failures("n", a, "absent"))
    check("relocking ignores the baseline", not regress.sound_failures("n", a, None))
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
    for test in (test_limits, test_messages, test_audit, test_soundness_and_coverage):
        test()
    bad = [name for name, ok in results if not ok]
    for name, ok in results:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    print(f"{len(results) - len(bad)} of {len(results)} gate tests passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
