import copy
import io

import pytest
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas

from app.services.export_service import export
from app.services.pdf_export import blueprint_pdf  # Registers the embedded fonts.
from app.services.pdf_diagrams import diagram_figures, cardinalities
from app.services.report_presentation import prepare_report
from app.models.final_report import validate_consistency
from tests.test_final_report import generated


def er_model(content):
    return next(d for s in content['final_report']['sections'] for d in s['diagrams'] if d['kind'] == 'er')


def test_er_is_vector_boxes_and_connectors_not_only_a_text_listing():
    diagram = er_model(generated())
    figures = list(diagram_figures(diagram, 490))
    assert len(figures) == 1
    figure, relationships = figures[0]
    out = io.BytesIO()
    canvas = Canvas(out)
    figure.drawOn(canvas, 40, 500)
    canvas.save()
    page = PdfReader(io.BytesIO(out.getvalue())).pages[0]
    text = page.extract_text()
    assert 'Invoice' in text and 'AuditEvent' in text
    assert 'id PK' in text and 'invoice_id FK' in text and 'R1' in text
    assert 'Context: Invoice importer' in text
    operations = [op for _, op in page.get_contents().operations]
    assert operations.count(b're') == 2  # Two bordered entity boxes.
    assert operations.count(b'l') >= 8  # Connector, dividers and cardinality markers.
    assert relationships[0][1]['label'] == diagram['edges'][0]['label']


@pytest.mark.parametrize('label,expected', [
    ('1 to 0..many; Invoice.id -> Audit.invoice_id', ('1', '0..*')),
    ('0..1 to 1..*: optional owner', ('0..1', '1..*')),
    ('1:1 mapping', ('1', '1')),
    ('Requires validation', ('', '')),
])
def test_cardinalities_are_only_drawn_when_explicit(label, expected):
    assert cardinalities(label) == expected


def test_large_er_preserves_every_entity_and_relationship_without_shrinking():
    content = generated()
    diagram = er_model(content)
    diagram['nodes'] = [dict(id=f'e{i}', label=f'Entity{i}\nid UUID PK\nparent_id UUID FK',
                             lane='Data', kind='entity') for i in range(30)]
    diagram['edges'] = [dict(source=f'e{i}', target=f'e{(i+1) % 29}',
                             label=f'1 to 0..*: relationship-{i}-end') for i in range(29)]
    diagram['edges'].append(dict(source='e0', target='e0', label='0..1 to 0..*: self-reference-end'))
    figures = list(diagram_figures(diagram, 490))
    assert all(figure.height < 560 for figure, _ in figures)
    assert sum(len(edges) for _, edges in figures) == len(diagram['edges'])
    payload = blueprint_pdf(content['final_report']['title'], content)
    pdf = PdfReader(io.BytesIO(payload))
    text = '\n'.join(page.extract_text() for page in pdf.pages)
    for node in diagram['nodes']:
        assert node['label'].splitlines()[0] in text
    for edge in diagram['edges']:
        assert edge['label'].split(': ', 1)[1] in text
    assert 'Entity29' in text  # Unrelated entities are not dropped.


def test_cleanup_preserves_distinct_content_and_never_mutates_saved_report():
    report = generated()['final_report']
    first = report['sections'][0]
    first['narrative'] = 'A specific finding.\n\nA specific finding.'
    first['items'] = ['A specific finding.', 'Unique detail', 'Unique   detail', 'CaseSensitiveID', 'casesensitiveid']
    first['tables'] = [dict(title='Requirements', columns=['ID', 'Requirement'],
                           rows=[['1', 'Preserve this'], ['1', 'Preserve this']])] * 2
    diagram = er_model({'final_report': report})
    first['diagrams'] = [copy.deepcopy(diagram), copy.deepcopy(diagram)]
    original = copy.deepcopy(report)
    cleaned = prepare_report(report)
    assert report == original
    assert cleaned['sections'][0]['narrative'] == 'A specific finding.'
    assert cleaned['sections'][0]['items'] == ['Unique detail', 'CaseSensitiveID', 'casesensitiveid']
    assert cleaned['sections'][0]['tables'][0]['rows'] == [['1', 'Preserve this']]
    assert len(cleaned['sections'][0]['tables']) == 1
    assert sum(len(s['diagrams']) for s in cleaned['sections']) == sum(len(s['diagrams']) for s in original['sections']) - 2


def test_minimal_pdf_has_numbered_contents_and_one_code_specification():
    content = generated()
    pdf = PdfReader(io.BytesIO(export('Formal blueprint', content, 'pdf')))
    text = '\n'.join(page.extract_text() for page in pdf.pages)
    assert 'Contents' in pdf.pages[0].extract_text()
    assert '1. Executive summary' in text
    assert 'Technical appendix: implementation specifications' in text
    assert 'AuditEvent.invoice_id -> Invoice.id' in text
    assert text.count('CREATE TABLE Invoice') == 1
    assert 'component_refs' not in text and 'No outgoing connection' not in text
    # The PDF draws only grayscale colors, including diagram fills and table headers.
    for page in pdf.pages:
        for operands, operator in page.get_contents().operations:
            if operator in (b'rg', b'RG'):
                assert len(set(operands)) == 1


@pytest.mark.parametrize('change', ['missing_er', 'missing_entity', 'not_applicable', 'unlabelled_relationship'])
def test_canonical_business_records_cannot_lose_their_er_model(change):
    content = generated()
    chapter = next(c for c in content['data_report']['chapters'] if c['key'] == 'data_model')
    if change == 'missing_er':
        chapter['diagrams'] = []
    if change == 'missing_entity':
        chapter['diagrams'][0]['nodes'][1]['label'] = 'Unrelated record'
    if change == 'not_applicable':
        chapter.update(applicability='not_applicable', diagrams=[])
    if change == 'unlabelled_relationship':
        chapter['diagrams'][0]['edges'][0]['label'] = ''
    with pytest.raises(ValueError):
        validate_consistency(content['option_decision'], content['solution'], content)
