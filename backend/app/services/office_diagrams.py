"""Render the same validated PDF figures into high-resolution Office pictures."""
import io
import threading
from reportlab.pdfgen.canvas import Canvas


_pdfium_lock = threading.Lock()


def figure_png(figure):
    # PDFium's process-wide native state is not safe for simultaneous threads.
    with _pdfium_lock:
        return _figure_png(figure)


def _figure_png(figure):
    import pypdfium2
    out = io.BytesIO()
    canvas = Canvas(out, pagesize=(figure.width + 16, figure.height + 16))
    figure.drawOn(canvas, 8, 8)
    canvas.save()
    document = pypdfium2.PdfDocument(out.getvalue())
    try:
        page = document[0]
        try:
            bitmap = page.render(scale=2)
            try:
                image = io.BytesIO()
                bitmap.to_pil().save(image, format='PNG')
                image.seek(0)
                return image
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()


def section_figures(section):
    # Register the report fonts before rendering the common figure classes.
    from app.services import pdf_export  # noqa: F401
    from app.services.pdf_diagrams import diagram_figures, wireframe_figures
    for diagram in section.get('diagrams', []):
        for figure, _ in diagram_figures(diagram, 490):
            yield diagram['title'], figure
    for screen in section.get('screens', []):
        for figure in wireframe_figures(screen, 490):
            yield screen['name'], figure
