"""The page's helpers are JavaScript, so their tests are too. This runs them as part of the suite."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_the_page_helpers_pass_their_own_tests():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is not installed, so the page helpers' tests did not run")
    result = subprocess.run(
        [node, "--test", "tests/js/lib.test.js"], cwd=ROOT, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]


def test_the_helpers_stand_alone():
    source = (ROOT / "site" / "lib.js").read_text(encoding="utf-8")
    assert not re.search(r"^import\b", source, flags=re.M)
    assert "document" not in source and "window" not in source
