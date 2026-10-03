"""Static checks on the page's files: mistakes that would otherwise show only in a browser."""
import re
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1] / "site"
BUILD_ID = "v={{BUILD_ID}}"


def read(name):
    return (SITE / name).read_text(encoding="utf-8")


def test_every_element_the_script_looks_up_is_on_the_page():
    wanted = set(re.findall(r'\$\("([a-z0-9-]+)"\)', read("app.js")))
    present = re.findall(r'\bid="([a-z0-9-]+)"', read("index.html"))
    assert len(wanted) > 20
    assert wanted - set(present) == set()
    assert len(present) == len(set(present)), "an id is used twice"


def test_the_page_has_nothing_the_content_security_policy_would_block():
    page = read("index.html")
    assert not re.search(r"<style\b", page)
    assert not re.search(r"\sstyle\s*=", page)
    assert not re.search(r"\son[a-z]+\s*=", page)
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", page, flags=re.S)
    assert len(scripts) == 2
    for attributes, body in scripts:
        assert "src=" in attributes and body.strip() == ""
    for name in ("app.js", "charts.js"):
        assert "innerHTML" not in read(name) and "eval(" not in read(name)


def test_every_file_the_page_loads_is_local_and_carries_the_build_id():
    page = read("index.html")
    loaded = re.findall(r'<link\b[^>]*\bhref="([^"]+)"', page) + re.findall(r'<script\b[^>]*\bsrc="([^"]+)"', page)
    files = [address for address in loaded if not address.startswith("data:")]
    assert len(files) == 4
    for address in files:
        path, _, query = address.partition("?")
        assert query == BUILD_ID, address
        assert "//" not in path and (SITE / path).is_file(), address
    assert not re.search(r'(?:src|href)="(?:[a-z]+:)?//', page), "the page must load nothing from another site"


@pytest.mark.parametrize("name", ["app.js", "charts.js"])
def test_the_scripts_import_each_other_with_the_build_id(name):
    imports = re.findall(r'^import\b.*\bfrom "([^"]+)";$', read(name), flags=re.M)
    assert imports
    for address in imports:
        path, _, query = address.partition("?")
        assert query == BUILD_ID, address
        assert path.startswith("./") and (SITE / path).is_file(), address


def test_every_colour_role_is_defined_for_light_and_for_dark():
    css = read("style.css")
    light = css[css.index(":root {"):css.index("@media (prefers-color-scheme: dark)")]
    dark = css[css.index("@media (prefers-color-scheme: dark)"):css.index("* {")]
    defined = set(re.findall(r"^\s*(--[a-z0-9-]+):", light, flags=re.M))
    used = set(re.findall(r"var\((--[a-z0-9-]+)\)", css)) | set(re.findall(r'value\("(--[a-z0-9-]+)"\)', read("charts.js")))
    assert used - defined == set()
    colours = {name for name in defined if name != "--thumb"}
    assert set(re.findall(r"^\s*(--[a-z0-9-]+):", dark, flags=re.M)) == colours
