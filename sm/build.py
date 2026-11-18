"""Build body + lid solids, flat-pattern DXFs and the assembly with the Raspberry Pi 4 envelope.
python sm/build.py   (build123d venv)"""
import json
import os
import sys
from pathlib import Path

import ezdxf
from build123d import Compound, Cylinder, Pos, Rot, export_step, export_stl, Face

sys.path.insert(0, str(Path(__file__).parent))
import params as P  # noqa: E402
import sheet as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("SM_OUT", ROOT / "out"))
for _k, _v in json.loads(os.environ.get("SM_PARAMS", "{}")).items():   # break tests only
    setattr(P, _k, _v)


def flat_face(regions):
    f = regions[0].fuse(*regions[1:]).clean()       # clean() merges the coplanar pieces into one face
    faces = f.faces()
    assert len(faces) == 1, f"flat pattern is not one piece ({len(faces)} faces)"
    return faces[0]


def write_dxf(part, face, holes, path):
    doc = ezdxf.new("R2018", setup=True)
    doc.units = ezdxf.units.MM
    doc.layers.add("OUTLINE", color=7)
    doc.layers.add("HOLES", color=3)
    doc.layers.add("BEND", color=1, linetype="DASHED")
    doc.layers.add("NOTES", color=8)
    msp = doc.modelspace()
    pts = []
    for e in face.outer_wire().order_edges():
        pts.append((e.start_point().X, e.start_point().Y))
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "OUTLINE"})
    for h in holes:
        x, y = S.flat_point(h)
        msp.add_circle((x, y), h["d"] / 2, dxfattribs={"layer": "HOLES"})
    for side, a, b, ang, d, ln in S.bend_lines(part):
        msp.add_line(a, b, dxfattribs={"layer": "BEND"})
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        msp.add_text(f"{d} R{P.R_IN}", height=3, dxfattribs={"layer": "NOTES"}).set_placement((mx + 1, my + 1))
    doc.saveas(path)
    return pts


def rpi_parts():
    ox, oy = P.RPI_ORIGIN
    zb = P.T + P.PEM_STANDOFF["length"]            # PCB underside on the standoffs
    zt = zb + P.RPI["t"]
    out = {"rpi_pcb": S.box(ox, ox + P.RPI["l"], oy, oy + P.RPI["w"], zb, zt)}
    for n, x0, y0, x1, y1, h in P.RPI_PARTS:
        out[f"rpi_{n}"] = S.box(ox + x0, ox + x1, oy + y0, oy + y1, zt, zt + h)
    eth = [p for p in P.RPI_PARTS if p[0] == "ethernet"][0]
    usbc = [p for p in P.RPI_PARTS if p[0] == "usb_c"][0]
    ec = (eth[2] + eth[4]) / 2
    rj = P.RJ45_PLUG
    ez = zt + eth[5] / 2
    out["plug_rj45"] = S.box(ox + eth[3], ox + eth[3] + rj["length"], oy + ec - rj["w"] / 2, oy + ec + rj["w"] / 2, ez - rj["h"] / 2, ez + rj["h"] / 2)
    uc = (usbc[1] + usbc[3]) / 2
    up = P.USBC_PLUG
    uz = zt + usbc[5] / 2
    out["plug_usbc"] = S.box(ox + uc - up["w"] / 2, ox + uc + up["w"] / 2, oy + usbc[2] - up["length"], oy + usbc[2], uz - up["h"] / 2, uz + up["h"] / 2)
    for i, (hx, hy) in enumerate(P.RPI["holes"]):
        out[f"standoff_{i}"] = Pos(ox + hx, oy + hy, P.T) * Cylinder(P.PEM_STANDOFF["od"] / 2, P.PEM_STANDOFF["length"],
                                                                         align=(S.Align.CENTER, S.Align.CENTER, S.Align.MIN))
    return out, zt


def hardware():
    u_si, zl, zsb, gap = S.lid_geom()
    out = {}
    hs = [h for h in S.holes() if h["kind"].startswith("PEM CLS")]
    for i, h in enumerate(hs):
        x, y, _ = h["c"]
        nut = P.PEM_NUT
        out[f"nut_{i}"] = Pos(x, y, P.H - P.T - nut["h"]) * Cylinder(nut["od"] / 2, nut["h"], align=(S.Align.CENTER, S.Align.CENTER, S.Align.MIN))
        sp = P.SPACER
        ring = Cylinder(sp["od"] / 2, gap, align=(S.Align.CENTER, S.Align.CENTER, S.Align.MIN)) - Cylinder(sp["id"] / 2, gap, align=(S.Align.CENTER, S.Align.CENTER, S.Align.MIN))
        out[f"spacer_{i}"] = Pos(x, y, P.H) * ring
    gk = P.GASKET
    T = P.T
    o, i_ = T + gk["outer"], T + gk["inner"]
    frame = S.box(-o, P.L + o, -o, P.W + o, P.H, P.H + gap) - S.box(-i_, P.L + i_, -i_, P.W + i_, P.H - 1, P.H + gap + 1)
    out["gasket"] = frame
    for h in S.holes():
        if not h["kind"].startswith("cable gland"):
            continue
        x, y, z = h["c"]
        g_ = P.GLAND_M16 if "M16" in h["kind"] else P.GLAND_PG7
        nut = Cylinder(g_["nut_od"] / 2, 5.0, align=(S.Align.CENTER, S.Align.CENTER, S.Align.MIN))
        body_out = Cylinder(g_["nut_od"] / 2, 20.0, align=(S.Align.CENTER, S.Align.CENTER, S.Align.MIN))
        if h["axis"] == "x":     # inside = -x
            out["gland_nut_M16"] = Pos(x - T / 2, y, z) * (Rot(0, -90, 0) * nut)
            out["gland_body_M16"] = Pos(x + T / 2, y, z) * (Rot(0, 90, 0) * body_out)
        else:                    # wall y = 0, inside = +y
            out["gland_nut_PG7"] = Pos(x, y + T / 2, z) * (Rot(-90, 0, 0) * nut)
            out["gland_body_PG7"] = Pos(x, y - T / 2, z) * (Rot(90, 0, 0) * body_out)
    return out


def main():
    OUT.mkdir(exist_ok=True)
    body = S.cut_holes(S.body_solid(), "body")
    lid = S.cut_holes(S.lid_solid(), "lid")
    body.label, lid.label = "body", "lid"
    meta = {}
    for n, s_ in (("body", body), ("lid", lid)):
        b = s_.bounding_box()
        meta[n] = {"volume": s_.volume, "bbox_min": [b.min.X, b.min.Y, b.min.Z], "bbox_max": [b.max.X, b.max.Y, b.max.Z],
                   "solids": len(s_.solids()), "valid": s_.is_valid}
        export_step(s_, OUT / f"{n}.step")
        export_stl(s_, OUT / f"{n}.stl", tolerance=0.005, angular_tolerance=0.05)
    hs = S.holes()
    flats = {}
    for n, regions in (("body", S.body_flat_regions()), ("lid", S.lid_flat_regions())):
        f = flat_face(regions)
        pts = write_dxf(n, f, [h for h in hs if h["part"] == n], OUT / f"{n}_flat.dxf")
        b = f.bounding_box()
        flats[n] = {"area_outline": f.area, "bbox": [b.min.X, b.min.Y, b.max.X, b.max.Y], "outline_vertices": len(pts),
                    "hole_area": sum(3.141592653589793 * (h["d"] / 2) ** 2 for h in hs if h["part"] == n)}
    rp, zt = rpi_parts()
    hw = hardware()
    extra = {**rp, **hw}
    for k, v in extra.items():
        v.label = k
    export_step(Compound(children=[body, lid, *extra.values()], label="assembly"), OUT / "assembly.step")
    export_step(Compound(children=list(extra.values())), OUT / "check_solids.step")
    (OUT / "check_solids.json").write_text(json.dumps(list(extra.keys())))
    (OUT / "build_meta.json").write_text(json.dumps({"parts": meta, "flats": flats, "holes": hs,
        "bends": {p: S.bend_lines(p) for p in ("body", "lid")}, "lid_geom": S.lid_geom(), "rpi_pcb_top": zt}, indent=1, default=list))
    print({k: (round(v["volume"], 1), v["solids"], v["valid"]) for k, v in meta.items()})
    print({k: (round(v["area_outline"], 1), [round(c, 2) for c in v["bbox"]]) for k, v in flats.items()})


if __name__ == "__main__":
    main()
