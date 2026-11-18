"""DXF -> PDF + PNG preview at true scale on A3.  Python 3.11 with ezdxf + PyMuPDF."""
from pathlib import Path
import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext, layout, pymupdf, config

D = Path(__file__).resolve().parent
for n in ("body_flat", "lid_flat", "assembly"):
    doc = ezdxf.readfile(D / f"{n}.dxf")
    cfg = config.Configuration(background_policy=config.BackgroundPolicy.WHITE, color_policy=config.ColorPolicy.BLACK,
                               lineweight_scaling=0.5)
    page = layout.Page(420, 297, layout.Units.mm)
    st = layout.Settings(scale=1, fit_page=False)
    be = pymupdf.PyMuPdfBackend(); Frontend(RenderContext(doc), be, config=cfg).draw_layout(doc.modelspace())
    (D / f"{n}.pdf").write_bytes(be.get_pdf_bytes(page, settings=st))
    be2 = pymupdf.PyMuPdfBackend(); Frontend(RenderContext(doc), be2, config=cfg).draw_layout(doc.modelspace())
    (D / f"{n}.png").write_bytes(be2.get_pixmap_bytes(page, fmt="png", settings=st, dpi=110))
    print("wrote", D / f"{n}.pdf")
