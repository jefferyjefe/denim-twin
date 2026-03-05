"""A keyword argument that the body never reads is a silent lie to the caller.

`segment_garment_consensus` carried `agreement_slack=0.25` for a day: a caller could pass it, see no error, and get no
effect. This test walks the package and fails on any function whose declared parameter never appears in its own body.
"""
import ast, os, sys
from pathlib import Path
import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "denimtwin"
ALLOW = {("__init__", "self"), }          # nothing yet; add (funcname, arg) pairs with a reason if ever needed

def _files():
    return sorted(SRC.rglob("*.py"))

def _dead_params(path):
    tree = ast.parse(path.read_text())
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
        args = node.args
        names = [a.arg for a in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)]
        if args.vararg: names.append(args.vararg.arg)
        if args.kwarg: names.append(args.kwarg.arg)
        used = set()
        for sub in ast.walk(node):
            if sub is node: continue
            if isinstance(sub, ast.Name): used.add(sub.id)
            elif isinstance(sub, ast.arg): pass
            elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)): used.add(sub.name)
        # a nested function's own parameters count as used within it (ast.walk already covers them)
        for n in names:
            if n in ("self", "cls", "_", "kw", "kwargs"): continue
            if n.startswith("_"): continue
            if (node.name, n) in ALLOW: continue
            if n not in used: out.append(f"{path.relative_to(SRC.parent.parent)}:{node.lineno} {node.name}({n}) is never read")
    return out

@pytest.mark.parametrize("path", _files(), ids=lambda p: p.name)
def test_no_declared_parameter_is_ignored(path):
    dead = _dead_params(path)
    assert not dead, "\n".join(dead)
