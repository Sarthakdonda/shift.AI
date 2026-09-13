"""Paginated PDF downloads for current and legacy blueprints."""
import io
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer

from app.services.export_service import lines, visual_lines


# Embed the portable fonts shipped with ReportLab instead of relying on OS fonts.
_fonts = Path(reportlab.__file__).parent / 'fonts'
pdfmetrics.registerFont(TTFont('Blueprint', str(_fonts / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('BlueprintBold', str(_fonts / 'VeraBd.ttf')))


def blueprint_pdf(title, content):
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=40, leftMargin=40,
                            topMargin=42, bottomMargin=42, title=title, author='shift.AI')
    body = ParagraphStyle('Body', fontName='Blueprint', fontSize=9, leading=14,
                          spaceAfter=7, textColor=colors.HexColor('#253342'))
    heading = ParagraphStyle('Heading', parent=body, fontName='BlueprintBold',
                             fontSize=15, leading=20, spaceBefore=14,
                             spaceAfter=10, keepWithNext=True)
    subheading = ParagraphStyle('Subheading', parent=heading, fontSize=11, leading=15)
    cover = ParagraphStyle('Cover', parent=heading, fontSize=24, leading=30)
    cell = ParagraphStyle('Cell', parent=body, fontSize=8, leading=11, spaceAfter=0)

    def paragraph(value, style=body):
        # Saved report text is content, never ReportLab markup.
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), style)

    story = [paragraph(title, cover), paragraph('shift.AI · Strategy & implementation blueprint')]
    report = content.get('final_report')
    if report:
        if report.get('report_version'):
            story.append(paragraph(f"Version {report['report_version']} · Prepared {report['prepared_at']}"))
        story.append(paragraph(f"Industry: {report['industry']} · Language: {report['language']} · Selected option: {report['selected_option']}"))
        for i, section in enumerate(report['sections'], 2):
            story.append(paragraph(f"{i}. {section['title']}", heading))
            if section['applicability'] == 'not_applicable':
                story.append(paragraph('Not applicable — rationale below.'))
            story.extend([paragraph(section['narrative']),
                          paragraph('Evidence / assumptions: ' + section['basis'])])
            story.extend(paragraph('• ' + item) for item in section['items'])
            for table in section['tables']:
                story.append(paragraph(table['title'], subheading))
                columns = table['columns']
                if not columns:
                    continue
                rows = [[paragraph(value, cell) for value in row]
                        for row in [columns, *table['rows']]]
                story.append(LongTable(rows, colWidths=[doc.width / len(columns)] * len(columns),
                                       repeatRows=1, splitInRow=1, style=[
                                           ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef2')),
                                           ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#cbd5df')),
                                           ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                           ('LEFTPADDING', (0, 0), (-1, -1), 6),
                                           ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                                           ('TOPPADDING', (0, 0), (-1, -1), 6),
                                           ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                                       ]))
                story.append(Spacer(1, 8))
            for depth, text in visual_lines(section):
                story.append(paragraph(text, subheading if depth == 1 else body))
    else:
        for depth, text in lines(content):
            story.append(paragraph(text, subheading if depth <= 1 and len(text) < 150 else body))
    story.append(paragraph('Advisory design. Validate evidence, assumptions and material risks before implementation.'))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Blueprint', 8)
        canvas.setFillColor(colors.HexColor('#687583'))
        canvas.drawString(40, 24, 'shift.AI · Blueprint')
        canvas.drawRightString(A4[0] - 40, 24, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
