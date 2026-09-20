"""Verify local imports and statically named calls on imported app objects."""
import ast
import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LocalReferenceTests(unittest.TestCase):
    def test_local_imports_and_attributes_exist(self):
        paths = list((ROOT / "app").rglob("*.py")) + [ROOT / "run.py", ROOT / "desktop.py"]
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            imported = {}
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.level or not node.module:
                    continue
                if not node.module.startswith(("app.", "tests.")):
                    continue
                module = importlib.import_module(node.module)
                for alias in node.names:
                    with self.subTest(file=path.name, line=node.lineno, symbol=alias.name):
                        self.assertTrue(hasattr(module, alias.name), f"{node.module}.{alias.name}")
                        imported[alias.asname or alias.name] = getattr(module, alias.name)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                owner = node.func.value
                if isinstance(owner, ast.Name) and owner.id in imported:
                    with self.subTest(file=path.name, line=node.lineno):
                        self.assertTrue(callable(getattr(imported[owner.id], node.func.attr, None)),
                                        f"Missing callable: {owner.id}.{node.func.attr}")
