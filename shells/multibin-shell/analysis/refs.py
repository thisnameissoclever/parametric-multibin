"""Reference shells and shared helpers for the shell analysis scripts.

Keys are <wall letter><X><Y><Z> in LU, using MultiBuild's file naming:
X is width, Y is front-to-back depth on the build plate, Z is height in the
print orientation (base to opening). T = Topped Rail, O = Topless Rail,
S = Simple. A drawer named WxHxD fits the shell with the same three numbers.
"""

import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import mbpaths  # noqa: E402

STL_DIR = mbpaths.refs("shell")

WALLS = {"T": "Topped Rail", "O": "Topless Rail", "S": "Simple Walls"}

# key -> (x, y, z) in LU
SIZES = {
    "111": (1, 1, 1), "212": (2, 1, 2), "313": (3, 1, 3), "3135": (3, 1, 3.5),
    "323": (3, 2, 3), "1215": (1, 2, 1.5),
}


def fname(key):
    wall, size = key[0], key[1:]
    x, y, z = SIZES[size]
    # MultiBuild names the Simple Walls files differently: "CU" and "Multibin"
    if wall == "S":
        return f"{x:g}x{y:g}x{z:g} CU - {WALLS[wall]} - Multibin Shell.stl"
    return f"{x:g}x{y:g}x{z:g} LU - {WALLS[wall]} - MultiBin Shell.stl"


def available():
    return [w + s for w in WALLS for s in SIZES if (STL_DIR / fname(w + s)).is_file()]


def load_tris(key):
    """Triangles as an (n, 3, 3) float64 array, read straight from the STL."""
    data = (STL_DIR / fname(key)).read_bytes()
    if data[:5].lower() == b"solid" and b"facet" in data[:1000]:
        verts = [[float(v) for v in ln.split()[1:4]]
                 for ln in data.decode(errors="ignore").splitlines()
                 if ln.strip().startswith("vertex")]
        return np.array(verts, dtype=np.float64).reshape(-1, 3, 3)
    n = struct.unpack_from("<I", data, 80)[0]
    rec = np.frombuffer(data, dtype=np.uint8, count=n * 50, offset=84).reshape(n, 50)
    return rec[:, :48].copy().view("<f4").reshape(n, 4, 3)[:, 1:4, :].astype(np.float64)


def normals_areas(tris):
    cr = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    a2 = np.linalg.norm(cr, axis=1)
    n = np.zeros_like(cr)
    ok = a2 > 1e-12
    n[ok] = cr[ok] / a2[ok][:, None]
    return n, a2 / 2


if __name__ == "__main__":
    for k in available():
        print(k, fname(k))
