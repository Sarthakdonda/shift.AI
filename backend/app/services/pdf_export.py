"""Minimal, paginated PDFs with searchable text and actual vector diagrams."""
import io
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, PageBreak, Preformatted, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

from app.services.export_service import lines
from app.services.pdf_diagrams import diagram_figures, entity_parts, pdf_text
from app.services.report_presentation import prepare_report, fingerprint


_fonts = Path(reportlab.__file__).parent / 'fonts'
pdfmetrics.registerFont(TTFont('Blueprint', str(_fonts / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('BlueprintBold', str(_fonts / 'VeraBd.ttf')))


class ReportDocument(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == 'Chapter':
            self.notify('TOCEntry', (0, escape(flowable.getPlainText()), self.page))


def blueprint_pdf(title, content):
    out = io.BytesIO()
    doc = ReportDocument(out, pagesize=A4, rightMargin=42, leftMargin=42,
                         topMargin=42, bottomMargin=42, title=title, author='shift.AI')
    body = ParagraphStyle('Body', fontName='Blueprint', fontSize=9, leading=13,
                          spaceAfter=7, textColor=colors.HexColor('#222222'))
    heading = ParagraphStyle('Chapter', parent=body, fontName='BlueprintBold',
                             fontSize=13, leading=17, spaceBefore=14,
                             spaceAfter=9, keepWithNext=True)
    subheading = ParagraphStyle('Subheading', parent=heading, fontSize=10, leading=14)
    cover = ParagraphStyle('Title', parent=heading, fontSize=20, leading=26)
    cell = ParagraphStyle('Cell', parent=body, fontSize=8, leading=11, spaceAfter=0)
    header_cell = ParagraphStyle('HeaderCell', parent=cell, fontName='BlueprintBold')
    note = ParagraphStyle('Note', parent=body, fontSize=8, leading=11, textColor=colors.HexColor('#555555'))
    legend = ParagraphStyle('DiagramLegend', parent=note, keepWithNext=True)
    code = ParagraphStyle('Code', fontName='Courier', fontSize=8, leading=10, spaceAfter=8)

    def paragraph(value, style=body):
        # Saved report text is content, never executable PDF/HTML markup.
        return Paragraph(escape(pdf_text(value)).replace('\n', '<br/>'), style)

    def add_table(table):
        columns = table['columns']
        if not columns or not table['rows']:
            return
        story.append(paragraph(table['title'], subheading))
        rows = [[paragraph(value, header_cell) for value in columns]]
        rows += [[paragraph(value, cell) for value in row] for row in table['rows']]
        widths = [doc.width * .28, doc.width * .72] if len(columns) == 2 else [doc.width / len(columns)] * len(columns)
        story.append(LongTable(rows, colWidths=widths, repeatRows=1, splitInRow=1, style=[
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f2f2f2')),
            ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#bdbdbd')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(Spacer(1, 7))

    story = [paragraph(title, cover), paragraph('Strategy and implementation blueprint', subheading)]
    report = prepare_report(content['final_report']) if content.get('final_report') else None
    if report:
        if report.get('report_version'):
            prepared = str(report.get('prepared_at', ''))[:10]
            story.append(paragraph(f"Version {report['report_version']} | Prepared {prepared}", note))
        story.append(paragraph(f"Industry: {report['industry']} | Language: {report['language']} | Selected option: {report['selected_option']}", note))
        story.append(paragraph('Proposed implementation design. Validate evidence, estimates and unresolved risks before approval.', note))
        story.append(paragraph('Contents', subheading))
        toc = TableOfContents()
        toc.levelStyles = [ParagraphStyle('ContentsEntry', parent=body, fontSize=8, leading=11, spaceBefore=0, spaceAfter=0)]
        toc.tableStyle = TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0),
                                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                    ('TOPPADDING', (0, 0), (-1, -1), 1),
                                    ('BOTTOMPADDING', (0, 0), (-1, -1), 1)])
        story.extend([toc, PageBreak()])
        seen_basis = set()
        assets = []
        er_legend = False
        for i, section in enumerate(report['sections'], 1):
            story.append(paragraph(f"{i}. {section['title']}", heading))
            if section['applicability'] == 'not_applicable':
                story.append(paragraph('Not applicable. ' + section['narrative']))
            else:
                story.extend(paragraph(part) for part in section['narrative'].split('\n\n') if part.strip())
            basis = fingerprint(section['basis'])
            if basis and basis not in seen_basis:
                seen_basis.add(basis)
                story.append(paragraph('Evidence / assumptions: ' + section['basis'], note))
            story.extend(paragraph('• ' + item) for item in section['items'])
            # Put the ER model before the detailed field catalogue it explains.
            for diagram in section['diagrams']:
                story.append(paragraph(diagram['title'], subheading))
                if diagram['kind'] == 'er' and not er_legend:
                    story.append(paragraph('Entity relationship diagram. PK = primary key; FK = foreign key. '
                                           'A bar means one, a circle means optional, and a fork means many. '
                                           'Relationship references (R) identify the definitions below.', legend))
                    er_legend = True
                names = {n['id']: entity_parts(n)[0] if diagram['kind'] == 'er' else n['label'] for n in diagram['nodes']}
                for figure, relationships in diagram_figures(diagram, doc.width - 12):
                    story.append(figure)
                    for number, edge in relationships:
                        story.append(paragraph(f"R{number}. {names[edge['source']]} — {names[edge['target']]}: {edge['label']}", note))
                    story.append(Spacer(1, 7))
            for table in section['tables']:
                add_table(table)
            for screen in section['screens']:
                story.append(paragraph(screen['name'], subheading))
                story.append(paragraph(screen['persona'] + ': ' + screen['purpose']))
                add_table({'title': 'Screen controls', 'columns': ['Control', 'Purpose and behavior'],
                           'rows': [[control['label'], control['detail']] for control in screen['controls']]})
            for asset in section['code_assets']:
                story.append(paragraph(f"Supporting specification: {asset['filename']} (technical appendix).", note))
                assets.append(asset)
        if assets:
            story.extend([PageBreak(), paragraph('Technical appendix: implementation specifications', heading)])
            for asset in assets:
                story.append(paragraph(asset['filename'], subheading))
                story.append(Preformatted(pdf_text(asset['content']), code, maxLineLength=95))
    else:
        for depth, text in lines(content):
            story.append(paragraph(text, subheading if depth <= 1 and len(text) < 150 else body))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Blueprint', 8)
        canvas.setFillColor(colors.HexColor('#555555'))
        canvas.drawString(42, 24, 'shift.AI | Implementation blueprint')
        canvas.drawRightString(A4[0] - 42, 24, str(document.page))
        canvas.restoreState()

    doc.multiBuild(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
