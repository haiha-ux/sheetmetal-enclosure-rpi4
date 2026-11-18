"""Assemble deliver/, report.json and spec.json (run after verify).  python package.py"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT, D = ROOT / "out", ROOT / "deliver"
sys.path.insert(0, str(ROOT / "sm"))
import params as P  # noqa: E402


def main():
    D.mkdir(exist_ok=True)
    for f in ("body.step", "lid.step", "assembly.step", "body.stl", "lid.stl", "body_flat.dxf", "lid_flat.dxf"):
        shutil.copy2(OUT / f, D / f)
    for sub, pat in (("drawing", ("*.pdf", "*.dxf", "*.png")), ("render", ("*.png",))):
        (D / sub).mkdir(exist_ok=True)
        for p in pat:
            for f in (ROOT / sub).glob(p):
                shutil.copy2(f, D / sub / f.name)
    R = json.loads((ROOT / "verify" / "report.json").read_text())
    M = json.loads((OUT / "build_meta.json").read_text())
    s = []
    add = s.append
    for n in ("body", "lid"):
        for ax in ("dx", "dy", "dz"):
            add(dict(name=f"{n} bbox {ax}", kind="bbox_dim", a=f"{n}.step#0", axis=ax[1], target=round(R[f"{n}.step#0.bbox_{ax}"], 3), tol=0.1, op="=="))
        add(dict(name=f"{n} sheet thickness", kind="thickness", a=f"{n}.step#0", target=P.T, tol=0.01, op="=="))
        add(dict(name=f"{n} bends", kind="bends", a=f"{n}.step#0", count=len(M["bends"][n]), r_in=P.R_IN, angle_deg=90, kfactor=P.K))
        add(dict(name=f"{n} flat DXF developed size", kind="bbox_dim", a=f"{n}_flat.dxf",
                 target=[round(v, 3) for v in M["flats"][n]["bbox"]], tol=0.1, op="==", axis="xy [x0, y0, x1, y1]"))
        add(dict(name=f"{n} holes to bend zone", kind="min_distance", a=f"{n}_flat.dxf holes", b="BEND zones", target=2 * P.T + P.R_IN, op=">="))
    for d, cnt, part, what in ((P.STUD["hole"], 4, "body", "PEM IFHA-M2.5-12 stud"), (P.PEM_NUT["hole"], 12, "body", "PEM CLS-M4-1"),
                               (P.GLAND_M16["hole"], 1, "body", "M16x1.5 gland"), (P.GLAND_PG7["hole"], 1, "body", "PG7 gland"),
                               (P.LID_HOLE_D, 12, "lid", "M4 clearance")):
        add(dict(name=what, kind="hole_diameter", a=f"{part}.step#0", target=d, tol=0.02, op="==", count=cnt))
    add(dict(name="volume = flat area x T with K", kind="volume", a="body.step#0 / lid.step#0", b="*_flat.dxf", tol_rel=0.005, op="<="))
    add(dict(name="plugs and Pi parts to walls, lid, glands", kind="min_distance", a="plug_rj45, plug_usbc, rpi_*", b="body, lid, glands",
             target=P.PORT_CLEARANCE, op=">="))
    add(dict(name="gasket compression", kind="ratio", target=[0.20, 0.30], measured=R["gasket.compression"], op="in"))
    (ROOT / "spec.json").write_text(json.dumps(s, indent=1))
    shutil.copy2(ROOT / "verify" / "report.json", ROOT / "report.json")
    print("deliver/ written,", len(s), "spec items")


if __name__ == "__main__":
    main()
