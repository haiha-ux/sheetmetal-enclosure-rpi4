"""Body and lid as true sheet-metal solids (planar faces + cylindrical bends), their flat patterns,
and the refold map that takes a flat point back to 3D.

Side frame: u = distance outward from the wall inner plane, s = along the edge, z up.
Sides: "x0" (wall at x = 0), "x1" (x = L), "y0" (y = 0), "y1" (y = W).
"""
import math

from build123d import (Align, Axis, Box, Cylinder, Polygon, Pos, Rectangle, Rot, extrude, Face, Location)

import params as P

A0 = (Align.MIN, Align.MIN, Align.MIN)
r, T = P.R_IN, P.T
SIDES = {  # normal axis, outward sign, wall inner coordinate, edge span
    "x0": ("x", -1, 0.0, P.W), "x1": ("x", 1, P.L, P.W),
    "y0": ("y", -1, 0.0, P.L), "y1": ("y", 1, P.W, P.L),
}


def box(x0, x1, y0, y1, z0, z1):
    xs, ys, zs = sorted((x0, x1)), sorted((y0, y1)), sorted((z0, z1))
    return Pos(xs[0], ys[0], zs[0]) * Box(xs[1] - xs[0], ys[1] - ys[0], zs[1] - zs[0], align=A0)


def g(side, u, s):
    """Side (u, s) -> global (x, y)."""
    ax, n, pos, _ = SIDES[side]
    return (pos + n * u, s) if ax == "x" else (s, pos + n * u)


def sbox(side, u0, u1, s0, s1, z0, z1):
    (xa, ya), (xb, yb) = g(side, u0, s0), g(side, u1, s1)
    return box(xa, xb, ya, yb, z0, z1)


def bend(side, uc, zc, s0, s1, quad_u, quad_z):
    """Quarter tube r..r+T about an edge-parallel axis at (uc, zc), kept inside the (u, z) quadrant box."""
    ax = SIDES[side][0]
    length = s1 - s0
    tube = Cylinder(r + T, length) - Cylinder(r, length)
    if ax == "x":        # edge along y
        tube = Rot(-90, 0, 0) * tube        # cylinder axis z -> y
        cx, _ = g(side, uc, 0)
        tube = Pos(cx, (s0 + s1) / 2, zc) * tube
    else:                # edge along x
        tube = Rot(0, 90, 0) * tube         # axis z -> x
        _, cy = g(side, uc, 0)
        tube = Pos((s0 + s1) / 2, cy, zc) * tube
    return tube & sbox(side, quad_u[0], quad_u[1], s0, s1, quad_z[0], quad_z[1])


def plan_prism(side, pts_us, z0, z1):
    return Pos(0, 0, z0) * extrude(fpoly(side, pts_us), z1 - z0)   # CCW face, so it extrudes up


# ------------------------------------------------------------------ body
def wall_flat():
    return P.H - 2 * T - 2 * r


def flange_flat():
    return P.F - r


def body_solid():
    L, W, H, F = P.L, P.W, P.H, P.F
    sb = P.BEND_SETBACK
    b = box(r, L - r, r, W - r, 0, T)
    for side, (ax, n, pos, E) in SIDES.items():
        b += bend(side, -r, T + r, r + sb, E - r - sb, (-r, T), (0, T + r))
        b += sbox(side, 0, T, r + sb, E - r - sb, T + r, H - T - r)
        b += bend(side, T + r, H - T - r, r + sb, E - r - sb, (0, T + r), (H - T - r, H))
        u0, u1 = T + r, T + F
        b += plan_prism(side, [(u0, -u0), (u1, -u1), (u1, E + u1), (u0, E + u0)], H - T, H)
    for sl in relief_slots("body"):
        b -= Pos(0, 0, -1) * extrude(sl, T + 2)
    return b


def relief_slots(part):
    """Bend reliefs at the 4 corners: a slot BEND_SETBACK wide and RELIEF_DEPTH deep into the base or plate,
    beside each end of each bend (relief width >= T/2, depth >= T + r + 0.5 past the bend)."""
    sb, rd = P.BEND_SETBACK, P.RELIEF_DEPTH
    out = []
    for side, (ax, n, pos, E) in SIDES.items():
        if part == "body":
            e0, s0, s1 = -r, r, E - r
        else:
            a = lid_geom()[0] - r
            e0, s0, s1 = a, -a, E + a
        for a_, b_ in ((s0, s0 + sb), (s1 - sb, s1)):
            out.append(fpoly(side, [(e0 - rd, a_), (e0, a_), (e0, b_), (e0 - rd, b_)]))
    return out


def lid_geom():
    u_si = T + P.F + P.LID_GAP_SKIRT                  # skirt inner face
    gap = P.GASKET["free_t"] * (1 - P.GASKET["compression"])
    zl = P.H + gap                                    # lid underside
    zsb = P.H - T - P.LID_SKIRT_BELOW                 # skirt bottom
    return u_si, zl, zsb, gap


def lid_solid():
    L, W = P.L, P.W
    u_si, zl, zsb, _ = lid_geom()
    a = u_si - r
    sb = P.BEND_SETBACK
    b = box(-a, L + a, -a, W + a, zl, zl + T)
    for side, (ax, n, pos, E) in SIDES.items():
        b += bend(side, u_si - r, zl - r, -a + sb, E + a - sb, (u_si - r, u_si + T), (zl - r, zl + T))
        b += sbox(side, u_si, u_si + T, -a + sb, E + a - sb, zsb, zl - r)
    for sl in relief_slots("lid"):
        b -= Pos(0, 0, zl - 1) * extrude(sl, T + 2)
    return b


# ------------------------------------------------------------------ features (holes)
def holes():
    """Every hole: dict(part, kind, d, centre3d, axis, side|None, flat)."""
    L, W, H = P.L, P.W, P.H
    out = []
    ox, oy = P.RPI_ORIGIN
    for hx, hy in P.RPI["holes"]:
        out.append(dict(part="body", kind=P.STUD["name"] + " stud", d=P.STUD["hole"],
                        c=(ox + hx, oy + hy, T / 2), axis="z", side=None))
    uh = T + P.FLANGE_HOLE_FROM_WALL
    for side, (ax, n, pos, E) in SIDES.items():
        for s in (P.FLANGE_HOLES_Y if ax == "x" else P.FLANGE_HOLES_X):
            x, y = g(side, uh, s)
            out.append(dict(part="body", kind="PEM CLS-M4-1 nut", d=P.PEM_NUT["hole"], c=(x, y, H - T / 2), axis="z", side=side))
            out.append(dict(part="lid", kind="M4 clearance", d=P.LID_HOLE_D, c=(x, y, lid_geom()[1] + T / 2), axis="z", side=side))
    # glands: Ethernet cable on the x = L wall in line with the jack, USB-C power on the y = 0 wall in line with the plug
    eth_y = oy + 45.75
    out.append(dict(part="body", kind=P.GLAND_M16["name"], d=P.GLAND_M16["hole"], c=(L + T / 2, eth_y, P.GLAND_M16_Z),
                    axis="x", side="x1"))
    usb_x = ox + 11.2
    out.append(dict(part="body", kind=P.GLAND_PG7["name"], d=P.GLAND_PG7["hole"], c=(usb_x, -T / 2, P.GLAND_PG7_Z),
                    axis="y", side="y0"))
    return out


def cut_holes(solid, part):
    for h in holes():
        if h["part"] != part:
            continue
        x, y, z = h["c"]
        c = Cylinder(h["d"] / 2, 20)
        if h["axis"] == "x":
            c = Rot(0, 90, 0) * c
        elif h["axis"] == "y":
            c = Rot(-90, 0, 0) * c
        solid -= Pos(x, y, z) * c
    return solid


# ------------------------------------------------------------------ flat patterns
def body_flat_regions():
    """2D faces of the body flat pattern, in the base plane frame (same x, y as the base)."""
    L, W = P.L, P.W
    BA = P.ba(90)
    sb = P.BEND_SETBACK
    base = Pos((L) / 2, (W) / 2) * Rectangle(L - 2 * r, W - 2 * r)
    for sl in relief_slots("body"):
        base = base - sl
    faces = [base]
    for side, (ax, n, pos, E) in SIDES.items():
        u_edge = -r                                # base flat edge, in u
        v_wall_end = 2 * BA + wall_flat()
        faces.append(fpoly(side, [(u_edge, r + sb), (u_edge + v_wall_end, r + sb), (u_edge + v_wall_end, E - r - sb), (u_edge, E - r - sb)]))
        # flange: flat u' = u_edge + v ; 3D u = T + r + (v - v_wall_end); miter s >= -u3d
        v0, v1 = v_wall_end, v_wall_end + flange_flat()
        u3 = lambda v: T + r + (v - v0)
        faces.append(fpoly(side, [(u_edge + v0, -u3(v0)), (u_edge + v1, -u3(v1)), (u_edge + v1, E + u3(v1)), (u_edge + v0, E + u3(v0))]))
    return faces


def lid_flat_regions():
    L, W = P.L, P.W
    u_si, zl, zsb, _ = lid_geom()
    a = u_si - r
    BA = P.ba(90)
    skirt_flat = (zl - r) - zsb
    sb = P.BEND_SETBACK
    plate = Pos(L / 2, W / 2) * Rectangle(L + 2 * a, W + 2 * a)
    for sl in relief_slots("lid"):
        plate = plate - sl
    faces = [plate]
    for side, (ax, n, pos, E) in SIDES.items():
        faces.append(fpoly(side, [(a, -a + sb), (a + BA + skirt_flat, -a + sb), (a + BA + skirt_flat, E + a - sb), (a, E + a - sb)]))
    return faces


def fpoly(side, pts_us):
    pts = [g(side, u, s) for u, s in pts_us]
    area2 = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    return Polygon(*(pts if area2 > 0 else pts[::-1]), align=None)   # CCW, so every piece faces +z and fuses


def bend_lines(part):
    """One line per bend at the middle of its zone in the flat: (side, (x0, y0), (x1, y1), angle, direction, length)."""
    BA = P.ba(90)
    out = []
    if part == "body":
        for side, (ax, n, pos, E) in SIDES.items():
            for v, d in ((BA / 2, "UP 90"), (BA + wall_flat() + BA / 2, "DOWN 90")):
                sb = P.BEND_SETBACK
                out.append((side, g(side, -r + v, r + sb), g(side, -r + v, E - r - sb), 90.0, d, E - 2 * r - 2 * sb))
    else:
        u_si, zl, zsb, _ = lid_geom()
        a = u_si - r
        for side, (ax, n, pos, E) in SIDES.items():
            sb = P.BEND_SETBACK
            out.append((side, g(side, a + BA / 2, -a + sb), g(side, a + BA / 2, E + a - sb), 90.0, "DOWN 90", E + 2 * a - 2 * sb))
    return out


def flat_point(h):
    """Flat (x, y) of a hole centre, computed from its 3D position (the unfold map)."""
    x, y, z = h["c"]
    BA = P.ba(90)
    if h["axis"] == "z" and h["side"] is None:
        return x, y                                       # base or lid plate: unchanged
    side = h["side"]
    ax, n, pos, E = SIDES[side]
    u3 = (x - pos) * n if ax == "x" else (y - pos) * n
    s = y if ax == "x" else x
    if h["part"] == "lid":
        return x, y                                       # lid holes are all in the plate
    if h["axis"] == "z":                                  # body flange
        v = 2 * BA + wall_flat() + (u3 - (T + r))
    else:                                                 # body wall
        v = BA + (z - (T + r))
    return g(side, -r + v, s)


def refold_point(part, xy, side_hint=None):
    """Flat (x, y) -> 3D centre-plane point. The inverse of flat_point, written from the bend sequence."""
    BA = P.ba(90)
    x, y = xy
    if part == "lid":
        return x, y, lid_geom()[1] + T / 2
    for side, (ax, n, pos, E) in SIDES.items():
        u = (x - pos) * n if ax == "x" else (y - pos) * n
        s = y if ax == "x" else x
        v = u + r                                        # distance beyond the base flat edge
        if v <= 0:
            continue
        if side_hint and side != side_hint:
            continue
        if v < BA:
            raise ValueError("point in a bend zone")
        if v <= BA + wall_flat():                          # wall: u3 = T/2, z grows with v
            u3, z = T / 2, T + r + (v - BA)
        elif v < 2 * BA + wall_flat():
            raise ValueError("point in a bend zone")
        else:                                            # flange
            u3, z = T + r + (v - 2 * BA - wall_flat()), P.H - T / 2
        gx, gy = g(side, u3, s)
        return gx, gy, z
    return x, y, T / 2
