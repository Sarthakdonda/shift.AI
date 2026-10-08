"""Bounded pure business functions. Shared static validation never executes source."""
import ast
import json
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CALLS = {'calculate', 'abs', 'min', 'max', 'sum', 'len', 'round', 'int', 'float', 'str', 'bool', 'sorted', 'range', 'money', 'number'}
NODES = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Assign, ast.AugAssign,
    ast.If, ast.For, ast.Break, ast.Continue, ast.Pass, ast.Expr, ast.IfExp, ast.BoolOp, ast.BinOp,
    ast.UnaryOp, ast.Compare, ast.Call, ast.Name, ast.Load, ast.Store, ast.Constant, ast.Dict,
    ast.List, ast.Tuple, ast.Subscript, ast.Slice, ast.Attribute, ast.keyword,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.USub, ast.UAdd, ast.Not,
    ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot)


def check_source(source):
    if not isinstance(source, str) or len(source) > 12000:
        raise ValueError('Business function source must be at most 12,000 characters.')
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError('Business function has invalid Python syntax.') from exc
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError('Provide exactly one calculate(record) function.')
    function = tree.body[0]
    if function.name != 'calculate' or function.decorator_list or function.returns or function.args.defaults or function.args.kw_defaults or function.args.vararg or function.args.kwarg or function.args.kwonlyargs or function.args.posonlyargs or len(function.args.args) != 1 or function.args.args[0].arg != 'record':
        raise ValueError('Business logic must define calculate(record) without decorators or default arguments.')
    nodes = list(ast.walk(tree))
    if len(nodes) > 1500:
        raise ValueError('Business function is too complex.')
    for node in nodes:
        if not isinstance(node, NODES) or (isinstance(node, ast.FunctionDef) and node is not function):
            raise ValueError('Unsupported business logic statement: ' + type(node).__name__)
        if isinstance(node, ast.Name) and node.id.startswith('_'):
            raise ValueError('Private names are not available to business functions.')
        if isinstance(node, ast.arg) and node.annotation:
            raise ValueError('Annotations are not supported.')
        if isinstance(node, ast.Attribute) and (node.attr != 'get' or not isinstance(node.ctx, ast.Load)):
            raise ValueError('Only dictionary get() is available; imports, I/O and reflection are disabled.')
        if isinstance(node, ast.Call) and not ((isinstance(node.func, ast.Name) and node.func.id in CALLS) or (isinstance(node.func, ast.Attribute) and node.func.attr == 'get')):
            raise ValueError('Unsupported business function call.')
    return tree


def run_logic(source, record):
    # This subprocess runs inside the generated application's Docker boundary.
    completed = subprocess.run([sys.executable, '-I', '-S', str(Path(__file__).resolve()), '--worker'],
        input=json.dumps({'source': source, 'record': record}), text=True, capture_output=True,
        timeout=3, env={}, cwd=Path(__file__).parent)
    if completed.returncode or len(completed.stdout) > 65536:
        raise ValueError('Business calculation failed. Check the approved rule and inputs.')
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError('Business calculation must return field values.')
    return value


def worker():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    except ImportError:
        pass
    value = json.loads(sys.stdin.read(80000))
    tree = check_source(value['source'])
    builtins = {'abs': abs, 'min': min, 'max': max, 'sum': sum, 'len': len, 'round': round,
        'int': int, 'float': float, 'str': str, 'bool': bool, 'sorted': sorted, 'range': range,
        'number': lambda value: Decimal(str(value)),
        'money': lambda value: float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))}
    namespace = {'__builtins__': builtins}
    exec(compile(tree, '<approved business function>', 'exec'), namespace)
    result = namespace['calculate'](value['record'])
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    worker()
