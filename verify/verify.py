"""Checks every claim about the sheet-metal enclosure from the exported files -> verify/report.json.
python verify/verify.py   (build123d venv, after sm/build.py). Exit 1 if any check fails.
"""
import json
import math
import os
import platform
import sys
from pathlib import Path

import ezdxf
import numpy as np
import trimesh
from build123d import Plane, Rectangle, import_step, GeomType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sm"))
import params as P  # noqa: E402
import sheet as S  # noqa: E402

OUT = Path(os.environ.get("SM_OUT", ROOT / "out"))
REPORT = Path(os.environ.get("SM_REPORT", ROOT / "verify"))
for _k, _v in json.loads(os.environ.get("SM_VERIFY_PARAMS", "{}")).items():
    setattr(P, _k, _v)
report, checks = {}, []


def check(name, ok, **kw):
    checks.append({"name": name, "pass": bool(ok), **kw})
    print(("PASS " if ok else "FAIL ") + name, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in kw.items()})


def bb(s):
    b = s.bounding_box()
    return np.array([b.min.X, b.min.Y, b.min.Z]), np.array([b.max.X, b.max.Y, b.max.Z])


def read_dxf(path):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    outl = [e for e in msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "OUTLINE"]
    circles = [(e.dxf.center.x, e.dxf.center.y, 2 * e.dxf.radius) for e in msp if e.dxftype() == "CIRCLE"]
    bends = [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)) for e in msp if e.dxftype() == "LINE" and e.dxf.layer == "BEND"]
    other = [e.dxftype() for e in msp if e.dxf.layer in ("OUTLINE", "HOLES") and e.dxftype() not in ("LWPOLYLINE", "CIRCLE")]
    pts = [(p[0], p[1]) for p in outl[0].get_points()] if outl else []
    return outl, pts, circles, bends, other, doc.units


def poly_area(pts):
    return 0.5 * abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1])))


def chord(pts, axis, value):
    """Extent of the outline polygon along the line {axis = value}."""
    hits = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        a0, a1 = (y0, y1) if axis == "y" else (x0, x1)
        b0, b1 = (x0, x1) if axis == "y" else (y0, y1)
        if (a0 - value) * (a1 - value) < 0:
            hits.append(b0 + (value - a0) / (a1 - a0) * (b1 - b0))
    return max(hits) - min(hits)


def seg_dist(p, a, b):
    p, a, b = map(np.array, (p, a, b))
    t = np.clip(np.dot(p - a, b - a) / np.dot(b - a, b - a), 0, 1)
    return float(np.linalg.norm(p - (a + t * (b - a))))


def min_thickness(stl):
    m = trimesh.load(stl)
    o = m.triangles_center - m.face_normals * 1e-4
    loc, idx, tri = m.ray.intersects_location(o, -m.face_normals, multiple_hits=False)
    d = np.linalg.norm(loc - o[idx], axis=1)
    facing = np.einsum("ij,ij->i", m.face_normals[idx], m.face_normals[tri]) < -0.99   # opposite skin of the sheet
    skin = d[facing & (d < 2 * P.T)]          # longer hits cross the air inside the box to another wall
    return float(skin.min()), float(skin.max()), float(np.median(skin))


def step_holes(solid, diameters):
    """Hole centres from the STEP: OCC splits a hole into half-cylinders, so the faces of one hole
    are grouped and the centre is the middle of their joint bounding box (axis point, mid-sheet)."""
    faces = []
    for f in solid.faces():
        if f.geom_type != GeomType.CYLINDER:
            continue
        d = 2 * f.radius
        if any(abs(d - dd) < 1e-3 for dd in diameters):
            b = f.bounding_box()
            faces.append([d, np.array([b.min.X, b.min.Y, b.min.Z]), np.array([b.max.X, b.max.Y, b.max.Z])])
    groups = []
    for d, lo, hi in faces:
        for g_ in groups:
            if abs(g_[0] - d) < 1e-3 and np.all(lo <= g_[2] + 1e-6) and np.all(hi >= g_[1] - 1e-6):
                g_[1], g_[2] = np.minimum(g_[1], lo), np.maximum(g_[2], hi)
                break
        else:
            groups.append([d, lo, hi])
    return [(d, tuple((lo + hi) / 2)) for d, lo, hi in groups]


def main():
    meta = json.loads((OUT / "build_meta.json").read_text())
    BA = P.ba(90)
    report.update({"T": P.T, "kfactor": P.K, "kfactor_source": P.K_SOURCE, "r_in": P.R_IN, "material": P.MATERIAL})
    parts = {}
    for n in ("body", "lid"):
        s = import_step(OUT / f"{n}.step")
        parts[n] = s
        lo, hi = bb(s)
        m0 = meta["parts"][n]
        dv = abs(s.volume - m0["volume"]) / m0["volume"]
        db = max(np.max(np.abs(lo - m0["bbox_min"])), np.max(np.abs(hi - m0["bbox_max"]))) / max(hi - lo)
        k = f"{n}.step#0"
        report.update({f"{k}.volume": s.volume, f"{k}.bbox_dx": hi[0] - lo[0], f"{k}.bbox_dy": hi[1] - lo[1], f"{k}.bbox_dz": hi[2] - lo[2],
                       f"{k}.solid_count": len(s.solids()), f"{k}.is_valid": s.is_valid})
        check(f"{n}: one valid solid, STEP re-import matches build", len(s.solids()) == 1 and s.is_valid and dv < 1e-6 and db < 1e-6,
              solids=len(s.solids()), rel_volume=dv, rel_bbox=db)
        tmin, tmax, tmed = min_thickness(OUT / f"{n}.stl")
        report[f"{k}.thickness"], report[f"{k}.thickness_min"], report[f"{k}.thickness_max"] = tmed, tmin, tmax
        check(f"{n}: uniform thickness T = {P.T} (+-0.01, skin-to-skin rays)", abs(tmin - P.T) < 0.01 and abs(tmax - P.T) < 0.01,
              min=tmin, max=tmax)
        mesh = trimesh.load(OUT / f"{n}.stl")
        check(f"{n}: STL watertight", mesh.is_watertight and abs(mesh.volume - s.volume) / s.volume < 5e-3, stl_volume=float(mesh.volume))

        # flat pattern DXF format
        outl, pts, circles, bends, other, units = read_dxf(OUT / f"{n}_flat.dxf")
        nb = 8 if n == "body" else 4
        report.update({f"{n}_flat.outline_polylines": len(outl), f"{n}_flat.holes": len(circles), f"{n}_flat.bend_lines": len(bends),
                       f"{n}_flat.units": units})
        check(f"{n}_flat.dxf: 1 closed outline, holes as circles, {nb} BEND lines, mm",
              len(outl) == 1 and outl[0].closed and not other and len(bends) == nb and units == 4,
              outlines=len(outl), bends=len(bends), other=other, units=units)

        # unfold the STEP independently: section strip area / T = neutral-ish length, then K correction per bend
        bends_meta = meta["bends"][n]
        for axis, val in (("y", 30.0), ("x", 100.0)):
            plane = Plane.XZ.offset(-val) if axis == "y" else Plane.YZ.offset(val)
            sec = s & (plane * Rectangle(1000, 1000))
            mid = sum(f.area for f in sec.faces()) / P.T
            nbends = 4 if n == "body" else 2
            developed = mid - nbends * math.radians(90) * P.T * (0.5 - P.K)
            flat = chord(pts, axis, val)
            report[f"{n}.unfold_from_step.{axis}={val}"] = developed
            report[f"{n}_flat.chord.{axis}={val}"] = flat
            check(f"{n}: STEP unfolded along {'x' if axis == 'y' else 'y'} (section at {axis}={val}) = DXF flat length (+-0.1)",
                  abs(developed - flat) <= 0.1, step=developed, dxf=flat)

        # mass conservation with K
        a_flat = poly_area(pts) - sum(math.pi * (d / 2) ** 2 for _, _, d in circles)
        corr = sum(math.radians(b[3]) * P.T * P.T * (0.5 - P.K) * b[5] for b in bends_meta)
        v_exp = a_flat * P.T + corr
        dv = abs(v_exp - s.volume) / s.volume
        report.update({f"{n}_flat.area_net": a_flat, f"{n}.volume_from_flat": v_exp, f"{n}.volume_rel_err": dv})
        check(f"{n}: flat area x T (K-corrected) = STEP volume within 0.5 %", dv <= 5e-3, rel_err=dv)

        # refold: every DXF hole folded back to 3D must sit on a STEP hole of the same size
        sh = step_holes(s, sorted({round(d, 4) for _, _, d in circles}))
        worst, unmatched = 0.0, 0
        for x, y, d in circles:
            q = np.array(S.refold_point(n, (x, y)))
            cands = [np.linalg.norm(q - np.array(c)) for dd, c in sh if abs(dd - d) < 1e-3]
            if not cands:
                unmatched += 1
                continue
            worst = max(worst, min(cands))
        report[f"{n}.refold_hole_max_err"] = worst
        check(f"{n}: DXF holes refolded onto STEP holes (+-0.1), counts equal", worst <= 0.1 and unmatched == 0 and len(sh) == len(circles),
              worst=worst, dxf_holes=len(circles), step_holes=len(sh), unmatched=unmatched)

        # hole to bend >= 2T + r_in, PEM edge distances
        need = 2 * P.T + P.R_IN
        hb = min(seg_dist((x, y), a, b_) - d / 2 - BA / 2 for x, y, d in circles for a, b_ in bends)
        report[f"{n}.hole_to_bend_min"] = hb
        check(f"{n}: every hole edge >= 2T + r_in = {need} from the bend zone", hb >= need, min=hb)
        for nm, spec in (("PEM CLS-M4", P.PEM_NUT), ("PEM IFHA-M2.5 stud", P.STUD)):
            hs = [(x, y) for x, y, d in circles if abs(d - spec["hole"]) < 1e-3]
            if not hs:
                continue
            e = min(seg_dist(h, a, b_) for h in hs for a, b_ in zip(pts, pts[1:] + pts[:1]))
            report[f"{n}.{nm}.centre_to_edge_min"] = e
            check(f"{n}: {nm} centre to sheet edge >= {spec['min_edge']}", e >= spec["min_edge"] and P.T >= spec["min_sheet"], min=e)

    # bends / flanges
    report["bends"] = {p: [{"r_in": P.R_IN, "angle_deg": b[3], "direction": b[4], "length": b[5], "side": b[0]} for b in meta["bends"][p]]
                       for p in ("body", "lid")}
    u_si, zl, zsb, gap = meta["lid_geom"]
    flanges = {"body wall": P.H, "body flange": P.F + P.T, "lid skirt": (zl + P.T) - zsb}
    report["flange_lengths_outside"] = flanges
    check(f"every flange >= SendCutSend minimum {P.MIN_FLANGE}", min(flanges.values()) >= P.MIN_FLANGE, **flanges)
    # bend reliefs measured on the DXF blanks: probe each expected slot, find where material starts again
    from matplotlib.path import Path as MPath
    rel = {}
    for part in ("body", "lid"):
        outl, pts, circles, bends, other, units = read_dxf(OUT / f"{part}_flat.dxf")
        poly = MPath(pts)
        inside = lambda q: bool(poly.contains_point(q))
        widths, depths = [], []
        BA_ = P.ba(90)
        for side, (ax, n, pos, E) in S.SIDES.items():
            # base/plate edge (u) and the corner s-values of this side
            e0, s0, s1 = (-P.R_IN, P.R_IN, E - P.R_IN) if part == "body" else (S.lid_geom()[0] - P.R_IN, -(S.lid_geom()[0] - P.R_IN), E + S.lid_geom()[0] - P.R_IN)
            for edge_s, sgn in ((s0, 1), (s1, -1)):
                # width: just inside the plate edge, walk along the bend line from the corner until material starts
                w = 0.0
                while w < 10 and not inside(S.g(side, e0 - 0.3, edge_s + sgn * (w + 0.005))):
                    w += 0.01
                # depth: in the middle of the relief, walk from the plate edge into the plate until material starts
                d = 0.0
                while d < 10 and not inside(S.g(side, e0 - (d + 0.005), edge_s + sgn * w / 2)):
                    d += 0.01
                widths.append(w); depths.append(d + BA_ / 2)        # depth reported from the bend line
        rel[part] = {"width_min": min(widths), "depth_min": min(depths)}
    need_d = P.T + P.R_IN + 0.5
    report["bend_relief_measured_on_dxf"] = rel
    check(f"bend reliefs on the DXF: width >= T/2 = {P.T / 2}, depth from the bend >= T + r + 0.5 = {need_d}",
          all(v["width_min"] >= P.T / 2 - 0.01 and v["depth_min"] >= need_d - 0.01 for v in rel.values()),
          body=rel["body"], lid=rel["lid"])
    comp = 1 - gap / P.GASKET["free_t"]
    report["gasket.compression"] = comp
    check("gasket compression inside 20-30 % (Stockwell, IP-rated)", 0.20 <= comp <= 0.30, compression=comp)

    # interference and clearances
    names = json.loads((OUT / "check_solids.json").read_text())
    ex = dict(zip(names, import_step(OUT / "check_solids.step").solids()))
    assert len(ex) == len(names)
    body, lid = parts["body"], parts["lid"]
    for pn, p in (("body.step#0", body), ("lid.step#0", lid)):
        for on, o in ex.items():
            c = p & o
            v = 0.0 if c is None else sum(x.volume for x in c.solids())
            d = p.distance_to(o)
            report[f"pair.{on}|{pn}.min_clearance"], report[f"pair.{on}|{pn}.common_volume"] = d, v
            if v > 1e-3:
                check(f"no interference {on} | {pn}", False, common_volume=v)
    c = body & lid
    v = 0.0 if c is None else sum(x.volume for x in c.solids())
    report["pair.body.step#0|lid.step#0.min_clearance"] = body.distance_to(lid)
    check("no interference between body, lid and every other part", not [k for k in checks if not k["pass"] and k["name"].startswith("no interference")] and v < 1e-3,
          body_lid=v)
    rpi = [k for k in ex if k.startswith("rpi_")]
    plugs = [k for k in ex if k.startswith("plug_")]
    for k in rpi + plugs:
        d = min(body.distance_to(ex[k]) if k != "rpi_pcb" else 99, lid.distance_to(ex[k]))
        report[f"clearance.{k}"] = d
    for k in plugs:
        others = [o for o in ex if o.startswith("gland_")]
        d = min([body.distance_to(ex[k]), lid.distance_to(ex[k])] + [ex[k].distance_to(ex[o]) for o in others])
        report[f"clearance.{k}"] = d
        check(f"{k}: >= {P.PORT_CLEARANCE} from walls, lid and glands", d >= P.PORT_CLEARANCE, clearance=d)
    for k in rpi:
        if k == "rpi_pcb":
            continue
        d = min(body.distance_to(ex[k]), lid.distance_to(ex[k]))
        check(f"{k}: >= {P.PORT_CLEARANCE} from body and lid", d >= P.PORT_CLEARANCE, clearance=d)
    import build123d, OCP
    report["tools"] = {"python": platform.python_version(), "build123d": build123d.__version__, "OCP": "8.0.1.1", "ezdxf": ezdxf.__version__,
                       "trimesh": trimesh.__version__}
    report["checks_failed"] = [c["name"] for c in checks if not c["pass"]]
    report["checks_total"] = len(checks)
    REPORT.mkdir(exist_ok=True)
    (REPORT / "report.json").write_text(json.dumps(report, indent=1, default=float))
    (REPORT / "checks.json").write_text(json.dumps(checks, indent=1, default=float))
    print(f"\n{len(checks) - len(report['checks_failed'])}/{len(checks)} checks pass")
    sys.exit(1 if report["checks_failed"] else 0)


if __name__ == "__main__":
    main()
