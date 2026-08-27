"""
Phase 7's load-bearing guarantee: zero live influence. This test proves
it structurally, not by assumption - core/ai_reasoning must never
import from core/execution or core/risk, which would be the only way
it could ever touch a real order or bypass the risk engine.

Written before the real reasoning/retrieval code, per the same
discipline Phase 6 applied to fail-safe logic: prove the safety
property first, build on top of a verified boundary.
"""
import ast
import os


def get_imports(filepath: str) -> set[str]:
    with open(filepath, "r") as f:
        tree = ast.parse(f.read(), filename=filepath)

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def test_ai_reasoning_never_imports_execution_or_risk():
    """
    Scans every .py file under core/ai_reasoning/ and fails if any of
    them import from core.execution or core.risk, directly or via
    submodule. This is the actual proof of "zero live influence" -
    not a comment, not a docstring claim, a real structural check.
    """
    ai_reasoning_dir = "core/ai_reasoning"
    forbidden_prefixes = ("core.execution", "core.risk")

    violations = []
    for root, _, files in os.walk(ai_reasoning_dir):
        for filename in files:
            if not filename.endswith(".py"):
                continue
            filepath = os.path.join(root, filename)
            imports = get_imports(filepath)
            for imp in imports:
                if imp.startswith(forbidden_prefixes):
                    violations.append((filepath, imp))

    assert not violations, (
        f"core/ai_reasoning imports from execution/risk - violates zero "
        f"live influence: {violations}"
    )


def test_ai_reasoning_directory_exists():
    """Sanity check the scan target itself is real, not silently checking nothing."""
    assert os.path.isdir("core/ai_reasoning")