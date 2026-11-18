"""Break the design on purpose; verify.py must fail the named check.  python verify/break_test.py"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
CASES = [
    ("flat built with K 0.33, checked with K 0.42", {"K": 0.33}, "DXF flat length"),
    ("nut holes 3 mm from the wall", {"FLANGE_HOLE_FROM_WALL": 3.0}, "from the bend zone"),
    ("M16 gland 8 mm above the base", {"GLAND_M16_Z": 8.0}, "from the bend zone"),
    ("gasket squeezed 40 %", {"GASKET": {"inner": 3.0, "outer": 11.0, "free_t": 3.0, "compression": 0.40, "kind": "x"}}, "gasket compression"),
    ("Pi moved 34 mm toward the y = 0 wall", {"RPI_ORIGIN": [15.0, 5.0]}, "plug_usbc"),
    ("flange 20 mm (nut too close to the edge)", {"F": 20.0}, "centre to sheet edge"),
    ("relief only 2 mm deep", {"RELIEF_DEPTH": 2.0}, "bend reliefs"),
]
res = []
for name, over, expect in CASES:
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ, SM_OUT=td, SM_REPORT=td, SM_PARAMS=json.dumps(over))
        if "K" not in over:
            env["SM_VERIFY_PARAMS"] = json.dumps(over)    # geometry changes: verify reads the same parameters
        subprocess.run([PY, str(ROOT / "sm/build.py")], env=env, check=True, capture_output=True)
        r = subprocess.run([PY, str(ROOT / "verify/verify.py")], env=env, capture_output=True, text=True)
        failed = json.loads((Path(td) / "report.json").read_text())["checks_failed"]
    ok = r.returncode != 0 and any(expect in f for f in failed)
    res.append({"case": name, "override": over, "caught": ok, "failed_checks": failed})
    print(("CAUGHT " if ok else "MISSED ") + name, failed[:3])
(ROOT / "verify" / "break_test.json").write_text(json.dumps(res, indent=1))
sys.exit(0 if all(r["caught"] for r in res) else 1)
