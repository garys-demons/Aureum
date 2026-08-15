"""
tests/unit/test_research_boundary.py

Enforces the explicit Phase 3 rule: "keep research/ code cleanly
separated from core/ and services/ — nothing here gets imported into
the live pipeline directly."

This isn't a technical restriction Python enforces on its own — a
teammate could accidentally `import research.storage` from inside
services/ and nothing would stop them at write-time. This test catches
it in CI instead: it scans every .py file under core/ and services/
for any import mentioning "research", and fails loudly with the exact
file if it finds one.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PIPELINE_DIRS = ["core", "services"]

IMPORT_PATTERN = re.compile(r"^\s*(?:from|import)\s+research\b", re.MULTILINE)


def test_no_pipeline_code_imports_research():
    violations = []

    for dirname in PIPELINE_DIRS:
        pipeline_dir = REPO_ROOT / dirname
        if not pipeline_dir.exists():
            continue

        for py_file in pipeline_dir.rglob("*.py"):
            content = py_file.read_text()
            if IMPORT_PATTERN.search(content):
                violations.append(str(py_file.relative_to(REPO_ROOT)))

    assert not violations, (
        f"Found {len(violations)} file(s) in core/ or services/ importing "
        f"from research/, which must stay isolated from the live pipeline: "
        f"{violations}"
    )