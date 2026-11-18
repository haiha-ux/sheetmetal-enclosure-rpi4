"""Every number of the sheet-metal enclosure, with its source. Units mm, degrees.

Frame (body, lid, assembly): x along the long side, y along the short side, z up.
Inner faces of the four walls at x = 0, x = L, y = 0, y = W. Underside of the base at z = 0.
"""
import math

# --- material -------------------------------------------------------------------
MATERIAL = "Aluminium 5052-H32"
T = 1.5                 # sheet thickness
R_IN = 1.5              # inside bend radius = T (brief)
K = 0.42                # SendCutSend bending calculator, 5052 0.063 in (1.6 mm); see SOURCES and README
K_SOURCE = "SendCutSend bending calculator, 5052-H32 0.063 in: K 0.42 (their tooling, effective inside radius 0.89 mm)"
MIN_FLANGE = 7.70       # SendCutSend, same table

# --- body: tray with outward flanges (gasket land) ------------------------------
L, W = 150.0, 110.0     # inside length / width
H = 42.0                # base underside to flange top face
F = 23.5                # flange projection beyond the wall outer face (nut edge distance 7.5 >= 6.9)
GASKET = dict(inner=3.0, outer=11.0, free_t=3.0, compression=0.25,
              kind="EPDM closed-cell sponge strip, adhesive backed, 8 x 3 mm")
FLANGE_HOLE_FROM_WALL = 16.0      # M4 clinch-nut centre from the wall outer face (spacer clears the gasket band)
FLANGE_HOLES_X = (15.0, 75.0, 135.0)   # along the y = 0 and y = W flanges (inner x)
FLANGE_HOLES_Y = (15.0, 55.0, 95.0)    # along the x = 0 and x = L flanges (inner y)

# --- lid: flat plate with a skirt -----------------------------------------------
LID_GAP_SKIRT = 1.0     # skirt inner face to flange outer edge
LID_SKIRT_BELOW = 4.0   # skirt bottom below the flange underside
LID_HOLE_D = 4.5        # M4 clearance (ISO 273 medium)

# --- fasteners (filled from sources.json) ---------------------------------------
PEM_NUT = dict(name="PEM CLS-M4-1", hole=5.41, min_sheet=1.0, min_edge=6.9, od=7.9, h=3.6)   # od/h: envelope, not from the data sheet
PEM_STANDOFF = dict(name="PEM SO-M2.5-6", hole=4.22, min_sheet=1.0, min_edge=5.8, od=4.2, length=6.0)
GLAND_M16 = dict(name="cable gland M16x1.5 (Lapp SKINTOP class)", hole=16.2, nut_od=19 / 0.866, cable=(4.0, 10.0))
GLAND_PG7 = dict(name="cable gland PG7 (Lapp SKINTOP class)", hole=12.7, nut_od=14 / 0.866, cable=(2.0, 6.0))
GLAND_M16_Z = 20.0      # gland centre height above the base underside
GLAND_PG7_Z = 16.0
SPACER = dict(od=8.0, id=4.3, t=None)   # compression limiter, t set from the gasket

# --- Raspberry Pi 4 B (official mechanical drawing) -----------------------------
RPI_DRAWING = "https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-mechanical-drawing.pdf"
RPI = dict(l=85.0, w=56.0, t=1.4, corner_r=3.0, hole_d=2.7,
           holes=[(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)])
# (name, x0, y0, x1, y1, height above PCB). Centres and heights are dimensioned on the drawing;
# the box extents are read from the drawn outlines (not dimensioned) and marked as such in the README.
RPI_PARTS = [
    ("ethernet", 66.7, 45.75 - 7.85, 87.9, 45.75 + 7.85, 13.5),
    ("usb_a_top", 70.4, 27.0 - 6.7, 88.4, 27.0 + 6.7, 16.0),
    ("usb_a_bottom", 70.4, 9.0 - 6.6, 88.4, 9.0 + 6.6, 16.0),
    ("usb_c", 11.2 - 4.3, -1.2, 11.2 + 4.3, 6.25, 3.2),
    ("hdmi0", 26.0 - 3.25, -1.2, 26.0 + 3.25, 6.25, 3.0),
    ("hdmi1", 39.5 - 3.25, -1.2, 39.5 + 3.25, 6.25, 3.0),
    ("audio", 50.6, -2.7, 57.5, 12.5, 6.0),
    ("gpio", 32.5 - 25.4, 52.5 - 2.54, 32.5 + 25.4, 52.5 + 2.54, 8.5),
]
RPI_ORIGIN = (15.0, 39.0)   # board lower-left corner in body coordinates (inner x, inner y)

# plugs used inside the box (cable leaves through a gland)
RJ45_PLUG = dict(w=15.0, h=15.0, length=30.0)    # booted plug 22.5 x 15 x 11.7 (Delock, tier B) + 7.5 margin; square 15 envelope
USBC_PLUG = dict(w=12.85, h=7.0, length=30.0)    # overmold 12.85 x 7.0 (USB-C ECN 2023); length 30 assumed (no source)

PORT_CLEARANCE = 0.5


def ba(angle_deg=90.0, r=R_IN, k=None):
    """Bend allowance: arc length of the neutral axis."""
    return math.radians(angle_deg) * (r + (K if k is None else k) * T)


def load_sources(path):
    """Take K and fastener numbers from the scout's sources.json when they are there."""
    import json
    global K, K_SOURCE
    try:
        s = json.loads(open(path, encoding="utf-8").read())
    except FileNotFoundError:
        return {}
    return s

SOURCES = {
    "K-factor / min flange": "https://sendcutsend.com/resources/bending-calculator/ (5052 0.063 in: K 0.42, inside radius 0.035 in, min flange 0.303 in)",
    "5052 bend radius": "https://sendcutsend.com/materials/5052-aluminum/ (inside radius as low as 1 x thickness)",
    "PEM CLS-M4-1": "hole 5.41, min sheet 1.0, min centre-to-edge 6.9 (PEM product page / cldata)",
    "PEM SO-M2.5-6": "hole 4.22, min centre-to-edge 5.8 (PEM SO data, tier B column match)",
    "cable glands": "Lapp SKINTOP: M16x1.5 entry 16.0-16.2, SW 19, cable 4-10 mm; PG7 entry 12.5-12.8, SW 14 (Lapp data sheets)",
    "EPDM sponge compression": "Stockwell Elastomerics: 20-30 % for IP-rated seals",
    "Raspberry Pi 4 B": RPI_DRAWING,
}
