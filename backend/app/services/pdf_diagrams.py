"""Print-sized vector diagrams built from saved nodes/edges, without model code."""
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Flowable, Paragraph

INK = colors.HexColor('#222222')


def pdf_text(value):
    # Vera has no arrow glyphs. Printable equivalents preserve relation direction
    # instead of silently drawing missing-glyph squares in field definitions.
    return str(value).translate(str.maketrans({'→': '->', '←': '<-', '↔': '<->', '⇒': '=>', '⇐': '<='}))


def entity_parts(node):
    # Existing reports encode entity names and key fields in the node label.
    parts = [part.strip() for part in re.split(r'\n|\s*[·|]\s*', node['label']) if part.strip()]
    return parts[0], parts[1:]


def cardinalities(label):
    match = re.match(r'^\s*(0\.\.1|1|0\.\.(?:many|\*)|1\.\.(?:many|\*)|many|\*)\s*'
                     r'(?:to|:|→|—|--|-)\s*(0\.\.1|1|0\.\.(?:many|\*)|1\.\.(?:many|\*)|many|\*)(?=\s|;|,|:|$)', label, re.I)
    if not match:
        return '', ''
    return tuple(value.lower().replace('many', '*') for value in match.groups())


class TextBlock(Flowable):
    """A paragraph at an exact diagram position; keeps Unicode text searchable."""
    def __init__(self, text, width, bold=False):
        super().__init__()
        style = ParagraphStyle('DiagramText', fontName='BlueprintBold' if bold else 'Blueprint',
                               fontSize=9, leading=12, textColor=INK)
        self.paragraph = Paragraph(escape(pdf_text(text)), style)
        self.width, self.height = self.paragraph.wrap(width, 1000)

    def draw(self):
        self.paragraph.drawOn(self.canv, 0, 0)


class DiagramFigure(Flowable):
    """Six entities per overview; large models use complete relationship views."""
    def __init__(self, nodes, edges, width, er=False, edge_offset=0):
        super().__init__()
        self.width = width
        self.er = er
        self.edges = edges
        self.edge_offset = edge_offset
        self.box_width = (width - 105) / 2
        self.nodes = []
        self.positions = {}
        row_heights = []
        for index, node in enumerate(nodes):
            title, fields = entity_parts(node) if er else (node['label'], [])
            if node.get('kind') in ('start', 'decision', 'end'):
                fields.append(node['kind'].title())
            if node.get('lane'):
                fields.append('Context: ' + node['lane'])
            blocks = [TextBlock(title, self.box_width - 16, True)]
            blocks += [TextBlock(field, self.box_width - 16) for field in fields]
            height = max(48, sum(block.height for block in blocks) + 20 + (5 if fields else 0))
            if index % 2 == 0:
                row_heights.append(height)
            else:
                row_heights[-1] = max(row_heights[-1], height)
            self.nodes.append((node, blocks, height))
        self.height = sum(row_heights) + max(0, len(row_heights) - 1) * 44 + 32
        y = self.height - 16
        for index, (node, blocks, height) in enumerate(self.nodes):
            row = index // 2
            if index and index % 2 == 0:
                y -= row_heights[row - 1] + 44
            x = 24 + (index % 2) * (self.box_width + 57)
            self.positions[node['id']] = (x, y - height, height)

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeColor(INK)
        canvas.setFillColor(INK)
        canvas.setLineWidth(.7)
        for index, edge in enumerate(self.edges):
            ax, ay, ah = self.positions[edge['source']]
            bx, by, bh = self.positions[edge['target']]
            ay += ah / 2
            by += bh / 2
            if ax != bx:
                direction = 1 if ax < bx else -1
                start = ax + (self.box_width if direction == 1 else 0)
                end = bx + (0 if direction == 1 else self.box_width)
                rail = self.width / 2 + ((index % 3) - 1) * 7
                points = [(start, ay), (rail, ay), (rail, by), (end, by)]
                label_x, label_y = rail, (ay + by) / 2 + 5
            else:
                direction = -1 if ax < self.width / 2 else 1
                start = ax + (0 if direction == -1 else self.box_width)
                end = start
                rail = start + direction * (12 + (index % 3) * 4)
                if edge['source'] == edge['target']:
                    by = ay - ah / 3
                points = [(start, ay), (rail, ay), (rail, by), (end, by)]
                label_x, label_y = rail, (ay + by) / 2 + 4
            path = canvas.beginPath()
            path.moveTo(*points[0])
            for point in points[1:]:
                path.lineTo(*point)
            canvas.drawPath(path)
            canvas.setFont('Blueprint', 7)
            canvas.drawCentredString(label_x, label_y, f'R{index + self.edge_offset + 1}')
            if self.er:
                source, target = cardinalities(edge.get('label', ''))
                self.marker(canvas, start, ay, direction, source)
                self.marker(canvas, end, by, direction if ax == bx else -direction, target)
            else:
                # Arrow points into the target; ER connections are not process arrows.
                approach = direction if ax == bx else -direction
                canvas.line(end, by, end + approach * 5, by + 3)
                canvas.line(end, by, end + approach * 5, by - 3)
        for node, blocks, height in self.nodes:
            x, y, _ = self.positions[node['id']]
            canvas.setFillColor(colors.white)
            canvas.rect(x, y, self.box_width, height, stroke=1, fill=1)
            canvas.setFillColor(INK)
            cursor = y + height - 8
            for index, block in enumerate(blocks):
                cursor -= block.height
                block.drawOn(canvas, x + 8, cursor)
                if index == 0 and len(blocks) > 1:
                    cursor -= 3
                    canvas.line(x, cursor, x + self.box_width, cursor)
                    cursor -= 5
        canvas.restoreState()

    @staticmethod
    def marker(canvas, x, y, outward, cardinality):
        if not cardinality:
            return
        if '*' in cardinality:
            for offset in (-4, 0, 4):
                canvas.line(x, y + offset, x + outward * 8, y)
        else:
            canvas.line(x + outward * 5, y - 4, x + outward * 5, y + 4)
        if cardinality.startswith('0'):
            canvas.setFillColor(colors.white)
            canvas.circle(x + outward * 13, y, 2.5, stroke=1, fill=1)
            canvas.setFillColor(INK)
        elif cardinality != '*':
            canvas.line(x + outward * 12, y - 4, x + outward * 12, y + 4)


def diagram_figures(diagram, width):
    nodes, edges = diagram['nodes'], diagram['edges']
    er = diagram['kind'] == 'er'
    # Keep readable 9pt labels; never shrink a large schema onto one page.
    overview = DiagramFigure(nodes, edges, width, er)
    if len(nodes) <= 6 and len(edges) <= 8 and overview.height <= 560:
        yield overview, list(enumerate(edges, 1))
        return
    by_id = {node['id']: node for node in nodes}
    used = set()
    for index, edge in enumerate(edges):
        ids = list(dict.fromkeys([edge['source'], edge['target']]))
        used.update(ids)
        yield DiagramFigure([by_id[key] for key in ids], [edge], width, er, index), [(index + 1, edge)]
    for node in nodes:
        if node['id'] not in used:
            yield DiagramFigure([node], [], width, er), []
