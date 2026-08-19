"""
tests/unit/test_research_boundary.py

Enforces the explicit Phase 3 rule: "keep research/ code cleanly
separated from core/ and services/ — nothing here gets imported into
the live pipeline directly."

This isn't a technical restriction Python enforces on its own — a
teammate could accidentally `import research.storage` from inside
services/ and nothing would stop them at write-time. This test catches
it in CI instead: it parses every .py file under core/ and services/
and checks for a REAL import statement referencing "research", using
Python's own ast module — not a text/regex match.

Why ast, not regex (learned the hard way): an earlier regex-based
version of this test false-positived on core/portfolio/portfolio.py's
own docstring, which explains this exact boundary rule in prose and
happens to contain a line starting with "from research/ — which core/
and services/ are never allowed to do". Regex on raw text can't tell
a real import apart from a comment/docstring that merely mentions one.
Parsing the actual AST and checking for genuine ast.Import/ast.ImportFrom
nodes eliminates that whole category of false positive.
"""
import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PIPELINE_DIRS = ["core", "services"]


def _imports_research(file_path: Path) -> bool:
    """True if this file has a genuine `import research` or
    `from research...` statement — determined from the real parsed
    AST, not text matching."""
    try:
        tree = ast.parse(file_path.read_text())
    except SyntaxError:
        return False  # not this test's job to catch unrelated syntax errors

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name == "research" or alias.name.startswith("research.")
                for alias in node.names
            ):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "research" or node.module.startswith("research.")):
                return True
    return False


def test_no_pipeline_code_imports_research():
    violations = []

    for dirname in PIPELINE_DIRS:
        pipeline_dir = REPO_ROOT / dirname
        if not pipeline_dir.exists():
            continue

        for py_file in pipeline_dir.rglob("*.py"):
            if _imports_research(py_file):
                violations.append(str(py_file.relative_to(REPO_ROOT)))

    assert not violations, (
        f"Found {len(violations)} file(s) in core/ or services/ importing "
        f"from research/, which must stay isolated from the live pipeline: "
        f"{violations}"
    )