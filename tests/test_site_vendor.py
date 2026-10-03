"""The chart library copied into site/vendor/ is exactly what its authors published."""
import hashlib
from pathlib import Path

import pytest

VENDOR = Path(__file__).resolve().parents[1] / "site" / "vendor"

# uPlot 1.6.32 (MIT licence), from https://registry.npmjs.org/uplot/-/uplot-1.6.32.tgz
# To change the version: download the new package, read what changed, and replace these checksums.
PUBLISHED = {
    "uPlot.iife.min.js": "19c8d4c6ad88929a79f4ae49d6f7161566dfd0ba3d15cc495e974f787eb78f1f",
    "uPlot.min.css": "df630c6a8d6f8eeaff264b50f73ce5b114f646ffd9a0bb74f049b0a00135fa04",
    "uPlot-LICENSE.txt": "8f989229699b4fe2f1a0432d0e9edc338a8a911e250e2d1b01ecd770a5f5b1bd",
}


@pytest.mark.parametrize("name", PUBLISHED)
def test_a_vendored_file_is_the_published_one(name):
    assert hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() == PUBLISHED[name]


def test_nothing_else_is_in_the_vendor_folder():
    assert sorted(path.name for path in VENDOR.iterdir() if not path.name.startswith(".")) == sorted(PUBLISHED)
