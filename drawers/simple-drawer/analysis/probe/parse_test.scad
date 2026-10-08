// Probe: can OpenSCAD 2021.01 parse "2,1,1.5" into numbers with only builtins?
DIG = "0123456789";

function _dv(c) = let (h = search(c, DIG)) len(h) == 0 ? -1 : h[0];

// number starting at i; returns [value, next_index]
function _num(s, i, acc = 0, seen = false, frac = 0) =
    i >= len(s) ? [seen ? acc : undef, i] :
    let (d = _dv(s[i]))
    d >= 0 ? (frac == 0 ? _num(s, i+1, acc*10 + d, true, 0)
                        : _num(s, i+1, acc + d*frac, true, frac/10)) :
    (s[i] == "." && frac == 0) ? _num(s, i+1, acc, seen, 0.1) :
    [seen ? acc : undef, i];

function _scan(s, i = 0, out = []) =
    i >= len(s) ? out :
    let (r = _num(s, i))
    r[0] == undef ? _scan(s, i+1, out) : _scan(s, r[1], concat(out, [r[0]]));

function parse_nums(s) = _scan(s);

echo(A = parse_nums("2,1,1.5"));
echo(B = parse_nums(" 3 , 0.25,10 "));
echo(C = parse_nums(""));
echo(D = parse_nums("junk"));
echo(E = parse_nums("1,,2"));
echo(F = parse_nums("1.25"));
echo(G = parse_nums("0.5,0.5,0.5,0.5"));
cube(1);
