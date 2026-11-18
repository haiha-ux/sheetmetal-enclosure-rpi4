"""Fabrication drawings (DXF, A3, 1:2): body flat, lid flat (bend + hole tables), assembly with BOM.
python drawing/drawing.py  (build123d venv)   then  Python311 drawing/to_pdf.py
Geometry is read back from out/*_flat.dxf and out/*.step; every value printed comes from those files or params.
"""
import datetime
import json
import sys
from pathlib import Path

import ezdxf
from build123d import import_step

ROOT = Path(__file__).resolve().parents[1]
OUT, DWG = ROOT / "out", ROOT / "drawing"
sys.path.insert(0, str(ROOT / "sm"))
import params as P  # noqa: E402

SC = 0.5   # 1:2


def setup(doc):
    doc.units = ezdxf.units.MM
    for n, c, lt in (("VISIBLE", 7, "CONTINUOUS"), ("HIDDEN", 8, "DASHED"), ("BEND", 1, "DASHED"), ("DIM", 1, "CONTINUOUS"),
                     ("FRAME", 7, "CONTINUOUS"), ("TEXT", 7, "CONTINUOUS")):
        doc.layers.add(n, color=c, linetype=lt)
    ds = doc.dimstyles.new("ISO2")
    ds.dxf.dimtxt, ds.dxf.dimasz, ds.dxf.dimexe, ds.dxf.dimexo, ds.dxf.dimgap = 2.5, 2.5, 1.0, 0.8, 0.8
    ds.dxf.dimdec, ds.dxf.dimtad, ds.dxf.dimzin, ds.dxf.dimlfac = 2, 1, 8, 1 / SC
    ds.dxf.dimdsep = ord(".")
    doc.styles.add("ISO", font="isocpeur.ttf")
    ds.dxf.dimtxsty = "ISO"


def txt(msp, s, at, h=2.5):
    msp.add_text(s, height=h, dxfattribs={"layer": "TEXT", "style": "ISO"}).set_placement(at)


def frame(msp, title, notes):
    W, H = 420, 297
    msp.add_lwpolyline([(0, 0), (W, 0), (W, H), (0, H)], close=True, dxfattribs={"layer": "FRAME"})
    msp.add_lwpolyline([(20, 10), (W - 10, 10), (W - 10, H - 10), (20, H - 10)], close=True, dxfattribs={"layer": "FRAME"})
    x0 = W - 190
    msp.add_lwpolyline([(x0, 10), (W - 10, 10), (W - 10, 46), (x0, 46)], close=True, dxfattribs={"layer": "FRAME"})
    for i, (t, h) in enumerate(((title, 4.5), (f"Material: {P.MATERIAL}, t = {P.T} mm   Inside bend radius {P.R_IN}   K = {P.K}", 2.5),
                                ("Scale 1:2   Units mm   Sheet A3   Third-angle   General tol. ISO 2768-m", 2.5),
                                (f"Drawn: Ha Phan Thanh Hai   {datetime.date.today().isoformat()}", 2.5))):
        txt(msp, t, (x0 + 3, 38 - 8 * i), h)
    y = H - 20
    for i, n in enumerate(notes, 1):
        txt(msp, f"{i}. {n}", (x0 - 10, y), 2.3)
        y -= 4.6


def dim(msp, p1, p2, base, angle=0):
    d = msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dimstyle="ISO2", dxfattribs={"layer": "DIM"})
    d.render()


def flat_sheet(part, title, origin, notes):
    src = ezdxf.readfile(OUT / f"{part}_flat.dxf").modelspace()
    meta = json.loads((OUT / "build_meta.json").read_text())
    poly = [e for e in src if e.dxftype() == "LWPOLYLINE"][0]
    pts = [(p[0], p[1]) for p in poly.get_points()]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = min(xs), min(ys)
    ox, oy = origin
    T = lambda x, y: (ox + (x - x0) * SC, oy + (y - y0) * SC)
    doc = ezdxf.new("R2018", setup=True)
    setup(doc)
    msp = doc.modelspace()
    msp.add_lwpolyline([T(*p) for p in pts], close=True, dxfattribs={"layer": "VISIBLE"})
    holes = [(e.dxf.center.x, e.dxf.center.y, 2 * e.dxf.radius) for e in src if e.dxftype() == "CIRCLE"]
    for x, y, d in holes:
        msp.add_circle(T(x, y), d / 2 * SC, dxfattribs={"layer": "VISIBLE"})
    bends = [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)) for e in src if e.dxftype() == "LINE"]
    for i, (a, b) in enumerate(bends, 1):
        msp.add_line(T(*a), T(*b), dxfattribs={"layer": "BEND"})
        mx, my = T(a[0] + 0.3 * (b[0] - a[0]), a[1] + 0.3 * (b[1] - a[1]))   # 30 % along: clear of the mid-edge holes
        txt(msp, f"B{i}", (mx + 1, my + 1), 2.2)
    X1, Y1 = max(xs), max(ys)
    dim(msp, T(x0, y0), T(X1, y0), base=T(0, y0 - 12 / SC))
    dim(msp, T(x0, y0), T(x0, Y1), base=T(x0 - 12 / SC, 0), angle=90)
    # bend line positions measured from the left / bottom of the blank
    vx = sorted({round(a[0], 3) for a, b in bends if abs(a[0] - b[0]) < 1e-6})
    vy = sorted({round(a[1], 3) for a, b in bends if abs(a[1] - b[1]) < 1e-6})
    # each bend line dimensioned from the nearer edge of the blank (reads like a brake set-up)
    lo_x = [x for x in vx if x - x0 <= X1 - x]
    hi_x = [x for x in vx if x - x0 > X1 - x]
    for j, x in enumerate(lo_x):
        dim(msp, T(x0, Y1), T(x, Y1), base=T(0, Y1 + (6 + 5 * j) / SC))
    for j, x in enumerate(hi_x):
        dim(msp, T(X1, Y1), T(x, Y1), base=T(0, Y1 + (6 + 5 * j) / SC))
    lo_y = [y for y in vy if y - y0 <= Y1 - y]
    hi_y = [y for y in vy if y - y0 > Y1 - y]
    for j, y in enumerate(lo_y):
        dim(msp, T(X1, y0), T(X1, y), base=T(X1 + (6 + 5 * j) / SC, 0), angle=90)
    for j, y in enumerate(hi_y):
        dim(msp, T(X1, Y1), T(X1, y), base=T(X1 + (6 + 5 * j) / SC, 0), angle=90)
    # corner notch (relief + bend zone): the concave corner nearest the lower-left whose two edges are both short
    n = len(pts)
    best = None
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        la, lc = abs(b[0] - a[0]) + abs(b[1] - a[1]), abs(c[0] - b[0]) + abs(c[1] - b[1])
        if cross < 0 and 5 < la < 15 and 5 < lc < 15 and (best is None or b[0] + b[1] < best[1][0] + best[1][1]):
            best = (a, b, c)
    assert best, "no corner notch found"
    a, b, c = best
    for p in (a, c):
        if abs(p[1] - b[1]) < 1e-6:     # horizontal edge: dimension below/above it
            dim(msp, T(*p), T(*b), base=T(0, b[1] + 6 / SC))
        else:
            dim(msp, T(*p), T(*b), base=T(b[0] + 6 / SC, 0), angle=90)
    txt(msp, f"corner notch, 4x alike (includes the {P.RELIEF_DEPTH:g} x {P.RELIEF_DEPTH:g} relief)",
        (T(*b)[0] + 14, T(*b)[1] + 4), 2.0)
    # bend table
    tb = meta["bends"][part]
    tx, ty = 250, 228
    txt(msp, "BEND TABLE (order = sequence on the brake)", (tx, ty), 2.8)
    hdr = "ID   side  angle  direction  r_in   length   K     BA"
    txt(msp, hdr, (tx, ty - 6), 2.2)
    order = sorted(range(len(tb)), key=lambda i: 0 if "DOWN" in tb[i][4] else 1) if part == "body" else list(range(len(tb)))
    for row, i in enumerate(order):
        b = tb[i]
        txt(msp, f"B{i + 1:<3} {b[0]:<5} {b[3]:.0f}     {b[4]:<9}  {P.R_IN:.1f}   {b[5]:7.2f}  {P.K}  {P.ba(90):.3f}   step {row + 1}",
            (tx, ty - 11 - 4.5 * row), 2.2)
    # hole table (coordinates from the lower-left corner of the blank)
    hy = ty - 18 - 4.5 * len(tb)
    txt(msp, "HOLE TABLE (from lower-left of blank)", (tx, hy), 2.8)
    kinds = {}
    for x, y, d in holes:
        kinds.setdefault(round(d, 2), []).append((x - x0, y - y0))
    yy = hy - 6
    for d, lst in sorted(kinds.items()):
        name = {P.PEM_NUT["hole"]: "PEM CLS-M4-1 nut", P.STUD["hole"]: "PEM IFHA-M2.5-12 stud (2.50 +0.08)",
                P.GLAND_M16["hole"]: "M16x1.5 gland", P.GLAND_PG7["hole"]: "PG7 gland", P.LID_HOLE_D: "M4 clearance"}.get(d, "")
        txt(msp, f"{len(lst)} x %%c{d:.2f}  {name}", (tx, yy), 2.2)
        yy -= 4.2
        for k in range(0, len(lst), 3):
            txt(msp, "   " + "  ".join(f"({x:.2f}, {y:.2f})" for x, y in lst[k:k + 3]), (tx, yy), 2.0)
            yy -= 3.8
    frame(msp, title, notes)
    doc.saveas(DWG / f"{part}_flat.dxf")
    print("wrote", DWG / f"{part}_flat.dxf")


def assembly_sheet():
    from build123d import Compound
    body, lid = import_step(OUT / "body.step"), import_step(OUT / "lid.step")
    asm = Compound(children=[body, lid])
    doc = ezdxf.new("R2018", setup=True)
    setup(doc)
    msp = doc.modelspace()
    b = asm.bounding_box()
    lo, hi = (b.min.X, b.min.Y, b.min.Z), (b.max.X, b.max.Y, b.max.Z)
    views = {"TOP": ((0, 0, 500), (0, 1, 0), (0, 1), (40, 120)), "FRONT (from -Y)": ((0, -500, 0), (0, 0, 1), (0, 2), (40, 60)),
             "RIGHT (from +X)": ((500, 0, 0), (0, 0, 1), (1, 2), (175, 60))}
    M = {}
    for name, (cam, up, (ui, vi), (ox, oy)) in views.items():
        shape = lid if name == "TOP" else asm          # from above only the lid is visible; HLR of the pair drew hidden body edges
        vis, hid = shape.project_to_viewport(cam, viewport_up=up, look_at=(0, 0, 0))
        allp = [p for e in vis for p in (e.start_point(), e.end_point())]
        umin, vmin = min(p.X for p in allp), min(p.Y for p in allp)
        for es, layer in ((vis, "VISIBLE"), (hid, "HIDDEN")):
            for e in es:
                ps = [((p.X - umin) * SC + ox, (p.Y - vmin) * SC + oy) for p in e.positions([i / 16 for i in range(17)])]
                msp.add_lwpolyline(ps, dxfattribs={"layer": layer})
        hv = max(p.Y for p in allp) - vmin
        txt(msp, name, (ox, oy + hv * SC + 14), 3.0)
        M[name] = lambda a, c, ui=ui, vi=vi, ox=ox, oy=oy: (ox + (a - lo[ui]) * SC, oy + (c - lo[vi]) * SC)
    Tv, F, R = M["TOP"], M["FRONT (from -Y)"], M["RIGHT (from +X)"]
    dim(msp, Tv(lo[0], lo[1]), Tv(hi[0], lo[1]), base=Tv(0, lo[1] - 10 / SC))
    dim(msp, Tv(lo[0], lo[1]), Tv(lo[0], hi[1]), base=Tv(lo[0] - 10 / SC, 0), angle=90)
    dim(msp, F(lo[0], lo[2]), F(lo[0], hi[2]), base=F(lo[0] - 10 / SC, 0), angle=90)
    meta = json.loads((OUT / "build_meta.json").read_text())
    for h in meta["holes"]:
        if not h["kind"].startswith("cable gland"):
            continue
        x, y, z = h["c"]
        if h["axis"] == "x":
            dim(msp, R(lo[1], lo[2]), R(y, z), base=R(0, hi[2] + 8 / SC))
            dim(msp, R(hi[1], lo[2]), R(y, z), base=R(hi[1] + 8 / SC, 0), angle=90)
        else:
            dim(msp, F(lo[0], lo[2]), F(x, z), base=F(0, hi[2] + 8 / SC))
            dim(msp, F(hi[0], lo[2]), F(x, z), base=F(hi[0] + 8 / SC, 0), angle=90)
    bom = ["BOM",
           "1  Body, 5052-H32 t1.5 (body_flat.dxf), corners and flange mitres TIG welded, ground flush",
           "1  Lid, 5052-H32 t1.5 (lid_flat.dxf)",
           f"1  Gasket: {P.GASKET['kind']}, frame on the flange land {P.GASKET['inner']}-{P.GASKET['outer']} mm from the wall",
           f"12 PEM CLS-M4-1 self-clinching nut (body flange)",
           f"12 Spacer {P.SPACER['od']}/{P.SPACER['id']} x {meta['lid_geom'][3]:.2f} mm (gasket compression stop)",
           "12 M4 pan-head screw, length per PEM CLS-M4-1 thread (M4x8 nominal), with sealing washer",
           f"4  PEM IFHA-M2.5-12 sealed flush-head stud (IPX7/IPX9K per PEM) + 6 mm spacer 5/2.7 + M2.5 nut",
           f"1  {P.GLAND_M16['name']}, cable {P.GLAND_M16['cable'][0]}-{P.GLAND_M16['cable'][1]} mm (Ethernet)",
           f"1  {P.GLAND_PG7['name']}, cable {P.GLAND_PG7['cable'][0]}-{P.GLAND_PG7['cable'][1]} mm (USB-C power)",
           "1  Raspberry Pi 4 Model B"]
    for i, l in enumerate(bom):
        txt(msp, l, (175, 260 - 5 * i), 2.6 if i == 0 else 2.2)
    frame(msp, "RPi 4 IP65 sheet-metal enclosure - ASSEMBLY",
          ["IP65 is a design target, not a certification: seal = gasket + welded seams + rated glands.",
           f"Gasket {P.GASKET['free_t']} mm free, {meta['lid_geom'][3]:.2f} mm installed ({P.GASKET['compression'] * 100:.0f} % compression).",
           "Screws sit outside the gasket line; tighten until the lid seats on the spacers."])
    doc.saveas(DWG / "assembly.dxf")
    print("wrote", DWG / "assembly.dxf")


def main():
    common = ["Bend lines (red, dashed) mark the middle of each bend zone.",
              f"Bend allowance {P.ba(90):.3f} per 90 deg bend (K {P.K}, r_in {P.R_IN}).",
              f"Corner reliefs {P.RELIEF_DEPTH:g} x {P.RELIEF_DEPTH:g} at every corner; bends stop at them."]
    flat_sheet("body", "RPi 4 IP65 enclosure - BODY flat pattern", (35, 25),
               common + ["Order: bend (flanges DOWN, then walls UP) > weld > flatten land > press PEM.",
                         "Close corner notches, gaps, mitres: filler weld, or patch / folded tab.",
                         "Leak test every welded corner, then flatten the gasket land to 0.3 mm.",
                         "Press CLS-M4-1 and IFHA-M2.5-12 last; IFHA head flush on the outside.",
                         "IFHA: head on punch side, no deburring; hole 2.50-2.58 (go/no-go pins).",
                         "IFHA seal untested in 5052 by PEM: pass a 5052 coupon test first."])
    flat_sheet("lid", "RPi 4 IP65 enclosure - LID flat pattern", (45, 50), common + ["Skirt corners and reliefs stay open (not part of the seal)."])
    assembly_sheet()


if __name__ == "__main__":
    main()
