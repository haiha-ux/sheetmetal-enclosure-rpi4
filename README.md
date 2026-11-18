# IP65-target sheet-metal enclosure for a Raspberry Pi 4

A two-part enclosure in 1.5 mm aluminium 5052-H32 for a Raspberry Pi 4 Model B.
- The body is a tray with four walls and an outward flange that forms the gasket land.
- The lid is a flat plate with a short skirt.
- The cables leave through two cable glands, so no Pi port faces the outside.

It is built in build123d as true sheet metal: planar faces with cylindrical bends of inside radius 1.5 mm. The
flat patterns are built from the same parameters, and a separate check unfolds the 3D solid again and compares
it with them.

IP65 is a design target, not a certification. The design has not been made or tested. Every fit and seal statement
below is a CAD check only.

![exploded](render/2_exploded.png)

## Design

| Item | Value |
|---|---|
| Material | Al 5052-H32, t = 1.5 mm, inside bend radius 1.5 mm (= t) |
| K-factor | 0.42 (SendCutSend bending calculator, 5052 0.063 in). Bend allowance 3.346 mm per 90° bend |
| Body | 150 × 110 mm inside, 42 mm tall to the flange top. The flange projects 23.5 mm beyond the wall's outer face (25 mm from its inner face). 8 bends. Each bend stops 0.75 mm short of the corner, with a 0.75 × 3.5 mm relief slot into the base. Wall corners, reliefs and flange mitres are TIG welded and ground flush |
| Lid | 205 × 165 mm plate with a 9.25 mm skirt. 4 bends with the same 0.75 × 3.5 mm corner reliefs. Skirt corners left open (they are not part of the seal) |
| Closed size | 205 × 165 × 45.75 mm, plus the gland bodies outside |
| Seal | EPDM closed-cell sponge strip, 8 × 3 mm. It sits on the flange land 3–11 mm from the wall and is compressed 25 % (3.0 → 2.25 mm). 2.25 mm spacers at each screw stop the lid, so the screws cannot over-compress the gasket. The screws are outside the gasket line. |
| Fasteners | 12 × PEM CLS-M4-1 self-clinching nuts in the flange. 12 × M4 screws through Ø4.5 lid holes |
| Pi mounting | 4 × PEM FHA-M2.5-12 flush-head studs, on the hole pattern of the official drawing. Each takes a 6 mm spacer (Ø5 / 2.7) and an M2.5 nut. The studs are blind, so there is no hole through the base. PEM's blind standoffs (BSO) start at M3, which is too big for the Pi's 2.7 mm holes. |
| Cable entries | M16×1.5 gland (cable 4–10 mm) in line with the Ethernet jack. PG7 gland (cable 2–6 mm) in line with the USB-C power plug |

Why no port openings: an opening for a USB or Ethernet jack cannot be IP65 without a sealed panel connector. The Pi
therefore sits inside with its cables plugged in, and they leave through rated glands. "Port clearance" here means the
plugged connectors (RJ45 with boot, USB-C overmold) keep at least 0.5 mm from walls, lid and glands. They keep 6.65 mm
and 2.8 mm.

## Results (verify/report.json)

These are my own checks (`verify/verify.py`, 34 of 34). The reviewer's independent checker is being updated to match.

| Check | Result |
|---|---|
| Body and lid are one valid solid each. The STEP re-imports unchanged and the STL is watertight. | pass |
| Thickness, measured skin to skin by ray casting | 1.4998–1.4999 mm everywhere |
| The STEP is unfolded independently: each section strip area ÷ t gives a length, the K correction is applied, and the result is compared with the DXF flat. | body 276.383 / 236.383 mm, lid 218.192 / 178.192 mm. Equal to the DXF to 0.000 mm |
| Flat area × t, K-corrected, against the STEP volume | 0.00 % difference |
| Every DXF hole folded back to 3D lands on a STEP hole of the same size | 18 + 12 holes, 0.000 mm error |
| Hole edge to bend zone (≥ 2t + r = 4.5 required) | body 6.65 mm, lid 4.75 mm |
| PEM CLS-M4 centre to sheet edge (≥ 6.9 required, PEM data) | 7.5 mm |
| Flange lengths against SendCutSend's 7.7 mm minimum | wall 42, flange 25, skirt 9.25 mm |
| Gasket compression against the 20–30 % IP-rated range | 25 % |
| Bend reliefs against SendCutSend's guide (width ≥ t/2, depth ≥ t + r + 0.5) | 0.75 wide, 3.5 deep |
| Interference between body, lid, gasket, spacers, nuts, studs, Pi spacers and nuts, glands, Pi envelope and plugs | 0 for every pair |

`verify/break_test.py` breaks the design seven ways, and each break fails the check it should:
- K 0.33 in the flat but 0.42 in the check.
- Nut holes 3 mm from the wall.
- M16 gland 8 mm above the base.
- Gasket squeezed 40 %.
- Pi pushed against a wall.
- Flange cut to 20 mm.
- Relief only 2 mm deep.

## Files

| Path | What |
|---|---|
| `deliver/body.step`, `deliver/lid.step` | one solid each, in the assembly frame |
| `deliver/assembly.step` | body, lid, Pi 4 envelope from the official drawing, plugs, gasket, spacers, PEM parts, glands |
| `deliver/body_flat.dxf`, `deliver/lid_flat.dxf` | blanks in mm: outline as one closed polyline on `OUTLINE`, holes as circles on `HOLES`, one line per bend on `BEND`, bend notes on `NOTES` |
| `deliver/drawing/` | fabrication drawings, A3 1:2: body flat, lid flat (bend table with order, hole table), assembly with BOM |
| `deliver/render/` | renders |
| `report.json`, `spec.json` | measured values, and the dimensions this design commits to |
| `sm/params.py` | every number, with its source |

Run everything with `python run_all.py` (Python 3.11 with build123d 0.13, trimesh, vtk, ezdxf; PyMuPDF for the PDFs).

## Bend order

Bend the four flanges first (DOWN 90°), then the four walls (UP 90°), then weld the corners, reliefs and mitres.
The lid's four skirts are DOWN 90°. The step column in the bend tables gives the sequence. On the wall bends the
finished 23.5 mm flanges hang off the tool, so confirm with the fabricator that their box-and-pan brake clears them.

## Welding and the gasket land

The flange mitres run about 23 mm across the gasket land, and TIG welding 1.5 mm aluminium will pull the land out of
flat. Require a gasket-land flatness of 0.3 mm after welding, using a fixture or a light skim. The tolerance matters
because the 2.25 mm spacers fix the lid height. A land that is 0.5 mm low in places drops the local compression from
25 % to about 8 %, which is too little to seal. A tighter weld gap at the corners (now 2.1 mm) would reduce the
distortion.

## Sources

- **Raspberry Pi 4 B:** the official mechanical drawing, https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-mechanical-drawing.pdf,
  downloaded 2026-11-18.
  - Hole pattern, connector centres and component heights are taken from its dimensions.
  - Each connector's box size is read from the drawn outline, because the drawing does not dimension it.
- **K-factor and minimum flange:** SendCutSend bending calculator. 5052 minimum bend radius 1 × t: SendCutSend 5052 page.
- **PEM CLS-M4-1:** hole 5.41, minimum sheet 1.0, centre to edge 6.9 (pemnet.com).
- **PEM FHA-M2.5-12:** hole 2.5 (+0.08), minimum sheet 1, centre to edge 5.4 (PEM FH bulletin, p. FH-5). The BSO table (PEM SO bulletin, p. SO-4) shows no M2.5.
- **Bend reliefs:** SendCutSend relief guide, as cited in review.
- **Glands:** Lapp SKINTOP data sheets and thread table. M16 entry hole 16.0–16.2, PG7 12.5–12.8.
- **Gasket compression:** Stockwell Elastomerics, 20–30 % for IP-rated seals.

The full URLs are in `sm/params.py` → `SOURCES`.

## Not certain

1. Bend data. SendCutSend's K 0.42 is for 1.6 mm (0.063 in) 5052 on their own tooling, with an effective inside
   radius of 0.89 mm. The radius matters more than K here:
   - An air bend in 5052-H32 1.5 mm over a 12 mm V-die gives an inside radius of about 1.9 mm (≈ 0.16 × V). That
     changes each bend by about +0.6 mm.
   - K anywhere from 0.38 to 0.45 moves it by only −0.09 / +0.07 mm.

   Get the fabricator's inside radius and K, or their bend deduction, and re-run before cutting.
2. Plug lengths. The USB-C plug with strain relief (30 mm) has no source. The RJ45 plug is a 22.5 mm booted plug
   (Delock) plus a margin. Measure the cables you will use.
3. PEM part envelopes. The nut barrels and studs in the assembly are envelopes, not data-sheet bodies. The M4 screw
   length must be checked against the CLS-M4-1 thread length. A flush-head stud has no through hole, but the press
   fit is metal to metal; add a drop of thread sealant under each head if the IP65 target must hold.
4. Hardware sizes. The PG7 hole (12.7 mm) is in the middle of the 12.5–12.8 range quoted by different makers; use
   the value of the gland you buy. The gland locknut size was not found and is modelled from the body wrench size.
5. Corner seal. The seal at the corners depends on the welds. The corner gaps, the 0.75 × 3.5 mm reliefs and the
   flange mitres must be welded closed, and the land kept flat to 0.3 mm (see above).
