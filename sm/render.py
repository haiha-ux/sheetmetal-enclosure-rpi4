"""Renders of the assembly (vtk off-screen) + flat pattern previews.  python sm/render.py"""
import json
import sys
from pathlib import Path

import vtk
from build123d import import_step, export_stl, Compound

ROOT = Path(__file__).resolve().parents[1]
OUT, R = ROOT / "out", ROOT / "render"
R.mkdir(exist_ok=True)
TMP = OUT / "_mesh"
TMP.mkdir(exist_ok=True)
COL = {"body": (0.70, 0.72, 0.75), "lid": (0.55, 0.58, 0.62), "rpi_pcb": (0.05, 0.40, 0.15), "gasket": (0.08, 0.08, 0.08)}


def col(n):
    if n in COL:
        return COL[n]
    if n.startswith("plug"):
        return (0.85, 0.55, 0.15)
    if n.startswith("gland"):
        return (0.15, 0.15, 0.18)
    if n.startswith("rpi"):
        return (0.75, 0.75, 0.70)
    return (0.6, 0.6, 0.6)


def actor(path, c, off=(0, 0, 0), opacity=1.0):
    r = vtk.vtkSTLReader(); r.SetFileName(str(path)); r.Update()
    t = vtk.vtkTransform(); t.Translate(*off)
    tf = vtk.vtkTransformFilter(); tf.SetInputConnection(r.GetOutputPort()); tf.SetTransform(t)
    m = vtk.vtkPolyDataMapper(); m.SetInputConnection(tf.GetOutputPort())
    a = vtk.vtkActor(); a.SetMapper(m)
    p = a.GetProperty(); p.SetColor(*c); p.SetOpacity(opacity); p.SetDiffuse(0.75); p.SetAmbient(0.15); p.SetSpecular(0.25)
    return a


def shot(actors, name, pos, focal, up=(0, 0, 1)):
    ren = vtk.vtkRenderer(); ren.GradientBackgroundOn(); ren.SetBackground(0.62, 0.66, 0.72); ren.SetBackground2(0.30, 0.33, 0.38)
    for a in actors:
        ren.AddActor(a)
    cam = ren.GetActiveCamera(); cam.SetPosition(*pos); cam.SetFocalPoint(*focal); cam.SetViewUp(*up)
    ren.ResetCamera(); cam.Zoom(1.2)
    w = vtk.vtkRenderWindow(); w.SetOffScreenRendering(1); w.AddRenderer(ren); w.SetSize(1600, 1200); w.Render()
    f = vtk.vtkWindowToImageFilter(); f.SetInput(w); f.Update()
    wr = vtk.vtkPNGWriter(); wr.SetFileName(str(R / name)); wr.SetInputConnection(f.GetOutputPort()); wr.Write()
    print("wrote", R / name)


def main():
    asm = import_step(OUT / "assembly.step")
    parts = []
    for c in asm.children:
        f = TMP / f"{c.label}.stl"
        export_stl(c, f, tolerance=0.05, angular_tolerance=0.3)
        parts.append((c.label, f))
    c = (75, 55, 20)
    shot([actor(f, col(n)) for n, f in parts], "1_iso_closed.png", (330, -260, 260), c)
    off = {"lid": (0, 0, 70), "gasket": (0, 0, 40)}
    shot([actor(f, col(n), off.get(n, (0, 0, 70) if n.startswith("spacer") else (0, 0, 0))) for n, f in parts],
         "2_exploded.png", (330, -260, 300), (75, 55, 45))
    shot([actor(f, col(n)) for n, f in parts if n != "lid" and not n.startswith("spacer") and n != "gasket"],
         "3_open_top.png", (75, 55, 400), c, up=(0, 1, 0))


if __name__ == "__main__":
    main()
