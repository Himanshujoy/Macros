"""Paths and fixed settings for the Mac-side commands."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
WORK_DIR = ROOT / "work"
CACHE_DIR = ROOT / ".cache"
SITE_DIR = ROOT / "site"
DATA_DIR = ROOT / "data"

USER_AGENT = "macros-page/1.0 (personal dashboard)"
HTTP_TIMEOUT = 30.0
