// MultiBin Simple Drawer - parametric remake
// Reverse-engineered from MultiBoard's official "MultiBin Simple Drawer" STLs so that
// matching configurations reproduce the originals; every other configuration follows
// the same rules (50 mm grid per LU, identical wall, lip, label, scoop and magnet
// geometry). Paste this whole file into MakerWorld's Parametric Model Maker.
//
// Drawer orientation: X = width, Y = depth (front toward -Y), Z = height.
// Centered on X; back face at Y = 0; base at Z = 0.

/* [Size (in 50 mm layout units)] */
// Drawer width in LU
width_lu = 2; // [1:0.5:12]
// Drawer depth in LU
depth_lu = 2; // [1:0.5:12]
// Drawer height in LU
height_lu = 1; // [0.5:0.5:12]

/* [Compartments] */
// Number of width-wise sections (columns)
width_sections = 1; // [1:12]
// Number of depth-wise sections (rows)
depth_sections = 1; // [1:12]
// Relative widths of the columns, left to right as you face the label, such as 2,1,1. Blank means equal
width_ratios = "";
// Relative depths of the rows, front to back, such as 1,2. Each row is counted with the divider behind it. Blank means equal
depth_ratios = "";
// Divider height in LU (clamped to the wall height)
divider_height_lu = 12; // [0.5:0.5:12]
// Divider thickness in mm
divider_thickness = 1.0; // [0.6:0.1:4]
// Finger scoop in the tops of the dividers. front slopes each width divider down toward the label end; center notches every divider between crossings
divider_scoop = "none"; // [none, front, center]
// Depth of the scoop in mm (reduced where a divider is too low or a compartment too short for it)
divider_scoop_mm = 10; // [2:1:40]

/* [Features] */
// Magnet pocket(s) in the back wall (thickens the back wall to 4 mm)
magnet = false;
// Label holder on the front face
label = "large"; // [none, small, large]

/* [Hidden] */
$fs = 0.25;
$fa = 1;
eps = 0.01;
hs  = 0.0005;   // hull-slab thickness: keeps lofted faces on their nominal planes

U  = 50;                        // one layout unit
W  = max(1, width_lu);
D  = max(1, depth_lu);
H  = max(0.5, height_lu);

OW   = U*W - 7;                 // outer width
half = OW/2;
OH   = U*H - 7;                 // outer height
WT   = OH - 5.272;              // side/back wall + divider top height
F    = -(U*D - 1);              // front wall outer face (Y)
LIPF = F - 8;                   // lip plate front face (Y)

// Feature gates: the label frame and the magnet pocket both need a full layout
// unit of height; below that they are omitted (with a warning) instead of
// emitting broken geometry. Gating on the unit rather than on a millimetre
// threshold matters for heights typed in off the 0.5 step: at 0.74 LU a
// millimetre gate would still build the label frame, and it would fuse into
// the pull lip.
lab_on = (label != "none") && (H >= 1);
mag_on = magnet && (H >= 1);

floor_t   = 1.6;                // floor thickness
wall_s    = 1.0;                // side wall thickness
wall_b    = mag_on ? 4.0 : 1.0; // back wall base thickness
wall_f    = 2.0;                // front wall thickness
lean0     = WT - 8;             // back wall starts thickening to 2 mm here
lean1     = WT - 4;             // back wall reaches 2 mm here
fil_r     = 5;                  // interior floor fillet radius (front/back/dividers)
fil_cz    = floor_t + fil_r;    // fillet center height (6.6)
side_ch   = 4.686;              // interior side-wall floor chamfer leg
bot_ch    = 5.272;              // outer side bottom chamfer leg
frt_r     = 7;                  // outer front-bottom fillet radius
brace_len = min(8*H + 2, U*D - 5);  // corner brace flange length, clamped to the depth
div_t     = min(4, max(0.6, divider_thickness));   // divider thickness (1.0 on the originals)
div_top   = min(WT, U*divider_height_lu - 12.272); // divider top height

n_cells = max(1, floor(W + eps));                 // full 50 mm cells across the width
cell_c  = [for (i = [0:1:n_cells-1]) (i - (n_cells-1)/2) * U];       // cell centers
cell_b  = n_cells < 2 ? [] :
          [for (i = [0:1:n_cells-2]) (cell_c[i] + cell_c[i+1]) / 2]; // cell boundaries

n_grooves = max(0, floor((WT - 3) / U + eps));    // internal 50 mm height boundaries

// ---- compartment sizes typed as text, such as "2,1,1"
// OpenSCAD 2021.01 has no string-to-number function, so the numbers are read
// one character at a time. A list is numbers separated by commas, with spaces
// allowed around each; anything else makes the whole text unusable.
function _digit(c) = let (h = search(c, "0123456789")) len(h) == 0 ? -1 : h[0];
function _blank(s, i = 0) = i >= len(s) ? true : s[i] != " " ? false : _blank(s, i + 1);
// index of the next comma at or after i, or the end of the text
function _field_end(s, i) = i >= len(s) || s[i] == "," ? i : _field_end(s, i + 1);
// the number written in s from i up to j, or undef if that stretch is not one number
function _number(s, i, j, acc = 0, scale = 0, digits = 0, done = false) =
    i >= j ? (digits > 0 ? acc : undef) :
    let (c = s[i], d = _digit(c))
    c == " " ? _number(s, i + 1, j, acc, scale, digits, digits > 0 || scale != 0) :
    done ? undef :
    d >= 0 ? (scale == 0 ? _number(s, i + 1, j, acc*10 + d, 0, digits + 1)
                         : _number(s, i + 1, j, acc + d*scale, scale/10, digits + 1)) :
    c == "." && scale == 0 ? _number(s, i + 1, j, acc, 0.1, digits) :
    undef;
// every number of a comma-separated list, or undef if any field is not a number
function _numbers(s, i = 0, out = []) =
    let (j = _field_end(s, i), v = _number(s, i, j))
    v == undef ? undef :
    j >= len(s) ? concat(out, [v]) : _numbers(s, j + 1, concat(out, [v]));
function _sum(v, n, i = 0) = i >= n ? 0 : v[i] + _sum(v, n, i + 1);   // sum of the first n values

// The ratios for n sections from the typed text. [] means equal sections: a
// blank text, or numbers that are all the same. undef means the text is not a
// list of positive numbers; that holds for every number typed, including any
// beyond the n-th, which are otherwise not used. Too few numbers are padded with
// the last one given.
function section_ratios(text, n) =
    !is_string(text) ? undef :
    _blank(text) ? [] :
    let (v = _numbers(text))
    v == undef || min(v) <= 0 ? undef :
    let (p = [for (i = [0:1:n - 1]) v[min(i, len(v) - 1)]])
    max(p) == min(p) ? [] : p;

// A compartment narrower than this at the floor of the cavity is a sliver, and
// is not built. Higher up a wall can stand up to 1 mm further in (the back
// wall's lean, and the panels behind the grooves and jogs of taller drawers).
min_cell = 2;
cavW = (half - wall_s) - (-(half - wall_s)); // cavity width between the side walls
cavD = (-wall_b) - (F + wall_f);            // cavity depth between the front and back walls

// widths of the columns for a list of ratios ([] = equal), left to right
function width_cells(r) =
    let (usable = cavW - (width_sections - 1)*div_t)
    len(r) == 0 ? [for (i = [0:1:width_sections - 1]) usable/width_sections]
                : [for (i = [0:1:width_sections - 1]) usable*r[i]/_sum(r, width_sections)];
// Division lines of the rows for a list of ratios ([] = equal), front to back.
// The originals place each depth divider with its BACK face on its division
// line (g212 measured), so a divider takes its thickness from the row in front
// of the line, and with equal ratios every row but the back one is one divider
// thickness shorter than the back one.
function depth_lines(r) =
    let (cavB = -wall_b, cavF = F + wall_f)
    len(r) == 0 ? [for (k = [1:1:depth_sections - 1]) cavB - (depth_sections - k)*(cavD/depth_sections)]
                : [for (k = [1:1:depth_sections - 1]) cavF + cavD*_sum(r, k)/_sum(r, depth_sections)];
// clear depths of the rows, front to back
function depth_cells(r) =
    let (cavB = -wall_b, cavF = F + wall_f, y = depth_lines(r), n = depth_sections)
    [for (k = [0:1:n - 1]) (k == n - 1 ? cavB : y[k] - div_t) - (k == 0 ? cavF : y[k - 1])];

w_typed = section_ratios(width_ratios, width_sections);
d_typed = section_ratios(depth_ratios, depth_sections);
// ratios that would leave a sliver are dropped for equal sections
w_ratio = (w_typed == undef || min(width_cells(w_typed)) < min_cell) ? [] : w_typed;
d_ratio = (d_typed == undef || min(depth_cells(d_typed)) < min_cell) ? [] : d_typed;
// dividers are left out altogether when even equal sections would be slivers
w_div = width_sections > 1 && min(width_cells(w_ratio)) >= min_cell;
d_div = depth_sections > 1 && min(depth_cells(d_ratio)) >= min_cell;

if (w_typed == undef)
    echo("WARNING: width_ratios is not a list of positive numbers such as 2,1,1; using equal widths.");
else if (w_typed != w_ratio)
    echo("WARNING: width_ratios would leave a column under 2 mm wide; using equal widths.");
if (d_typed == undef)
    echo("WARNING: depth_ratios is not a list of positive numbers such as 1,2; using equal depths.");
else if (d_typed != d_ratio)
    echo("WARNING: depth_ratios would leave a row under 2 mm deep; using equal depths.");
if (width_sections > 1 && !w_div)
    echo("WARNING: the columns would be under 2 mm wide; width dividers omitted.");
if (depth_sections > 1 && !d_div)
    echo("WARNING: the rows would be under 2 mm deep; depth dividers omitted.");

// Left-hand X face of every width divider, left to right. The front-bottom
// fillet cut does not read this: it is placed from the 50 mm cell boundaries
// (deviation D5), so uneven columns do not move it.
function divider_x() =
    !w_div ? [] :
    let (cavL = -(half - wall_s), cw = width_cells(w_ratio))
    len(w_ratio) == 0 ? [for (i = [1:1:width_sections - 1]) cavL + i*cw[0] + (i - 1)*div_t]
                      : [for (i = [1:1:width_sections - 1]) cavL + _sum(cw, i) + (i - 1)*div_t];

label_cells = (lab_on && label == "large") ? min(2, n_cells) : 1;
lab_win  = 13.2  + 25*(label_cells-1);  // window half width
lab_chan = 14.25 + 25*(label_cells-1);  // card channel half width
lab_foot = 16.4  + 25*(label_cells-1);  // rail outboard half width at the wall face
lab_p    = 1.6;                         // frame protrusion in front of the wall face

if (label != "none" && !lab_on)
    echo("WARNING: the label holder needs a drawer at least 1 LU tall; label omitted.");
if (magnet && !mag_on)
    echo("WARNING: the magnet pocket needs a drawer at least 1 LU tall; magnet omitted.");
if (lab_on && label == "large" && n_cells < 2)
    echo("NOTE: large label needs a drawer at least 2 LU wide; using the 1-cell frame.");

// ------------------------------------------------------------------ helpers

// 2D polygon in the (Y,Z) plane extruded along +X from x0 to x1
module prismX(pts, x0, x1) {
    translate([x0, 0, 0]) rotate([90, 0, 90])
        linear_extrude(height = x1 - x0) polygon(pts);
}
// 2D polygon in the (X,Z) plane extruded along +Y from y0 to y1  (y0 < y1)
module prismY(pts, y0, y1) {
    translate([0, y1, 0]) rotate([90, 0, 0])
        linear_extrude(height = y1 - y0) polygon(pts);
}
// ------------------------------------------------------------------ core parts

// back wall (Y,Z) profile, including the top lean and the brace inner face
back_prof = mag_on ?
    [[0, 1], [0, OH], [-2, OH], [-4, WT], [-4, 0], [-1, 0]] :
    [[0, 1], [0, OH], [-2, OH], [-2, lean1], [-1, lean0], [-1, 0]];

module back_wall() {
    difference() {
        prismX(back_prof, -half, half);
        for (k = [1:1:n_grooves]) groove_cut(k*U);
    }
}
// the inward-jogged wall panels behind the grooves; added after the cavity cut
module groove_bumps() {
    if (!mag_on) for (k = [1:1:n_grooves]) groove_bump(k*U);
}
// (X,Z) octagon spanning x0..x1, z0..z1 with 45-degree corner chamfer legs
function oct_xz(x0, x1, z0, z1, leg) = [
    [x0, z0 + leg], [x0 + leg, z0], [x1 - leg, z0], [x1, z0 + leg],
    [x1, z1 - leg], [x1 - leg, z1], [x0 + leg, z1], [x0, z1 - leg]];

// outer groove at height zk: an octagonal recess, 1 mm deep, lofted between
// its outer-face outline and its floor outline (60-degree drafts all around)
// The 45-degree corner legs shrink with depth at 1.015 per mm (measured), the
// same law the side-wall jog windows use.
module groove_cut(zk) {
    hull() {
        prismY(oct_xz(-(half - 5), half - 5, zk - 8.5, zk + 1.5, 2.929), 0, hs);
        prismY(oct_xz(-(half - 6.732), half - 6.732, zk - 6.768, zk - 0.232, 1.914), -1 - hs, -1);
    }
}
// matching inward-jogged wall panel: the shell offset of the groove (measured)
module groove_bump(zk) {
    hull() {
        prismY(oct_xz(-(half - 4.732), half - 4.732, zk - 8.768, zk + 1.768, 3.086), -1 - hs, -1);
        prismY(oct_xz(-(half - 6.464), half - 6.464, zk - 7.036, zk + 0.036, 2.071), -2, -2 + hs);
    }
}

// side-wall jog window polygon in (Y,Z), at inset d from the outer face (d in 0..1).
// Same numbers as the back-wall groove: 60-degree drafts on every edge, and plain
// 45-degree corner chamfers with equal legs (measured from the originals).
function jog_w(zk, d) =
    let (y0 = -5 - 1.732*d,          // back edge (max y)
         y1 = F + 5 + 1.732*d,       // front edge (min y)
         zA = zk - 8.5 + 1.732*d, zB = zk + 1.5 - 1.732*d,
         leg = 2.929 - 1.015*d)
    [[y0, zA + leg], [y0 - leg, zA], [y1 + leg, zA], [y1, zA + leg],
     [y1, zB - leg], [y1 + leg, zB], [y0 - leg, zB], [y0, zB - leg]];

// one side wall (sx = +1 / -1) with its jog windows
module side_wall(sx) {
    scale([sx, 1, 1])
        difference() {
            translate([half - wall_s, F, 0]) cube([wall_s, -F, WT]);
            for (k = [1:1:n_grooves]) hull() {
                prismX(jog_w(k*U, 0), half, half + hs);
                prismX(jog_w(k*U, 1), half - 1, half - 1 + hs);
            }
        }
}
// the inward-jogged side wall panels: the shell offset of the jog window (measured).
// The back corners are 45 degrees; the front corners are cut at about 52.4 degrees
// in plan (legs 3.308 in Z against 2.550 in Y at the base), and every edge carries
// the same 60 degree draft through the 1 mm panel thickness.
function jog_in(zk, d) =
    let (y0 = -4.732 - 1.732*d,      // the whole panel sits shifted +0.268 in Y
         y1 = F + 5.268 + 1.732*d,
         zA = zk - 8.768 + 1.732*d, zB = zk + 1.768 - 1.732*d,
         leg = 3.086 - 1.015*d,
         fz  = 3.308 - 1.142*d,
         fy  = 2.550 - 0.880*d)
    [[y0, zA + leg], [y0 - leg, zA], [y1 + fy, zA], [y1, zA + fz],
     [y1, zB - fz], [y1 + fy, zB], [y0 - leg, zB], [y0, zB - leg]];
module side_jog_panels() {
    for (sx = [-1, 1]) scale([sx, 1, 1])
        for (k = [1:1:n_grooves]) hull() {
            prismX(jog_in(k*U, 0), half - 1 - hs, half - 1);
            prismX(jog_in(k*U, 1), half - 2, half - 2 + hs);
        }
}

module front_wall() { translate([-half, F, 0]) cube([OW, wall_f, OH]); }
module floor_slab() { translate([-half, F, 0]) cube([OW, -F, floor_t]); }

// back corner braces: 1 mm arm leaning 45 degrees inward, with a flange along the side
module corner_braces() {
    for (sx = [-1, 1]) scale([sx, 1, 1]) intersection() {
        // leaning band (X,Z) extruded along Y
        // The band carries a short skirt 0.5 below the wall top, running exactly on
        // the wall's own two faces. Without it the leaning faces would meet the wall
        // faces edge-on at z = WT: the surfaces touch along a line instead of
        // crossing, and CGAL answers that with duplicated facets, which leaves the
        // exported mesh non-manifold at some depth and height combinations. Running
        // the skirt coplanar with the wall merges the two into one flat face instead.
        prismY([[half - (OH + 1 - WT), OH + 1], [half, WT], [half, WT - 0.5],
                [half - wall_s, WT - 0.5], [half - wall_s, WT],
                [half - wall_s - (OH + 1 - WT), OH + 1]],
               -(brace_len + 2), 0);
        // Bounded in Y by the flange end with its 45-degree chamfers. The profile runs
        // 1 below the wall top so the leaning band above does the clipping; ending it
        // exactly on WT made the two coincide and left a knife edge there, which
        // float32 binary STL export collapses into a non-manifold sliver.
        prismX([[1, WT - 1], [1, OH + 1], [-(brace_len - 2), OH + 1], [-brace_len, OH - 1],
                [-brace_len, WT + 1], [-(brace_len + 2), WT - 1]], 0, half);
    }
}

// ------------------------------------------------------------------ cutters

module cavity() {
    mainB = mag_on ? -4 : -2;   // rear boundary of the main cavity box
    translate([-(half - wall_s), F + wall_f, floor_t])
        cube([OW - 2*wall_s, -(F + wall_f) + mainB, OH + 10 - floor_t]);
    if (!mag_on) {
        translate([-(half - wall_s), -2, floor_t])
            cube([OW - 2*wall_s, 1, lean0 - floor_t]);
        prismX([[-1, lean0], [-2, lean1], [-2, lean0]],
               -(half - wall_s), half - wall_s);
    }
}
// solid fillet bar along X at wall face y = yw, bulging toward dir (re-added after cavity)
module fillet_barX(x0, x1, yw, dir) {
    translate([x0, yw, 0]) rotate([90, 0, 90]) linear_extrude(height = x1 - x0)
        difference() {
            polygon([[0, floor_t], [dir*fil_r, floor_t], [dir*fil_r, fil_cz], [0, fil_cz]]);
            translate([dir*fil_r, fil_cz]) circle(r = fil_r);
        }
}

// Back-wall finger scoop. On every original the flat ends 18.544 short of the side
// wall, which for whole-LU widths is identical to the outer cell centres +/-2.956.
// Driving it from the half-width instead reproduces those exactly and keeps the
// same shoulder on half-LU widths, where cell centres alone would leave the scoop
// 12.5 too narrow at each end.
module scoop_cut() {
    x1 = half - 18.544; x0 = -x1;
    rise = OH - WT + 2;
    prismY([[x0, WT], [x1, WT], [x1 + rise, WT + rise], [x0 - rise, WT + rise]], -7, 1);
}

module outer_edge_cuts() {
    // side bottom chamfers (5.272 legs)
    for (sx = [-1, 1]) scale([sx, 1, 1])
        prismY([[half - bot_ch - 1, -1], [half + 2, -1], [half + 2, bot_ch + 3], [half, bot_ch]],
               F - eps, eps);
    // back bottom chamfer (1)
    prismX([[0, 1], [2, 1], [2, -1], [-1, -1], [-1, 0]], -half - 1, half + 1);
    // Front bottom: 45-degree lead + r7 fillet across the finger-slot span, stopping
    // at the lip-gusset bands. Measured on the originals: the cut boundary follows
    // the gusset bands only, never the divider positions, so where a divider
    // overhangs its gusset the cut passes through it (see DEVIATIONS.md D5). At the
    // front wall's inner face the arc sits at z 1.701, so it takes about 0.1 off the
    // divider foot there and nothing deeper in.
    fb_stops = concat([-(half - 8.101)],
                      [for (b = cell_b) each [b - 1.7, b + 1.7]],
                      [half - 8.101]);
    for (i = [0:1:len(fb_stops)/2 - 1])
        prismX(front_bottom_cut(), fb_stops[2*i], fb_stops[2*i + 1]);
    // tilted hip chamfers where the 1 mm edge chamfers cross the 45-degree corner zones
    hip_cuts();
    // vertical corner chamfers (1 mm legs) at back and front-wall corners;
    // each cutter is a big triangle whose hypotenuse lies exactly on the chamfer face
    for (sx = [-1, 1]) scale([sx, 1, 1]) {
        translate([0, 0, -1]) linear_extrude(height = OH + 2)
            polygon([[half - 5, 4], [half + 8, 4], [half + 8, -9]]);
        translate([0, 0, -1]) linear_extrude(height = OH + 2)
            polygon([[half - 5, F - 4], [half + 8, F - 4], [half + 8, F + 9]]);
    }
    // top outer 1 mm chamfers: back wall edge (y=0) and front wall edge (y=F)
    prismX([[2, OH - 3], [2, OH + 3], [-1, OH + 3], [-1, OH], [0, OH - 1]], -half - 1, half + 1);
    prismX([[F - 3, OH + 3], [F - 3, OH - 3], [F, OH - 1], [F + 1, OH], [F + 1, OH + 3]],
           -half - 1, half + 1);
    // top corner chamfers (5.272 legs), full depth: front wall, back wall and braces
    for (sx = [-1, 1]) scale([sx, 1, 1])
        prismY([[half - bot_ch - 2, OH + 2], [half + 3, WT - 3], [half + 3, OH + 2]],
               F - 1, 1);
    // everything above OH
    translate([-half - 2, LIPF - 4, OH]) cube([OW + 4, -LIPF + 8, 10]);
}
function front_bottom_cut() =
    let (n = 32)
    concat([[F + 4.701, -1]],
           [for (i = [0:n]) let (a = -135 - i*45/n)
                [F + frt_r + frt_r*cos(a), fil_cz + frt_r*sin(a)]],
           [[F, -1]]);

// 1 mm corner-edge chamfers, tilted along the slanted corner edges of the
// bottom side chamfers and the top corner chamfers (normals (1,+/-2,1)/sqrt(6) family)
module hip_cuts() {
    ub = 0.7071 * (half - bot_ch);   // bottom corner edge, in the rotated frame
    ut = 0.7071 * (half + WT);       // top corner edge
    for (sx = [-1, 1]) scale([sx, 1, 1]) {
        // bottom edges run along (1,0,1); clipped at the wall faces, and at the
        // front also to outboard of the lip wing (which merges with no chamfer)
        intersection() {
            rotate([0, 45, 0]) linear_extrude(height = 2000, center = true)
                polygon([[ub - 1, F], [ub, F + 1], [ub + 9, F + 1], [ub + 9, F]]);
            translate([0, 0, -1]) linear_extrude(height = 20)
                polygon([[half - bot_ch, F], [half - bot_ch + 12, F + 12], [half + 20, F + 12],
                         [half + 20, F - 9], [half - bot_ch - 9, F - 9]]);
        }
        rotate([0, 45, 0]) linear_extrude(height = 2000, center = true)
            polygon([[ub - 1, 0], [ub, -1], [ub + 9, -1], [ub + 9, 0]]);
        // top edges run along (-1,0,1)
        rotate([0, -45, 0]) linear_extrude(height = 2000, center = true) {
            polygon([[ut - 1, F], [ut, F + 1], [ut + 9, F + 1], [ut + 9, F]]);
            polygon([[ut - 1, 0], [ut, -1], [ut + 9, -1], [ut + 9, 0]]);
        }
    }
}

// magnet pocket, one per cell center, cut into the back wall from y = 0
module magnet_pockets() { for (c = cell_c) translate([c, 0, 0]) magnet_pocket(); }
module magnet_pocket() {
    lower0 = [[-3.521, 7], [3.521, 7], [8.5, 11.979], [8.5, 19.021 + hs],
              [-8.5, 19.021 + hs], [-8.5, 11.979]];
    lower1 = [[-3.121, 6.6], [3.121, 6.6], [8.5, 11.979], [8.5, 19.021 + hs],
              [-8.5, 19.021 + hs], [-8.5, 11.979]];
    // upper region, split into two convex pieces so each 45-degree flare is exact:
    // A: shoulder wedge under the fixed 45-degree lines (shrinks with depth)
    A0  = [[-8.5, 19.021], [8.5, 19.021], [5.6, 21.921], [-5.6, 21.921]];
    A29 = [[-8.5, 19.021], [8.5, 19.021], [8.5, 19.022], [-8.5, 19.022]];
    // W: waist and top: constant for the first 0.4, then flaring 45 degrees
    W04 = [[-6.0, 21.521], [6.0, 21.521], [6.0, 23.986], [2.486, 27.5], [-2.486, 27.5], [-6.0, 23.986]];
    W29 = [[-8.5, 19.02], [8.5, 19.02], [8.5, 25.021], [3.521, 30], [-3.521, 30], [-8.5, 25.021]];
    prismY(lower0, -3.2, 1);                                  // straight entry body
    hull() { prismY(lower0, -1.8 - hs, -1.8); prismY(lower1, -2.2, -2.2 + hs); }
    prismY(lower1, -3.2, -2.2);
    prismY(A0, 0, 1);
    hull() { prismY(A0, 0, hs); prismY(A29, -2.9 - hs, -2.9); }
    prismY(W04, -0.4, 1);
    hull() { prismY(W04, -0.4 - hs, -0.4); prismY(W29, -2.9, -2.9 + hs); }
    prismY(W29, -3.2, -2.9);
}

// ------------------------------------------------------------------ interior adds

module floor_blends() {
    intersection() {
        union() {
            fillet_barX(-(half - wall_s), half - wall_s, -wall_b, -1);
            fillet_barX(-(half - wall_s), half - wall_s, F + wall_f, 1);
            prismY([[-(half - wall_s), fil_cz - fil_r + side_ch], [-(half - wall_s), floor_t],
                    [-(half - wall_s) + side_ch, floor_t]], F + wall_f, -wall_b);
            prismY([[half - wall_s, fil_cz - fil_r + side_ch], [half - wall_s, floor_t],
                    [half - wall_s - side_ch, floor_t]], F + wall_f, -wall_b);
            // small vertical chamfers in the cavity corners (0.414 back, 0.4 front legs),
            // fading out toward the floor blends below z = 6.6;
            // the thick magnetic back wall has square corners in the originals
            for (sx = [-1, 1]) scale([sx, 1, 1]) {
                // Back corner: the 0.414-leg chamfer web runs to the wall top, and its
                // bottom is cut off by the fade plane (normal (0.5, 0.7071, -0.5)
                // through the outer corner at z 6.286), below which the floor blends
                // take over. Both are measured off the originals.
                if (!mag_on) {
                    intersection() {   // the chamfer web, its foot cut by the fade plane
                        linear_extrude(height = WT)
                            polygon([[half - wall_s + 0.5, -wall_b + 0.5],
                                     [half - wall_s - 0.914, -wall_b + 0.5],
                                     [half - wall_s + 0.5, -wall_b - 0.914]]);
                        below_plane([half - wall_s, -wall_b - 0.414, 6.286],
                                    [0.5, 0.7071, -0.5], [0.7071, 0, 0.7071], [0.5, -0.7071, -0.5]);
                    }
                    intersection() {   // and the square corner fill beneath that plane
                        below_plane([half - wall_s, -wall_b - 0.414, 6.286],
                                    [-0.5, -0.7071, 0.5], [0.7071, 0, 0.7071], [-0.5, 0.7071, 0.5]);
                        translate([half - wall_s - 3.4, -wall_b - 3.4, 3.8])
                            cube([3.4 + 1, 3.4 + 1, 3.2]);
                    }
                }
                // Front corner: a 0.4-leg web above z 6.6 with a near-vertical fade
                // band below it (the originals twist this face slightly as it descends).
                translate([0, 0, fil_cz]) linear_extrude(height = WT - fil_cz)
                    polygon([[half - wall_s + 0.5, F + wall_f - 0.5],
                             [half - wall_s - 0.9, F + wall_f - 0.5],
                             [half - wall_s + 0.5, F + wall_f + 0.9]]);
                intersection() {
                    below_plane([half - wall_s, F + 2.411, 6.286], [-0.708, 0.704, 0.045],
                                [0.704, 0.708, 0], [-0.03186, 0.03168, -0.99688]);
                    translate([half - wall_s - 1.6, F + wall_f - 1, 5.6])
                        cube([1.6 + 1, 1 + 2.4, 1.02]);
                }
            }
        }
        translate([-half, F, 0]) cube([OW, -F, OH]);
    }
}

module dividers() {
    cavL = -(half - wall_s); cavR = half - wall_s;
    cavB = -wall_b; cavF = F + wall_f;
    // everything is clipped to the cavity so fillet bars cannot escape the walls
    intersection() {
    translate([cavL, cavF, 0]) cube([cavR - cavL, cavB - cavF, OH]);
    difference() {
    union() {
    if (w_div) {
        for (xl = divider_x()) {
            translate([xl, cavF, 0]) cube([div_t, cavB - cavF, div_top]);
            translate([xl, 0, 0])         divider_filletY(cavF, cavB, -1);
            translate([xl + div_t, 0, 0]) divider_filletY(cavF, cavB, 1);
            // end flares; at the back they follow the wall as it leans to 2 mm
            translate([xl + div_t/2, cavF, 0]) linear_extrude(height = div_top)
                polygon([[-div_t/2 - 0.5, 0], [div_t/2 + 0.5, 0],
                         [div_t/2, 0.5], [-div_t/2, 0.5]]);
            // the magnetic back wall is flat, so its flare runs the full height;
            // a leaning wall carries the flare back with it above lean0
            translate([xl + div_t/2, cavB, 0])
                linear_extrude(height = mag_on ? div_top : min(div_top, lean0))
                polygon([[-div_t/2 - 0.5, 0], [div_t/2 + 0.5, 0],
                         [div_t/2, -0.5], [-div_t/2, -0.5]]);
            if (!mag_on && div_top > lean1) {
                translate([xl + div_t/2, cavB - 1, lean1]) linear_extrude(height = div_top - lean1)
                    polygon([[-div_t/2 - 0.5, 0], [div_t/2 + 0.5, 0],
                             [div_t/2, -0.5], [-div_t/2, -0.5]]);
                hull() {   // transition along the 1:4 lean
                    translate([xl + div_t/2, cavB, lean0]) linear_extrude(height = eps)
                        polygon([[-div_t/2 - 0.5, 0], [div_t/2 + 0.5, 0],
                                 [div_t/2, -0.5], [-div_t/2, -0.5]]);
                    translate([xl + div_t/2, cavB - 1, lean1]) linear_extrude(height = eps)
                        polygon([[-div_t/2 - 0.5, 0], [div_t/2 + 0.5, 0],
                                 [div_t/2, -0.5], [-div_t/2, -0.5]]);
                }
            }
        }
    }
    if (d_div) {
        // each depth divider has its back face on its division line (see depth_lines)
        for (line = depth_lines(d_ratio)) {
            yf = line - div_t;                  // front face of this divider
            translate([cavL, yf, 0]) cube([cavR - cavL, div_t, div_top]);
            translate([0, yf, 0])         divider_barX(cavL, cavR, -1);
            translate([0, yf + div_t, 0]) divider_barX(cavL, cavR, 1);
            for (xw = [cavL, cavR]) {
                dx = (xw == cavL) ? 1 : -1;
                translate([xw, yf + div_t/2, 0]) linear_extrude(height = div_top)
                    polygon([[0, -div_t/2 - 0.5], [0, div_t/2 + 0.5],
                             [dx*0.5, div_t/2], [dx*0.5, -div_t/2]]);
            }
        }
    }
    }   // union
    divider_scoops();
    }   // difference
    }   // cavity clip
}

// ---- finger scoops: cuts in the tops of the dividers. Every cut has 45-degree
// walls and removes material from the top only, so it adds no overhang. A scoop
// never reaches down into the dividers' floor fillets.
scoop_d = min(max(2, divider_scoop_mm), div_top - fil_cz);
// how far the leaning back wall stands in at the height of the divider tops
// (the magnet wall does not lean)
back_in = mag_on ? 0 : min(1, max(0, (div_top - lean0)/(lean1 - lean0)));
// The stretches of a width divider between crossings, front to back, each as
// [from, to]: from the front wall or a depth divider's back face, to the next
// depth divider's front face or the back wall where the divider tops meet it.
function stretches_y() =
    let (ys = d_div ? depth_lines(d_ratio) : [])
    [for (k = [0:1:len(ys)]) [k == 0 ? F + wall_f : ys[k - 1], k == len(ys) ? -wall_b - back_in : ys[k] - div_t]];
// the stretches of a depth divider between crossings, left to right
function stretches_x() =
    let (xs = divider_x())
    [for (k = [0:1:len(xs)]) [k == 0 ? -(half - wall_s) : xs[k - 1] + div_t, k == len(xs) ? half - wall_s : xs[k]]];
// Depth of the centre notch that fits a stretch, or 0 when none does. A notch is
// three times as wide at the top as it is deep, and leaves 2 mm of full-height
// divider at each end of its stretch.
function notch_depth(s) = let (d = min(scoop_d, (s[1] - s[0] - 4)/3)) d >= 2 ? d : 0;
// Run of the front slope, or 0 when none fits. It ends 2 mm before the end of
// the front stretch, which is a depth divider or the back wall.
function front_run() =
    let (s = stretches_y()[0], r = min(scoop_d, s[1] - s[0] - 2)) r >= 2 ? r : 0;
// outline of a notch d deep centred on m along a divider, against height; its
// sides run on past the divider top, so no corner of the cut lies in that face
function scoop_notch(m, d) =
    [[m - d/2, div_top - d], [m + d/2, div_top - d], [m + 1.5*d + 1, div_top + 1], [m - 1.5*d - 1, div_top + 1]];

scoop_cuts = divider_scoop == "front"  ? (w_div ? [front_run()] : []) :
             divider_scoop == "center" ? concat(w_div ? [for (s = stretches_y()) notch_depth(s)] : [],
                                                d_div ? [for (s = stretches_x()) notch_depth(s)] : []) : [];
if (!(divider_scoop == "none" || divider_scoop == "front" || divider_scoop == "center"))
    echo("WARNING: divider_scoop must be none, front or center; no scoop is cut.");
else if (divider_scoop != "none" && (len(scoop_cuts) == 0 || max(scoop_cuts) == 0))
    echo("NOTE: divider_scoop cuts nothing in this drawer: it has no divider long enough and tall enough for that scoop.");
else if (divider_scoop != "none" && min(scoop_cuts) < divider_scoop_mm)
    echo("NOTE: the divider scoop is shallower than divider_scoop_mm, or left out, where a divider is too low or a compartment too short for it.");

module divider_scoops() {
    side = 0.75;        // a cut reaches this far past a divider's faces, to take its 0.5 mm end flares with it
    if (divider_scoop == "front" && w_div) {
        // the top of each width divider slopes down toward the front wall
        run = front_run();
        cavF = F + wall_f;
        if (run > 0) for (xl = divider_x())
            prismX([[cavF - 1, div_top - run - 1], [cavF + run + 1, div_top + 1], [cavF - 1, div_top + 1]],
                   xl - side, xl + div_t + side);
    }
    if (divider_scoop == "center") {
        // one notch in each stretch of a divider: a flat bottom as long as the
        // notch is deep, under 45-degree sides
        if (w_div) for (xl = divider_x(), s = stretches_y())
            let (d = notch_depth(s))
            if (d > 0) prismX(scoop_notch((s[0] + s[1])/2, d), xl - side, xl + div_t + side);
        if (d_div) for (line = depth_lines(d_ratio), s = stretches_x())
            let (d = notch_depth(s))
            if (d > 0) prismY(scoop_notch((s[0] + s[1])/2, d), line - div_t - side, line + side);
    }
}
module divider_barX(x0, x1, dir) {
    rotate([90, 0, 90]) translate([0, 0, x0]) linear_extrude(height = x1 - x0)
        difference() {
            polygon([[0, floor_t], [dir*fil_r, floor_t], [dir*fil_r, fil_cz], [0, fil_cz]]);
            translate([dir*fil_r, fil_cz]) circle(r = fil_r);
        }
}
module divider_filletY(y0, y1, dir) {
    translate([0, y1, 0]) rotate([90, 0, 0]) linear_extrude(height = y1 - y0)
        difference() {
            polygon([[0, floor_t], [dir*fil_r, floor_t], [dir*fil_r, fil_cz], [0, fil_cz]]);
            translate([dir*fil_r, fil_cz]) circle(r = fil_r);
        }
}

// ------------------------------------------------------------------ exterior adds

// pull lip: floating plate, 45-degree wings, gussets at cell boundaries
module lip_ring2d() {
    difference() {
        polygon([[-(half - 3.272), F + 2], [half - 3.272, F + 2],
                 [half - 13.272, LIPF], [-(half - 13.272), LIPF]]);
        polygon([[-(half - 6.101), F + 2 + eps], [half - 6.101, F + 2 + eps],
                 [half - 14.101, LIPF + 2], [-(half - 14.101), LIPF + 2]]);
    }
}
module lip() {
    // plate: low profile with the 22.5-degree back slope (clipped at z = 0);
    // the wing planes also clip the plate band's outer corners
    intersection() {
        linear_extrude(height = 10) lip_ring2d();
        prismX([[LIPF - 0.2, 0], [LIPF - 0.2, 5.072], [LIPF + 0.869, 6.141],
                [LIPF + 0.869 + 6.141/0.4142, 0]],
               -half - 1, half + 1);
        below_plane([half, F, 6.772], [1, -2, 1], [1, 0, -1], [2, 1, 0]);
        scale([-1, 1, 1]) below_plane([half, F, 6.772], [1, -2, 1], [1, 0, -1], [2, 1, 0]);
    }
    // wings: their top is a single slanted plane, normal (1,-2,1)/sqrt(6),
    // through the point (half, F, 6.772) (measured on the originals)
    for (sx = [-1, 1]) scale([sx, 1, 1]) intersection() {
        linear_extrude(height = 20) lip_ring2d();
        // outboard of the finger-slot wall line (45 degrees in plan)
        translate([0, 0, -1]) linear_extrude(height = 22)
            polygon([[half - 5.101, F + 3], [half + 20, F + 3],
                     [half + 20, LIPF - 3], [half - 19.101, LIPF - 3],
                     [half - 14.101, LIPF + 2]]);
        below_plane([half, F, 6.772], [1, -2, 1], [1, 0, -1], [2, 1, 0]);
        // capped by the 45-degree plane rising from the plate's front-top edge
        below_plane([0, F, 13.272], [0, -1, 1], [1, 0, 0], [0, 1, 1]);
    }
    // gussets at internal cell boundaries: a 1.4-wide ridge band rising at
    // 45 degrees from the plate top front edge to the wall face, with
    // sqrt(2)-slope flank chamfers down to the gusset side walls
    for (b = cell_b) translate([b, 0, 0]) intersection() {
        prismX([[LIPF, 0], [LIPF, 25], [F + 2, 25], [F + 2, 0]], -1.7, 1.7);
        below_plane([0, F, 13.272], [0, -1, 1], [1, 0, 0], [0, 1, 1]);
        below_plane([0.7, F, 13.272], [1.414, -1, 1], [0, 1, 1], [-2, -1.414, 1.414]);
        below_plane([-0.7, F, 13.272], [-1.414, -1, 1], [0, 1, 1], [2, -1.414, 1.414]);
    }
}
// Half-space below the plane through p with normal n (e1, e2 span the plane).
// The box stands in for an infinite half-space, so it is sized from the model
// rather than fixed; a fixed box silently truncates features on large drawers.
bp = 2*(OW + abs(LIPF) + OH) + 200;
module below_plane(p, n, e1, e2) {
    multmatrix([[e1[0], e2[0], n[0], p[0]],
                [e1[1], e2[1], n[1], p[1]],
                [e1[2], e2[2], n[2], p[2]]])
        translate([-bp, -bp, -2*bp]) cube([2*bp, 2*bp, 2*bp]);
}

// side detent bumps on the bottom outer chamfers, near the front.
// Measured: the hull of a face trapezoid (on the plane |x| = half - 1.575)
// and a shelf trapezoid (at z = 1.575, lying on the chamfer). The originals
// carry two variants; the face bottom is 2.282 on 1-LU-tall multi-wide
// drawers and 2.565 everywhere else (see DEVIATIONS.md).
bump_zb = (H == 1 && W >= 2) ? 2.282 : 2.565;
bump_hw = 0.5 + (3.697 - bump_zb) * 0.7071;   // shelf/face top half-length
module detent_bumps() {
    for (sx = [-1, 1]) scale([sx, 1, 1]) hull() {
        // face trapezoid, thin in X (outer face exactly at half - 1.575)
        translate([half - 1.575 - hs, 0, 0]) rotate([90, 0, 90])
            linear_extrude(height = hs) polygon(
                [[F + 2.5, bump_zb], [F + 3.5, bump_zb],
                 [F + 3 + bump_hw, 3.697], [F + 3 - bump_hw, 3.697]]);
        // shelf trapezoid, thin in Z (shelf exactly at z = 1.575)
        translate([0, 0, 1.575]) linear_extrude(height = hs) polygon(
            [[half - bump_zb, F + 2.5], [half - bump_zb, F + 3.5],
             [half - 3.697, F + 3 + bump_hw], [half - 3.697, F + 3 - bump_hw]]);
    }
}

// label holder frame on the front face
module label_frame() {
    hb0 = OH - 20.9;   // hook underside chamfer start (on the wall face)
    hf0 = OH - 19.3;   // hook front face bottom
    hf1 = OH - 17.7;   // hook front face top = window bottom
    sf  = OH - 18.75;  // card slot floor
    rt  = OH - 4.9;    // rail top at the wall face (a single 45-degree chamfer from here)
    lt  = OH - 6.5;    // window ledge top
    difference() {
        union() {
            // bottom hook band, full frame width
            prismX([[F, hb0], [F - lab_p, hf0], [F - lab_p, hf1], [F - 0.8, hf1],
                    [F - 0.8, sf], [F, sf]], -lab_foot, lab_foot);
            // side rails (both layers, pre-chamfer)
            for (sx = [-1, 1]) scale([sx, 1, 1]) {
                translate([lab_chan, F - 0.8, sf]) cube([lab_foot - lab_chan, 0.8, rt - sf]);
                translate([lab_win, F - lab_p, sf]) cube([lab_foot - lab_win, lab_p - 0.8, rt - sf]);
            }
        }
        // outboard 45-degree plan chamfers
        for (sx = [-1, 1]) scale([sx, 1, 1])
            translate([0, 0, hb0 - 3]) linear_extrude(height = OH)
                polygon([[lab_foot + 1, F + 1], [lab_foot + 7, F + 1],
                         [lab_foot + 7, F - 6], [lab_foot - 6, F - 6]]);
        // Rail top chamfer: 45 degrees down toward the front, hinged at the wall face.
        // The cutter is extended along its own face line rather than offset by eps,
        // which would tilt the visible chamfer plane.
        prismX([[F + 1, rt + 1], [F - 4, rt - 4], [F - 4, rt + 8], [F + 1, rt + 8]],
               -lab_foot - 1, lab_foot + 1);
        // window ledge caps, stopping exactly on the card channel wall
        for (sx = [-1, 1]) scale([sx, 1, 1])
            translate([lab_win - eps, F - lab_p - 1, lt]) cube([lab_chan - lab_win + eps, lab_p + 1 - 0.8, OH]);
        // card channel
        translate([-lab_chan, F - 0.8, sf]) cube([2*lab_chan, 0.8 + eps, OH]);
        // window opening
        translate([-lab_win, F - lab_p - 1, hf1]) cube([2*lab_win, lab_p + 1 - 0.8 + eps, OH]);
    }
}

// ------------------------------------------------------------------ assembly

module drawer() {
    union() {
        difference() {
            union() {
                difference() {
                    union() {
                        floor_slab();
                        side_wall(1); side_wall(-1);
                        back_wall();
                        front_wall();
                    }
                    cavity();
                    scoop_cut();
                }
                corner_braces();   // lean over the cavity, so they go in after the cavity cut
                groove_bumps();    // ditto: jogged panels sit inside the cavity envelope
                side_jog_panels();
                floor_blends();
                dividers();
                lip();             // shaped by the outer edge cuts (wing roots get chamfered)
            }
            outer_edge_cuts();
            if (mag_on) magnet_pockets();
        }
        if (lab_on) label_frame();
        detent_bumps();
    }
}

drawer();
