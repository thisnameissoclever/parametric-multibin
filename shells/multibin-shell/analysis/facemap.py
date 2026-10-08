"""Depth image of one wall face of a reference shell, for spotting features.

Usage: python facemap.py KEY FACE SIDE [step] [out.png] [lo hi]
KEY may also be a path to any STL file, for mapping a generated mesh.
FACE is one of -x +x -y +y (the wall's outward direction). SIDE is "out" to
look at the outer surface from outside, or "in" to look at the inner surface
from the cavity. Rays run parallel to the face normal on a grid with the given
step (default 0.1 mm). Brightness encodes how far the surface sits from the
nominal plane: the gray level is linear over the printed depth range.
Also prints the distinct depth levels with the area each covers.
"""

import struct
import sys
import zlib
from pathlib import Path

import numpy as np
import trimesh

from refs import STL_DIR, fname


def write_png(path, img):
    """8-bit grayscale PNG from a 2D uint8 array (row 0 at the top)."""
    h, w = img.shape
    raw = b"".join(b"\x00" + img[r].tobytes() for r in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def main():
    key, face, side = sys.argv[1], sys.argv[2], sys.argv[3]
    step = float(sys.argv[4]) if len(sys.argv) > 4 else 0.1
    out = sys.argv[5] if len(sys.argv) > 5 else f"{key}_{face}_{side}.png"
    mesh = trimesh.load_mesh(Path(key) if key.lower().endswith(".stl") else STL_DIR / fname(key))
    lo, hi = mesh.bounds
    ax = "xyz".index(face[1])
    sgn = 1 if face[0] == "+" else -1
    u_ax, v_ax = [a for a in range(3) if a != ax]   # v is z for side faces
    us = np.arange(lo[u_ax], hi[u_ax] + 1e-9, step)
    vs = np.arange(lo[v_ax], hi[v_ax] + 1e-9, step)
    U, V = np.meshgrid(us, vs)
    origins = np.zeros((U.size, 3))
    origins[:, u_ax] = U.ravel()
    origins[:, v_ax] = V.ravel()
    direction = np.zeros(3)
    if side == "out":
        origins[:, ax] = (hi[ax] + 5) if sgn > 0 else (lo[ax] - 5)
        direction[ax] = -sgn
    else:
        origins[:, ax] = (lo[ax] + hi[ax]) / 2
        direction[ax] = sgn
    dirs = np.tile(direction, (len(origins), 1))
    depth = np.full(len(origins), np.nan)
    chunk = 20000      # bounded batches: dense regions blow up the candidate pairs
    for s0 in range(0, len(origins), chunk):
        locs, idx, _ = mesh.ray.intersects_location(
            origins[s0:s0 + chunk], dirs[s0:s0 + chunk], multiple_hits=False)
        depth[s0 + idx] = locs[:, ax]
    depth = depth.reshape(U.shape)
    valid = depth[~np.isnan(depth)]
    levels, counts = np.unique(np.round(valid, 2), return_counts=True)
    print(f"[{key} {face} {side}] grid {U.shape[1]}x{U.shape[0]} step {step}; "
          f"{'xyz'[u_ax]} across, {'xyz'[v_ax]} up; hit surface coordinate along {'xyz'[ax]}:")
    for lv, c in sorted(zip(levels, counts), key=lambda t: -t[1])[:25]:
        print(f"   {'xyz'[ax]}={lv:8.2f}  area {c * step * step:9.2f} mm2")
    if len(sys.argv) > 7:
        d0, d1 = float(sys.argv[6]), float(sys.argv[7])   # clip the gray scale
    else:
        d0, d1 = np.nanmin(depth), np.nanmax(depth)
    img = np.zeros(depth.shape, dtype=np.uint8)
    ok = ~np.isnan(depth)
    img[ok] = (40 + 215 * np.clip((depth[ok] - d0) / max(1e-9, d1 - d0), 0, 1)).astype(np.uint8)
    write_png(out, img[::-1])          # put +v at the top
    print(f"wrote {out}  (black = no hit; gray {d0:.2f} .. white {d1:.2f})")


if __name__ == "__main__":
    main()
