"""
tests/unit/test_ai_reasoning_audit_isolation.py

Extends Phase 7's "zero live influence" guarantee
(test_ai_reasoning_isolation.py) to cover core/persistence/
ai_reasoning_audit.py too. That file deliberately lives OUTSIDE
core/ai_reasoning/ (see its own module docstring for why), so
Samarth's isolation test — which specifically scans core/ai_reasoning/
— never sees it. This is a separate, small test doing the exact same
check (same AST-based technique, not text/regex matching, following
the established precedent from test_research_boundary.py and
test_ai_reasoning_isolation.py) for the one file that would otherwise
fall outside both nets.
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


def test_ai_reasoning_audit_never_imports_execution_or_risk():
    filepath = "core/persistence/ai_reasoning_audit.py"
    forbidden_prefixes = ("core.execution", "core.risk")

    imports = get_imports(filepath)
    violations = [imp for imp in imports if imp.startswith(forbidden_prefixes)]

    assert not violations, (
        f"{filepath} imports from execution/risk - violates zero live "
        f"influence: {violations}"
    )


def test_ai_reasoning_audit_file_exists():
    """Sanity check the scan target itself is real, not silently checking nothing."""
    assert os.path.isfile("core/persistence/ai_reasoning_audit.py")