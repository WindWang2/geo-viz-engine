import ast
from pathlib import Path


def test_geoviz_does_not_import_paleo_workbench():
    root = Path(__file__).resolve().parents[1] / "geoviz"
    violations = []

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots = [node.module.split(".", 1)[0]]
            else:
                continue
            if "paleo_workbench" in roots:
                violations.append(str(path.relative_to(root.parent)))

    assert not violations, violations
