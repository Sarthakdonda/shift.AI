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
            canvas.setStrokeColor(colors.HexColor('#8c9dad'))
            if not self.er and node.get('kind') == 'decision':
                path = canvas.beginPath()
                path.moveTo(x + 10, y)
                for px, py in [(x+self.box_width-10,y),(x+self.box_width,y+height/2),
                               (x+self.box_width-10,y+height),(x+10,y+height),(x,y+height/2)]:
                    path.lineTo(px, py)
                path.close()
                canvas.drawPath(path, stroke=1, fill=1)
            else:
                canvas.roundRect(x, y, self.box_width, height,
                                 12 if node.get('kind') in ('start', 'end') else 3, stroke=1, fill=1)
            canvas.setFillColor(colors.HexColor('#eef3f7'))
            canvas.rect(x+1, y+height-blocks[0].height-12, self.box_width-2, blocks[0].height+11, stroke=0, fill=1)
            canvas.setStrokeColor(INK)
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
    if any(edge['source'] not in by_id or edge['target'] not in by_id for edge in edges):
        raise ValueError('Diagram connection references a missing node. Edit or regenerate the diagram.')
    used = set()
    for index, edge in enumerate(edges):
        ids = list(dict.fromkeys([edge['source'], edge['target']]))
        used.update(ids)
        pair = [by_id[key] for key in ids]
        figure = DiagramFigure(pair, [edge], width, er, index)
        if figure.height <= 560:
            yield figure, [(index + 1, edge)]
        else:
            # Long field catalogues stay readable in continuation cards; the
            # relationship is shown with entity names before the complete fields.
            yield DiagramFigure([{**n, 'label': entity_parts(n)[0]} for n in pair], [edge], width, er, index), [(index + 1, edge)]
            for node in pair:
                yield from entity_continuations(node, width, er)
    for node in nodes:
        if node['id'] not in used:
            yield from entity_continuations(node, width, er)


def entity_continuations(node, width, er):
    figure = DiagramFigure([node], [], width, er)
    if figure.height <= 560:
        yield figure, []
        return
    title, fields = entity_parts(node)
    for start in range(0, len(fields), 10):
        yield DiagramFigure([{**node, 'label': title + (' (continued)' if start else '') + '\n' + '\n'.join(fields[start:start+10])}], [], width, er), []


class WireframeFigure(Flowable):
    """A real low-fidelity screen: navigation, inputs, metrics, tables and actions."""
    def __init__(self, screen, controls, width, continued=False):
        super().__init__()
        self.width = width
        self.screen = screen
        self.title = TextBlock(screen['name'] + (' (continued)' if continued else ''), width-32, True)
        self.controls = []
        for control in controls:
            label = TextBlock(control['label'], width-44, True)
            detail = TextBlock(control['detail'], width-44)
            visual = 32 if control['kind'] in ('input', 'select', 'button', 'table', 'metric') else 4
            height = label.height + detail.height + visual + 30
            self.controls.append((control, label, detail, height))
        self.height = self.title.height + 42 + sum(item[3] for item in self.controls)

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#a6b4c1'))
        canvas.setFillColor(colors.white)
        canvas.roundRect(0, 0, self.width, self.height, 5, stroke=1, fill=1)
        canvas.setFillColor(colors.HexColor('#edf2f6'))
        canvas.rect(1, self.height-self.title.height-24, self.width-2, self.title.height+23, stroke=0, fill=1)
        self.title.drawOn(canvas, 16, self.height-self.title.height-12)
        cursor = self.height-self.title.height-36
        for control, label, detail, height in self.controls:
            label.drawOn(canvas, 20, cursor-label.height)
            cursor -= label.height+8
            if control['kind'] in ('input', 'select', 'button', 'metric'):
                canvas.setFillColor(colors.HexColor('#e8eef3') if control['kind'] == 'button' else colors.white)
                canvas.roundRect(20, cursor-24, min(self.width-40, 170) if control['kind'] == 'button' else self.width-40, 24, 3, stroke=1, fill=1)
                if control['kind'] == 'select':
                    canvas.line(self.width-38,cursor-9,self.width-33,cursor-15)
                    canvas.line(self.width-33,cursor-15,self.width-28,cursor-9)
                cursor -= 32
            elif control['kind'] == 'table':
                canvas.setFillColor(colors.HexColor('#f3f5f7'))
                canvas.rect(20,cursor-24,self.width-40,24,stroke=1,fill=1)
                for x in range(1,4):
                    canvas.line(20+(self.width-40)*x/4,cursor,20+(self.width-40)*x/4,cursor-24)
                canvas.line(20,cursor-12,self.width-20,cursor-12)
                cursor -= 32
            else:
                cursor -= 4
            detail.drawOn(canvas,20,cursor-detail.height)
            cursor -= detail.height+22
        canvas.restoreState()


def wireframe_figures(screen, width):
    batch = []
    continued = False
    for control in screen['controls']:
        candidate = WireframeFigure(screen, [*batch, control], width, continued)
        if candidate.height > 540 and batch:
            yield WireframeFigure(screen, batch, width, continued)
            batch = []
            continued = True
        batch.append(control)
    if batch:
        yield WireframeFigure(screen, batch, width, continued)
