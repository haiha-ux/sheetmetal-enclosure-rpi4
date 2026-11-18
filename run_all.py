"""One command: build -> drawings -> renders -> verify -> break test -> deliver/.
<python with build123d 0.13> run_all.py   (PDFs need a Python 3.11 with ezdxf + PyMuPDF, path below)"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY, PY311 = sys.executable, Path(r"C:\Program Files\Python311\python.exe")
for cmd in ((PY, "sm/build.py"), (PY, "drawing/drawing.py"), (PY311, "drawing/to_pdf.py"), (PY, "sm/render.py"),
            (PY, "verify/verify.py"), (PY, "verify/break_test.py"), (PY, "package.py")):
    print(">", *cmd)
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT)
