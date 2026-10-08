// MultiBin Shell - parametric remake
// Rebuilds MultiBoard's MultiBin shells (Standard Base) from measurements, so
// matching sizes reproduce the published shells and every other size follows
// the same rules. Paste this whole file into MakerWorld's Parametric Model Maker.
//
// Print orientation: the base is on the build plate and the opening is on top.
// X = width, Y = front to back on the plate, Z = up. The first 50 mm cell is
// centred on the origin. A drawer made with the same three numbers fits inside:
// the drawer's height runs along Y and its depth along Z.

/* [Size (LU, the same numbers as the drawer that goes inside)] */
// Width in LU (X)
width_lu = 2; // [1:0.5:12]
// Drawer height in LU: the shell's front-to-back size on the build plate (Y)
height_lu = 1; // [0.5:0.5:12]
// Drawer depth in LU: the shell's height as printed, base to opening (Z)
depth_lu = 2; // [1:0.5:12]

/* [Walls (front faces the front of the build plate)] */
front_wall = "topped"; // [topped, topless, simple]
back_wall = "topped"; // [topped, topless, simple]
left_wall = "topped"; // [topped, topless, simple]
right_wall = "topped"; // [topped, topless, simple]

/* [Hidden] */
$fs = 0.25;
$fa = 2;
eps = 0.01;

U  = 50;
NX = max(1, width_lu);
NY = max(0.5, height_lu);
NZ = max(1, depth_lu);

X0 = -U/2;  X1 = U*NX - U/2;     // outer faces
Y0 = -U/2;  Y1 = U*NY - U/2;
ZT = U*NZ + 5;                   // rim height

wall    = 3.0;                   // outer face to inner face at the pillars
c_out   = 8.737;                 // outer vertical corner chamfer leg
c_in    = 5.565;                 // inner vertical corner chamfer leg
floor_z = 6.0;                   // top of the floor
foot_z  = 6.8;                   // outer face meets the 45-degree foot chamfer
pad_in  = 3.2;                   // base pad inset from the cell edge
pad_top = 3.6;                   // pad's vertical side ends here
pad_c   = 5.448;                 // pad corner chamfer leg
bridge_z = 5.4;                  // underside of the floor between pads, beside their flat sides
bridge_lo = 5.2;                 // ... and beside their corner chamfers
foot_c  = 5.8;                   // corner faces meet their outer plane here
corner_in = 2.2;                 // pad corner face inset from the outer corner face

// channel (dovetail rail slot), in face coordinates: t along the face,
// n into the wall from the outer face
ch_open  = 7.0;                  // half width at the face
ch_lip   = 0.4;                  // straight lip before the dovetail flank
ch_half  = 8.5;                  // half width inside, and at the bulges
ch_floor = 2.2;                  // depth of the channel floor
ch_flank = 1.9;                  // flank ends at this depth
bulge_h  = 5;                    // bulge half length at the face
notch_d  = 0.8;                  // bulge end notches: depth past the bulge side,
notch_n  = 1.0;                  // starting this far below the face,
notch_l  = 2.2;                  // and this long, with 45-degree ends
cap_low  = 5.5;                  // cap underside, below the rim, at the face
cap_high = 4.0;                  // cap underside, below the rim, at the flank
roof_c   = 12.5;                 // closed end: the slot turns 45 degrees on each
                                 // side, its centre lines meeting this far below the rim

// inner wall recesses: 0.4 deep, 2.2 tall, rising 1:2 below and 45 degrees above
rec_d    = 0.4;
rec_h    = 2.2;
rec_lo   = 0.8;                  // height of the 1:2 lower slope
catch_t0 = 10.435;               // catch slots span this .. catch_t1 from the LU centre
catch_t1 = 16.435;
catch_z0 = 13.3;                 // lower catch slots (first band only)
catch_up = 9.2;                  // upper catch slots: this far below each 50 mm band top
groove_up = 4.2;                 // rim groove: this far below the rim
seam_g   = 0.5;                  // seam groove half width at its floor

// screw thread in the base holes (right-handed). Along the helix coordinate
// u = z - pitch * angle / 360 (mod pitch), with the angle measured about the
// hole axis from +x: the radius rises 3.0 -> 3.5 over [thr_u[0], thr_u[1]],
// stays 3.5 to thr_u[2], falls back to 3.0 by thr_u[3], and is 3.0 otherwise.
thr_p     = 3.125;
thr_r0    = 3.0;
thr_r1    = 3.5;
thr_u     = [1.0735, 2.0110, 2.6360, 3.5735];
thr_steps = 96;                  // facets per turn
hole_top  = 5.2;
hole_cone = 3.8;                 // entry cone radius at z = 0 (45 degrees)

nx_cells = ceil(NX - eps);
ny_cells = ceil(NY - eps);

// ------------------------------------------------------------------ helpers

// octagon: rectangle [x0,x1]x[y0,y1] with all four corners chamfered by c
function octagon(x0, x1, y0, y1, c) =
    [[x0 + c, y0], [x1 - c, y0], [x1, y0 + c], [x1, y1 - c],
     [x1 - c, y1], [x0 + c, y1], [x0, y1 - c], [x0, y0 + c]];

module oct_prism(x0, x1, y0, y1, c, z0, z1)
    translate([0, 0, z0]) linear_extrude(height = z1 - z0)
        polygon(octagon(x0, x1, y0, y1, c));

// the same octagon offset inward by d (negative d grows it)
function oct_in(x0, x1, y0, y1, c, d) =
    octagon(x0 + d, x1 - d, y0 + d, y1 - d, c - d * (2 - sqrt(2)));

// loft between two octagons at z0 and z1 (both must be convex)
module oct_loft(a, b, z0, z1)
    hull() {
        translate([0, 0, z0]) linear_extrude(height = 0.001) polygon(a);
        translate([0, 0, z1 - 0.001]) linear_extrude(height = 0.001) polygon(b);
    }

// ------------------------------------------------------------------ body

module outer_body() {
    // walls above the foot; the four flat faces get a 1 mm chamfer at the rim,
    // the diagonal corner faces run straight to the top
    intersection() {
        oct_prism(X0, X1, Y0, Y1, c_out, foot_z, ZT);
        translate([0, Y0 - 1, 0]) rotate([-90, 0, 0]) linear_extrude(height = Y1 - Y0 + 2)
            polygon([[X0, -foot_z + 1], [X1, -foot_z + 1], [X1, -(ZT - 1)],
                     [X1 - 1, -ZT], [X0 + 1, -ZT], [X0, -(ZT - 1)]]);
        translate([X0 - 1, 0, 0]) rotate([90, 0, 90]) linear_extrude(height = X1 - X0 + 2)
            polygon([[Y0, foot_z - 1], [Y1, foot_z - 1], [Y1, ZT - 1],
                     [Y1 - 1, ZT], [Y0 + 1, ZT], [Y0, ZT - 1]]);
    }
}

// the outer envelope of everything below the walls: vertical sides inset by
// pad_in, then a 45-degree chamfer out to the outer faces at foot_z
module base_envelope() foot_block(X0, X1, Y0, Y1);

// a block with the foot's chamfers: flat faces inset pad_in below and chamfered
// 45 degrees out to the full face at foot_z, corner faces inset corner_in and
// chamfered 45 degrees out to the full corner at foot_c
module foot_block(x0, x1, y0, y1)
    intersection_for (f = [[0, x1, pad_in, foot_z], [90, y1, pad_in, foot_z],
                           [180, -x0, pad_in, foot_z], [270, -y0, pad_in, foot_z],
                           [45, (x1 + y1 - c_out) / sqrt(2), corner_in, foot_c],
                           [135, (-x0 + y1 - c_out) / sqrt(2), corner_in, foot_c],
                           [225, (-x0 - y0 - c_out) / sqrt(2), corner_in, foot_c],
                           [315, (x1 - y0 - c_out) / sqrt(2), corner_in, foot_c]])
        foot_halfspace(f[0], f[1], f[2], f[3]);

// everything on the inner side of a face whose outward normal points at angle
// ang: the face sits d0 from the origin, inset by `inset` below z_full - inset
// and chamfered 45 degrees up to the full face at z_full
module foot_halfspace(ang, d0, inset, z_full)
    rotate([0, 0, ang]) rotate([90, 0, 0]) linear_extrude(height = 4000, center = true)
        polygon([[-2000, -2], [d0 - inset, -2], [d0 - inset, z_full - inset],
                 [d0, z_full], [d0, foot_z + 1], [-2000, foot_z + 1]]);

module cell_pad(cx, cy) {
    h = U/2 - pad_in;            // 21.8
    intersection() {
        foot_block(cx - U/2, cx + U/2, cy - U/2, cy + U/2);
        union() {
            // 0.4 mm chamfer on the bottom edge
            oct_loft(oct_in(cx - h, cx + h, cy - h, cy + h, pad_c, 0.4),
                     octagon(cx - h, cx + h, cy - h, cy + h, pad_c), 0, 0.4);
            translate([cx - U, cy - U, 0.4 - eps]) cube([2 * U, 2 * U, foot_z]);
        }
    }
}

module base() {
    intersection() {
        base_envelope();
        union() {
            for (i = [0:nx_cells - 1], j = [0:ny_cells - 1]) cell_pad(U*i, U*j);
            translate([X0, Y0, bridge_z]) cube([X1 - X0, Y1 - Y0, foot_z - bridge_z + eps]);
            // between the pads the floor reaches down to bridge_lo, except in the gap
            // between two pads' 45-degree faces, where it stops at bridge_z: beside
            // the flat part of each pad side across columns, and along the whole
            // length of the seams between rows (through the crossings)
            difference() {
                translate([X0, Y0, bridge_lo]) cube([X1 - X0, Y1 - Y0, bridge_z - bridge_lo + eps]);
                fl = U/2 - pad_in - pad_c;                     // flat half length, 16.352
                for (i = [0:1:nx_cells - 2], j = [0:ny_cells - 1])
                    translate([U * i + U/2, U * j, 0]) rotate([0, 0, 90]) seam_gap(2 * fl);
                for (j = [0:1:ny_cells - 2])
                    translate([(U * (nx_cells - 1)) / 2, U * j + U/2, 0])
                        seam_gap(U * (nx_cells - 1) + 2 * fl);
            }        }
    }
}

// the gap between two pads' 45-degree faces near the floor underside, centred on
// a seam running along x, for the given length; its half width at height z is
// pad_in + pad_top - z (1.6 at bridge_lo, 1.4 at bridge_z)
function gap_hw(z) = pad_in + pad_top - z;
module seam_gap(len)
    translate([-len / 2, 0, 0]) rotate([90, 0, 90]) linear_extrude(height = len)
        polygon([[-gap_hw(bridge_lo - 0.1), bridge_lo - 0.1], [gap_hw(bridge_lo - 0.1), bridge_lo - 0.1],
                 [gap_hw(bridge_z + 0.1), bridge_z + 0.1], [-gap_hw(bridge_z + 0.1), bridge_z + 0.1]]);

module cavity() {
    xi0 = X0 + wall; xi1 = X1 - wall; yi0 = Y0 + wall; yi1 = Y1 - wall;
    // 1 mm 45-degree chamfer where the floor meets the walls
    oct_loft(oct_in(xi0, xi1, yi0, yi1, c_in, 1),
             octagon(xi0, xi1, yi0, yi1, c_in), floor_z, floor_z + 1);
    oct_prism(xi0, xi1, yi0, yi1, c_in, floor_z + 1 - eps, ZT - 1.2 + eps);
    // inner rim chamfer: 1.6 out over the top 1.2
    oct_loft(octagon(xi0, xi1, yi0, yi1, c_in),
             oct_in(xi0, xi1, yi0, yi1, c_in, -1.6), ZT - 1.2, ZT + eps);
    translate([0, 0, ZT]) linear_extrude(height = 1)
        polygon(oct_in(xi0, xi1, yi0, yi1, c_in, -1.6));
}

// ------------------------------------------------------------------ channels

// dovetail channel cutter for one LU of one face, built in face coordinates
// (t across, n into the wall, z up) and placed by the caller
module channel_cutter(kind) {
    if (kind == "topped")
        // each limit must be its own child of intersection(); grouped under one
        // if() they would be unioned first
        intersection() {
            channel_open();
            channel_cap();
            roof_side() channel_roof();
            mirror([1, 0, 0]) roof_side() channel_roof();
        }
    else
        channel_open();
}

// the slot without a closed end: dovetail plus the bulges every 25 mm
module channel_open() {
    profile = [[-ch_open, -1], [ch_open, -1], [ch_open, ch_lip],
               [ch_half, ch_flank], [ch_half, ch_floor],
               [-ch_half, ch_floor], [-ch_half, ch_flank], [-ch_open, ch_lip]];
    translate([0, 0, -1]) linear_extrude(height = ZT + 2) polygon(profile);
    for (k = [0:1:floor(ZT / 25)]) {
        zc = 5 + 25 * k;
        translate([0, ch_floor, 0]) rotate([90, 0, 0])
            linear_extrude(height = ch_floor + 1)
                polygon([[-ch_open, zc - bulge_h], [ch_open, zc - bulge_h],
                         [ch_half, zc - bulge_h + (ch_half - ch_open)],
                         [ch_half, zc + bulge_h - (ch_half - ch_open)],
                         [ch_open, zc + bulge_h], [-ch_open, zc + bulge_h],
                         [-ch_half, zc + bulge_h - (ch_half - ch_open)],
                         [-ch_half, zc - bulge_h + (ch_half - ch_open)]]);
        // a small notch in each side wall at both ends of the bulge
        zs = zc - bulge_h + (ch_half - ch_open);       // bulge straight section starts
        ze = zc + bulge_h - (ch_half - ch_open);       // and ends
        for (m = [0, 1]) mirror([m, 0, 0]) {
            bulge_notch(zs);
            bulge_notch(ze - notch_l);
        }
    }
}

// one notch at the +t side of a bulge, spanning z0 .. z0 + notch_l
module bulge_notch(z0)
    intersection() {
        translate([0, 0, z0 - 1]) linear_extrude(height = notch_l + 2)
            polygon([[ch_half - 0.1, notch_n - 0.1], [ch_half, notch_n],
                     [ch_half + notch_d, notch_n + notch_d],
                     [ch_half + notch_d, ch_floor], [ch_half - 0.1, ch_floor]]);
        translate([0, ch_floor + 0.5, 0]) rotate([90, 0, 0]) linear_extrude(height = 3)
            polygon([[ch_half - 0.1, z0 - 0.1], [ch_half, z0],
                     [ch_half + notch_d, z0 + notch_d], [ch_half + notch_d, z0 + notch_l - notch_d],
                     [ch_half, z0 + notch_l], [ch_half - 0.1, z0 + notch_l + 0.1]]);
    }

// below the cap: its underside is hooked 45 degrees between the lip and the flank
module channel_cap()
    translate([-20, 0, 0]) rotate([90, 0, 90]) linear_extrude(height = 40)
        polygon([[-1, -2], [-1, ZT - cap_low], [ch_lip, ZT - cap_low],
                 [ch_flank, ZT - cap_high], [ch_floor + 1, ZT - cap_high],
                 [ch_floor + 1, -2]]);

// one side of the closed end, built as a dovetail half-profile in (s, n)
// extruded along the 45-degree line and rotated into place
// (sized from the shell height: a fixed size would clip the bottom of tall shells)
module channel_roof()
    linear_extrude(height = 8 * ZT, center = true)
        polygon([[-4 * ZT, -1], [ch_open, -1], [ch_open, ch_lip], [ch_half, ch_flank],
                 [ch_half, ch_floor + 1], [-4 * ZT, ch_floor + 1]]);

module roof_side()
    translate([(ZT - roof_c) / 2, 0, (ZT - roof_c) / 2]) rotate([0, -45, 0]) children();

// place a cutter on a face: side is "front", "back", "left" or "right"
module place_on_face(side, s) {
    if (side == "front")      translate([s, Y0, 0]) children();
    else if (side == "back")  translate([s, Y1, 0]) rotate([0, 0, 180]) children();
    else if (side == "left")  translate([X0, s, 0]) rotate([0, 0, -90]) children();
    else if (side == "right") translate([X1, s, 0]) rotate([0, 0, 90]) children();
}

module channels() {
    for (f = [["front", front_wall, nx_cells], ["back", back_wall, nx_cells],
              ["left", left_wall, ny_cells], ["right", right_wall, ny_cells]])
        if (f[1] != "simple")
            for (k = [0:f[2] - 1])
                place_on_face(f[0], U * k) channel_cutter(f[1]);
}

// ------------------------------------------------------------------ inner recesses

// z profile shared by the catch slots and the rim groove, as a polygon in (n, z)
// where n is depth into the wall from the inner face
function rec_profile(z0) =
    [[-1, z0 - 0.5], [0, z0], [rec_d, z0 + rec_lo], [rec_d, z0 + rec_h - rec_d],
     [0, z0 + rec_h], [-1, z0 + rec_h + 1]];

// a catch slot on the wall, in face coordinates (t along, n into the wall from
// the inner face, z up); its ends are 45 degrees in t
module catch_slot(z0)
    intersection() {
        translate([0, 0, z0 - 1]) linear_extrude(height = rec_h + 2)
            polygon([[catch_t0 - 1, -1], [catch_t1 + 1, -1], [catch_t1, 0],
                     [catch_t1 - rec_d, rec_d], [catch_t0 + rec_d, rec_d], [catch_t0, 0]]);
        rotate([90, 0, 90]) translate([0, 0, catch_t0 - 2])
            linear_extrude(height = catch_t1 - catch_t0 + 4) polygon(rec_profile(z0));
    }

// a vertical groove on the inner face at a seam, z0 .. z1
module seam_groove(z0, z1)
    intersection() {
        translate([0, 0, z0 - 1]) linear_extrude(height = z1 - z0 + 2)
            polygon([[-seam_g - rec_d - 1, -1], [seam_g + rec_d + 1, -1], [seam_g + rec_d, 0],
                     [seam_g, rec_d], [-seam_g, rec_d], [-seam_g - rec_d, 0]]);
        rotate([90, 0, 90]) translate([0, 0, -5]) linear_extrude(height = 10)
            polygon([[-1, z0 - 0.5], [0, z0], [rec_d, z0 + rec_lo], [rec_d, z1 - rec_d],
                     [0, z1], [-1, z1 + 1]]);
    }

// place a feature on the inner face of a wall: the outer face frame shifted by
// the wall thickness, so n is measured from the inner face
module place_inner(side, s)
    place_on_face(side, s) translate([0, wall, 0]) mirror([0, 1, 0]) children();

module inner_recesses() {
    zbands = [for (k = [1:1:floor(NZ + eps)]) 5 + U * k];       // 50 mm band tops
    for (f = [["front", nx_cells], ["back", nx_cells], ["left", ny_cells], ["right", ny_cells]]) {
        for (k = [0:f[1] - 1]) place_inner(f[0], U * k) for (m = [0, 1]) mirror([m, 0, 0]) {
            catch_slot(catch_z0);
            for (zb = zbands) catch_slot(zb - catch_up);
        }
        // seam grooves between LUs along the face, one per 50 mm band
        for (k = [0:1:f[1] - 2]) place_inner(f[0], U * k + U/2)
            for (b = [0:1:floor(NZ + eps) - 1]) seam_groove(catch_z0 + U * b, U * (b + 1) - 2);
    }
    // rim groove: the flat inner faces pushed out, the corner planes kept
    xi0 = X0 + wall; xi1 = X1 - wall; yi0 = Y0 + wall; yi1 = Y1 - wall;
    zg = ZT - groove_up;
    oct_loft(octagon(xi0, xi1, yi0, yi1, c_in),
             octagon(xi0 - rec_d, xi1 + rec_d, yi0 - rec_d, yi1 + rec_d, c_in + 2 * rec_d), zg, zg + rec_lo);
    oct_prism(xi0 - rec_d, xi1 + rec_d, yi0 - rec_d, yi1 + rec_d, c_in + 2 * rec_d,
              zg + rec_lo - eps, zg + rec_h - rec_d + eps);
    oct_loft(octagon(xi0 - rec_d, xi1 + rec_d, yi0 - rec_d, yi1 + rec_d, c_in + 2 * rec_d),
             octagon(xi0, xi1, yi0, yi1, c_in), zg + rec_h - rec_d, zg + rec_h);
}

// ------------------------------------------------------------------ clip slots

// octagonal section in the (t, z) plane at depth n: half width a, half height b,
// corner chamfer c
module oct_slab(a, b, c, n)
    translate([0, n, 0]) rotate([-90, 0, 0]) linear_extrude(height = 0.001)
        polygon([[-a + c, -b], [a - c, -b], [a, -b + c], [a, b - c],
                 [a - c, b], [-a + c, b], [-a, b - c], [-a, -b + c]]);

// waisted through-slot at a seam: 6 x 2 at both faces, 4 wide in the middle.
// Face frame: t across, n from the outer face inward, z up; centred on z = zc
module seam_slot(zc)
    translate([0, 0, zc]) {
        hull() { oct_slab(3.2, 1.2, 0.517, -0.1); oct_slab(3.0, 1.0, 0.4, 0.2); }
        hull() { oct_slab(3.0, 1.0, 0.4, 0.2);   oct_slab(3.0, 1.0, 0.4, 0.8); }
        hull() { oct_slab(2.2, 1.0, 0.318, 0.8); oct_slab(2.0, 1.0, 0.4, 1.0); }
        hull() { oct_slab(2.0, 1.0, 0.4, 1.0);   oct_slab(2.0, 1.0, 0.4, 1.8); }
        hull() { oct_slab(2.0, 1.0, 0.4, 1.8);   oct_slab(2.2, 1.0, 0.318, 2.0); }
        hull() { oct_slab(3.0, 1.0, 0.4, 2.0);   oct_slab(3.0, 1.0, 0.4, 2.6); }
        hull() { oct_slab(3.0, 1.0, 0.4, 2.6);   oct_slab(3.5, 1.5, 0.693, 3.1); }
    }

// the slot through each outer corner, at the same height as the top seam slots;
// the corner wall is 2 mm thick, so only the outer part of the seam slot profile
// exists there
module corner_slot(zc)
    translate([0, 0, zc]) {
        hull() { oct_slab(3.2, 1.2, 0.517, -0.1); oct_slab(3.0, 1.0, 0.4, 0.2); }
        hull() { oct_slab(3.0, 1.0, 0.4, 0.2);   oct_slab(3.0, 1.0, 0.4, 0.8); }
        hull() { oct_slab(2.2, 1.0, 0.318, 0.8); oct_slab(2.0, 1.0, 0.4, 1.0); }
        hull() { oct_slab(2.0, 1.0, 0.4, 1.0);   oct_slab(2.0, 1.0, 0.4, 1.8); }
        hull() { oct_slab(2.0, 1.0, 0.4, 1.8);   oct_slab(2.5, 1.5, 0.693, 2.3); }
    }

module corner_slots()
    for (c = [[X1, Y1, 45], [X0, Y1, 135], [X0, Y0, 225], [X1, Y0, 315]]) {
        // centre of the diagonal corner face
        fx = c[0] - sign(c[0] - (X0 + X1) / 2) * c_out / 2;
        fy = c[1] - sign(c[1] - (Y0 + Y1) / 2) * c_out / 2;
        translate([fx, fy, 0]) rotate([0, 0, c[2] + 90]) corner_slot(ZT - 3);
    }

module seam_slots() {
    for (f = [["front", nx_cells], ["back", nx_cells], ["left", ny_cells], ["right", ny_cells]])
        for (k = [0:1:f[1] - 2]) place_on_face(f[0], U * k + U/2)
            for (zc = [27:25:ZT - 1]) seam_slot(zc);
}

// ------------------------------------------------------------------ base pockets

// octagonal bar used by the pad clip pockets: half width a, z 1 .. 3, 0.4
// chamfers on the long edges, running along y from y0 to y1
module pocket_bar(a, y0, y1)
    translate([0, y1, 2]) rotate([90, 0, 0]) linear_extrude(height = y1 - y0)
        polygon(pocket_section(a, 1, 0.4));

// octagonal pocket section about z = 2: half width a, half height b, chamfer c
function pocket_section(a, b, c) =
    [[-a + c, -b], [a - c, -b], [a, -b + c], [a, b - c], [a - c, b], [-a + c, b], [-a, b - c], [-a, -b + c]];

// a thin slice of a pocket section at depth y along the pocket axis
module pocket_slab(a, b, c, y)
    translate([0, y, 2]) rotate([90, 0, 0]) linear_extrude(height = 0.001) polygon(pocket_section(a, b, c));

// clip pocket entering a pad side, built for the +y side of a pad centred at the
// origin, at t along the side: a 6 wide entry, then an obround head
module side_pocket(t) {
    h = U/2 - pad_in;                                   // 21.8, the pad face
    translate([t, 0, 0]) {
        translate([-3, 19.0, 1]) cube([6, h - 19.0 + 1, 2]);
        hull() {                                        // 0.2 chamfer at the opening
            translate([-3, h - 0.2, 1]) cube([6, 0.001, 2]);
            translate([-3.2, h, 1]) cube([6.4, 0.5, 2]);
        }
        hull() for (dx = [-1.25, 1.25]) translate([dx, 18.05, 1]) cylinder(r = 2.25, h = 2);
        // ceiling slits, 0.1 wide and 0.2 tall, following the pocket outline
        for (ys = [16.7, 17.6, 19.7]) intersection() {
            union() {
                translate([-3, 19.0, 2.9]) cube([6, h - 19.0, 0.3]);
                hull() for (dx = [-1.25, 1.25]) translate([dx, 18.05, 2.9]) cylinder(r = 2.25, h = 0.3);
            }
            translate([-10, ys, 2.9]) cube([20, 0.1, 0.3]);
        }
    }
}

// T-shaped clip pocket entering a pad corner along its diagonal, built for the
// +x+y corner of a pad centred at the origin
module corner_pocket() {
    sf = (2 * (U/2 - pad_in) - pad_c) / sqrt(2);        // corner face, along the diagonal
    rotate([0, 0, -45]) {
        pocket_bar(2.0, sf - 2.8, sf + 0.5);
        pocket_bar(3.0, sf - 4.8, sf - 2.8);
        // 0.2 mm 45-degree chamfer around the opening
        hull() { pocket_slab(2.0, 1.0, 0.4, sf - 0.2); pocket_slab(2.5, 1.5, 0.693, sf + 0.3); }
    }
}

// pyramid notch under the middle of a pad side (+y side of a pad at the origin):
// y - z >= 19.5 and y -+ x - sqrt(2) z >= 17.222
module edge_notch() {
    h = U/2 - pad_in;
    intersection() {
        // 45-degree chamfer across the edge
        translate([-10, 0, 0]) rotate([90, 0, 90]) linear_extrude(height = 20)
            polygon([[19.5 - 1, -1], [h + 1, -1], [h + 1, h + 1 - 19.5], [19.5, 0]]);
        notch_side(1);
        notch_side(-1);
    }
}

// half-space y - sg * x - sqrt(2) z >= 17.222 inside a box; faces wound
// clockwise seen from outside
module notch_side(sg)
    polyhedron(
        points = [[-10, 17.222 - sg * 10 - sqrt(2), -1], [10, 17.222 + sg * 10 - sqrt(2), -1],
                  [10, 17.222 + sg * 10 + 4 * sqrt(2), 4], [-10, 17.222 - sg * 10 + 4 * sqrt(2), 4],
                  [-10, 40, -1], [10, 40, -1], [10, 40, 4], [-10, 40, 4]],
        faces = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [7, 6, 2, 3], [2, 6, 5, 1], [7, 3, 0, 4]]);

// the central pocket of each pad (built at the origin)
function point_prism(b) =
    [[-(18.021 + b), b], [18.021 + b, b], [8.5, -9.521], [8.5, -2.479], [0, 6.021],
     [-8.5, -2.479], [-8.5, -9.521]];
module central_pocket() {
    // flared octagon: half 6.0 at z = 0.4 growing 45 degrees to 8.5 at z = 2.9
    oct_prism(-6.0, 6.0, -6.0, 6.0, 3.515, -1, 0.4 + eps);
    oct_loft(octagon(-6.0, 6.0, -6.0, 6.0, 3.515), octagon(-8.5, 8.5, -8.5, 8.5, 4.979), 0.4, 2.9);
    oct_prism(-8.5, 8.5, -8.5, 8.5, 4.979, 2.9 - eps, 3.2);
    // pointed-top prism toward -y, its far edge stepping out 45 degrees at 1.8 .. 2.2
    translate([0, 0, -1]) linear_extrude(height = 2.8 + eps) polygon(point_prism(-14.5));
    hull() {
        translate([0, 0, 1.8]) linear_extrude(height = 0.001) polygon(point_prism(-14.5));
        translate([0, 0, 2.2 - 0.001]) linear_extrude(height = 0.001) polygon(point_prism(-14.9));
    }
    translate([0, 0, 2.2 - eps]) linear_extrude(height = 1.0 + eps) polygon(point_prism(-14.9));
    // ceiling slits over the pointed prism, every 1 mm
    for (k = [0:8]) intersection() {
        translate([0, 0, 3.0]) linear_extrude(height = 0.4) polygon(point_prism(-14.9));
        translate([-10, -14.2 + k, 3.0]) cube([20, 0.1, 0.4]);
    }
    // a plate up to 3.4 in the middle band, a square to 3.6, then the octagon to 5.2
    // the plate keeps the flared octagon's two top chamfers; its lower corners are square
    translate([0, 0, 3.2 - eps]) linear_extrude(height = 0.2 + eps)
        polygon([[-8.5, -5.1], [8.5, -5.1], [8.5, 3.521], [6.921, 5.1], [-6.921, 5.1], [-8.5, 3.521]]);
    translate([-5.1, -5.1, 3.4 - eps]) cube([10.2, 10.2, 0.2 + 2 * eps]);
    oct_prism(-5.1, 5.1, -5.1, 5.1, 2.988, 3.6 - eps, 5.2);
}

// i, j: the pad's cell indices. Side clip pockets only open onto the outside
// of the shell; a side facing a neighbouring pad has none.
module pad_features(i, j)
    translate([U * i, U * j, 0]) {
        central_pocket();
        // rotation -> the pad side it builds: 0 = +y, 90 = -x, 180 = -y, 270 = +x
        outside = [j == ny_cells - 1, i == 0, j == 0, i == nx_cells - 1];
        for (k = [0:3]) rotate([0, 0, 90 * k]) {
            if (outside[k]) {
                side_pocket(7.5);
                side_pocket(-7.5);
            }
            corner_pocket();
            edge_notch();
        }
    }

// ------------------------------------------------------------------ holes

module base_holes() {
    for (i = [0:nx_cells - 1], j = [0:ny_cells - 1], dx = [-12.5, 12.5], dy = [-12.5, 12.5])
        translate([U*i + dx, U*j + dy, 0]) threaded_hole();
}

// one blind threaded hole, axis at the origin, from below z = 0 up to hole_top
module threaded_hole() {
    intersection() {
        union() {
            rotate([0, 0, 180 / thr_steps]) translate([0, 0, -1])
                cylinder(r = thr_r0 / cos(180 / thr_steps), h = hole_top + 1, $fn = thr_steps);
            thread_ridge(-thr_p, 3);
        }
        translate([-5, -5, -1]) cube([10, 10, hole_top + 1]);
    }
    // 45-degree entry cone
    translate([0, 0, -1]) cylinder(r1 = hole_cone + 1, r2 = thr_r0 - 0.01,
                                   h = 1 + hole_cone - thr_r0 + 0.01, $fn = thr_steps);
}

// the groove of an internal thread as a helical bar with a trapezoid section,
// starting at z0 and running the given number of turns; its inner edge sits
// just inside the core cylinder so the two overlap
function thr_section() =
    let (k = (thr_u[1] - thr_u[0]) / (thr_r1 - thr_r0), ri = thr_r0 - 0.05)
    [[ri, thr_u[0] - k * 0.05], [thr_r1, thr_u[1]], [thr_r1, thr_u[2]], [ri, thr_u[3] + k * 0.05]];

module thread_ridge(z0, turns) {
    n = thr_steps * turns;
    sec = thr_section();
    pts = [for (i = [0:n]) let (a = 360 * i / thr_steps, dz = z0 + thr_p * i / thr_steps)
               for (q = sec) [q[0] * cos(a), q[0] * sin(a), q[1] + dz]];
    faces = concat(
        [[3, 2, 1, 0]],
        [[4 * n, 4 * n + 1, 4 * n + 2, 4 * n + 3]],
        [for (i = [0:n - 1], k = [0:3])
            let (a = 4 * i + k, b = 4 * i + (k + 1) % 4) [a, b, b + 4, a + 4]]);
    polyhedron(points = pts, faces = faces);
}

// ------------------------------------------------------------------ model

difference() {
    union() {
        outer_body();
        base();
    }
    cavity();
    channels();
    base_holes();
    inner_recesses();
    seam_slots();
    corner_slots();
    for (i = [0:nx_cells - 1], j = [0:ny_cells - 1]) pad_features(i, j);
}
