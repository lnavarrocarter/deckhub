"""Mensajes de error del daemon (raise ...("texto")) para traducirlos en el panel."""
import ast
import json
import pathlib
import sys

keys = []


def text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = text(node.left), text(node.right)
        return a + b if a is not None and b is not None else None
    return None


for f in pathlib.Path("py_modules/deckhub").rglob("*.py"):
    for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
        call = None
        if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call):
            call = n.exc
        elif isinstance(n, ast.Dict):  # {"error": "..."}
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value in ("error", "reason") and text(v):
                    keys.append(text(v))
        if call and call.args:
            t = text(call.args[0])
            if t and any(c.isalpha() for c in t) and t not in keys:
                keys.append(t)
json.dump(keys, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False)
print(len(keys))
