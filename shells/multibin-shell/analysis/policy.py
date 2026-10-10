"""Every number and list the shell's gate decides by, in one place.

RULES would suit any part; SHELL is this part's own coverage. gate_test.py
compares both with a literal copy, so no value changes without a test changing.
docs/verification-method.md gives the reasons for the limits.
"""

# ------------------------------------------------------------------ rules

# Gate 1 limits: bounding box and distances in mm, volume in percent
LIMITS = dict(bbox=0.02, vol=0.5, p99=0.05, mx=0.2)
# how much worse than its locked value a reference metric may get
DRIFT = dict(bbox=0.002, vol=0.01, p99=0.002, mx=0.002)
# surface samples per direction for the sampled distances
N_SAMPLES = 50000
# volume change, in mm3, that a configuration without a reference may show with
# unchanged vertices: repeat renders agree to 0.001 mm3
SOUND_VOL = 0.01
# deepest crossing between two triangles a sound render may have, in mm: binary
# STL rounding stays under 0.0001 mm, and overlapping solids cross far deeper
CROSSING_LIMIT = 1e-3
# a crossing this close to a triangle's corner is a shared point, not a crossing
CORNER_TOL = 1e-7
# vertex merge distances for the 3MF check, in mm: 10 and 100 times the
# 0.000001 mm step of the coordinates OpenSCAD writes into a 3MF file
MERGE_TOLS = (1e-5, 1e-4)
# STL renders are binary, which keeps 32-bit coordinates. OpenSCAD's default
# ASCII STL keeps six significant digits, 0.001 mm beyond 100 mm from the origin
EXPORT_FORMAT = ("--export-format", "binstl")

RULES = dict(LIMITS=LIMITS, DRIFT=DRIFT, N_SAMPLES=N_SAMPLES, SOUND_VOL=SOUND_VOL,
             CROSSING_LIMIT=CROSSING_LIMIT, CORNER_TOL=CORNER_TOL, MERGE_TOLS=MERGE_TOLS,
             EXPORT_FORMAT=EXPORT_FORMAT)

# ------------------------------------------------------------------ shell coverage


def _walls(front, back, left, right):
    return dict(front_wall=f'"{front}"', back_wall=f'"{back}"', left_wall=f'"{left}"', right_wall=f'"{right}"')


# every reference shell the gate measures; refs.py maps a key to its file
REFERENCES = ("T111", "T212", "T313", "T3135", "T323", "T1215",
              "O111", "O212", "O323", "O1215",
              "S111", "S212", "S323", "S1215")

# configurations without a reference: (name, generator parameters)
SOUNDNESS = (
    ("half_w_1.5x1x1", dict(width_lu=1.5, height_lu=1, depth_lu=1)),
    ("half_h_2x1.5x2", dict(width_lu=2, height_lu=1.5, depth_lu=2)),
    ("half_both_2.5x1.5x1.5", dict(width_lu=2.5, height_lu=1.5, depth_lu=1.5)),
    ("thin_1.5x0.5x1", dict(width_lu=1.5, height_lu=0.5, depth_lu=1)),
    ("deep_1x1x4", dict(width_lu=1, height_lu=1, depth_lu=4)),
    ("tall_1x1x12", dict(width_lu=1, height_lu=1, depth_lu=12)),
    ("wide_4x1x1", dict(width_lu=4, height_lu=1, depth_lu=1)),
    # pads far from the origin: some positions once exported broken pocket slits
    ("long_1x7x1", dict(width_lu=1, height_lu=7, depth_lu=1)),
    ("wide_12x1x1", dict(width_lu=12, height_lu=1, depth_lu=1)),
    ("long_1x12x1", dict(width_lu=1, height_lu=12, depth_lu=1)),
    ("long_mixed_2.5x7.5x1.5", dict(width_lu=2.5, height_lu=7.5, depth_lu=1.5,
                                    **_walls("topped", "topped", "topless", "simple"))),
    ("mixed_walls_2x2x1", dict(width_lu=2, height_lu=2, depth_lu=1,
                               **_walls("topped", "topless", "simple", "topped"))),
    ("simple_2x1x2", dict(width_lu=2, height_lu=1, depth_lu=2, **_walls("simple", "simple", "simple", "simple"))),
    # rim grooves crossing seams beside a half cell, under a partial top band
    ("topless_half_2.5x1.5x1.5", dict(width_lu=2.5, height_lu=1.5, depth_lu=1.5,
                                      **_walls("topless", "topless", "topless", "topless"))),
    # the short partial-band seam groove of simple walls beside a half cell
    ("simple_half_1.5x2x2.5", dict(width_lu=1.5, height_lu=2, depth_lu=2.5,
                                   **_walls("simple", "simple", "simple", "simple"))),
)

# configurations also exported as 3MF, which keeps separate vertices apart by
# index. The two half-LU sizes cover the half pads; 4 x 1 x 1 has seam slots far
# enough from the origin for rounding to split faces placed from opposite wall faces
THREEMF_CHECK = ("thin_1.5x0.5x1", "half_both_2.5x1.5x1.5", "wide_4x1x1")

# sizes the sliders cannot produce: (name, parameters, the error that must stop the render)
REJECTED = (
    ("offstep_width_1.3", dict(width_lu=1.3), "width_lu must be a multiple of 0.5 from 1 to 12, not 1.3"),
    ("zero_height", dict(height_lu=0), "height_lu must be a multiple of 0.5 from 0.5 to 12, not 0"),
    ("deep_12.5", dict(depth_lu=12.5), "depth_lu must be a multiple of 0.5 from 1 to 12, not 12.5"),
)

# console texts a configuration must print, and may print without failing
EXPECTED_MESSAGES = {
    "thin_1.5x0.5x1": (
        "NOTE: left_wall = topped has no effect: the side is shorter than 1 LU, so it has no rail channel.",
        "NOTE: right_wall = topped has no effect: the side is shorter than 1 LU, so it has no rail channel."),
}

SHELL = dict(REFERENCES=REFERENCES, SOUNDNESS=SOUNDNESS, THREEMF_CHECK=THREEMF_CHECK, REJECTED=REJECTED,
             EXPECTED_MESSAGES=EXPECTED_MESSAGES)
