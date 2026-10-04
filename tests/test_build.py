import hashlib
import json

import pytest

from macro.build import add_analysis, build_dist, write_manifest
from macro.errors import BuildError

SNAPSHOT = {"snapshot_id": "20261003T181500Z", "value": 1}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_writes_the_data_file_manifest_and_checksums(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT
    manifest = json.loads((dist / "manifest.json").read_text())
    assert manifest["snapshot_id"] == "20261003T181500Z"
    assert manifest["files"] == {
        "data.json": {
            "sha256": sha(dist / "data.json"),
            "bytes": (dist / "data.json").stat().st_size,
            "content_type": "application/json",
        }
    }
    assert (dist / "SHA256SUMS").read_text().splitlines() == [
        f"{sha(dist / 'data.json')}  data.json",
        f"{sha(dist / 'manifest.json')}  manifest.json",
    ]


def test_site_files_are_copied_and_listed_but_hidden_files_are_not(tmp_path):
    site = tmp_path / "site"
    (site / "vendor").mkdir(parents=True)
    (site / "index.html").write_text("<!doctype html>")
    (site / "vendor" / "lib.js").write_text("// lib")
    (site / ".DS_Store").write_text("finder")
    dist = tmp_path / "dist"
    build_dist(dist, site, SNAPSHOT)
    files = json.loads((dist / "manifest.json").read_text())["files"]
    assert sorted(files) == ["data.json", "index.html", "vendor/lib.js"]
    assert files["index.html"]["content_type"] == "text/html; charset=utf-8"
    assert files["vendor/lib.js"]["content_type"] == "text/javascript; charset=utf-8"
    assert not (dist / ".DS_Store").exists()


def test_a_rebuild_replaces_the_old_dist(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    (dist / "stale.txt").write_text("old")
    build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": 2})
    assert not (dist / "stale.txt").exists()
    assert json.loads((dist / "data.json").read_text())["value"] == 2


def test_a_failed_build_leaves_the_old_dist_alone(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    with pytest.raises(BuildError, match="JSON"):
        build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": float("nan")})
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT


def test_a_swap_that_fails_puts_the_old_dist_back(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    real_rename = type(dist).rename

    def failing_rename(self, target):
        if self.name == "dist.tmp":
            raise OSError("disk full")
        return real_rename(self, target)

    monkeypatch.setattr(type(dist), "rename", failing_rename)
    with pytest.raises(OSError, match="disk full"):
        build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": 2})
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT


def test_nothing_is_left_behind_after_a_build(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": 2})
    assert sorted(path.name for path in tmp_path.iterdir()) == ["dist"]


def test_a_file_with_an_unknown_type_stops_the_build(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "notes.docx").write_text("x")
    with pytest.raises(BuildError, match="notes.docx"):
        build_dist(tmp_path / "dist", site, SNAPSHOT)


def test_write_manifest_can_be_rerun_after_adding_a_file(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    (dist / "analysis.pdf").write_bytes(b"%PDF-1.4")
    write_manifest(dist, "20261003T181500Z")
    files = json.loads((dist / "manifest.json").read_text())["files"]
    assert sorted(files) == ["analysis.pdf", "data.json"]
    assert files["analysis.pdf"]["content_type"] == "application/pdf"


def test_an_old_dist_stranded_by_an_interrupted_run_is_put_back_first(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    dist.rename(tmp_path / "dist.old")  # as if a run had stopped between its two renames
    with pytest.raises(BuildError):
        build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": float("nan")})
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT


def test_the_page_and_its_own_scripts_get_the_build_id_in_their_addresses(tmp_path):
    site = tmp_path / "site"
    (site / "vendor").mkdir(parents=True)
    (site / "index.html").write_text('<script src="app.js?v={{BUILD_ID}}"></script>')
    (site / "app.js").write_text('import "./lib.js?v={{BUILD_ID}}";')
    (site / "lib.js").write_text("// nothing to fill in")
    (site / "style.css").write_text("/* {{BUILD_ID}} is left alone in a stylesheet */")
    (site / "vendor" / "other.js").write_text("// {{BUILD_ID}} is left alone in a file that is not ours")
    dist = tmp_path / "dist"
    build_dist(dist, site, {**SNAPSHOT, "build_id": "B7"})
    assert (dist / "index.html").read_text() == '<script src="app.js?v=B7"></script>'
    assert (dist / "app.js").read_text() == 'import "./lib.js?v=B7";'
    assert (dist / "lib.js").read_text() == "// nothing to fill in"
    assert "{{BUILD_ID}}" in (dist / "style.css").read_text()
    assert "{{BUILD_ID}}" in (dist / "vendor" / "other.js").read_text()
    files = json.loads((dist / "manifest.json").read_text())["files"]
    for name in ("index.html", "app.js"):
        assert files[name]["sha256"] == sha(dist / name)


def test_without_a_build_id_the_snapshot_id_is_used(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "app.js").write_text('import "./lib.js?v={{BUILD_ID}}";')
    dist = tmp_path / "dist"
    build_dist(dist, site, SNAPSHOT)
    assert (dist / "app.js").read_text() == 'import "./lib.js?v=20261003T181500Z";'


# --- the analysis PDF

PDF = b"%PDF-1.3 a first analysis"
WRITTEN = "2026-10-03T19:00:00Z"


def built(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<!doctype html>")
    dist = tmp_path / "dist"
    build_dist(dist, site, {**SNAPSHOT, "analysis": None})
    return dist


def test_an_analysis_is_added_recorded_and_listed(tmp_path):
    dist = built(tmp_path)
    name = add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)
    assert name == f"analysis-{hashlib.sha256(PDF).hexdigest()[:12]}.pdf"
    assert (dist / name).read_bytes() == PDF
    data = json.loads((dist / "data.json").read_text())
    assert data["analysis"] == {"file": name, "model": "Claude Opus 5.5", "generated_at": WRITTEN}
    assert data["snapshot_id"] == SNAPSHOT["snapshot_id"] and data["value"] == 1
    manifest = json.loads((dist / "manifest.json").read_text())
    assert manifest["snapshot_id"] == SNAPSHOT["snapshot_id"]
    assert sorted(manifest["files"]) == sorted([name, "data.json", "index.html"])
    assert manifest["files"][name] == {
        "sha256": hashlib.sha256(PDF).hexdigest(),
        "bytes": len(PDF),
        "content_type": "application/pdf",
    }
    assert manifest["files"]["data.json"]["sha256"] == sha(dist / "data.json")
    assert f"{sha(dist / 'manifest.json')}  manifest.json" in (dist / "SHA256SUMS").read_text()


def test_a_rewritten_analysis_replaces_the_first_under_a_new_name(tmp_path):
    dist = built(tmp_path)
    first = add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)
    second = add_analysis(dist, b"%PDF-1.3 a second analysis", "Claude Opus 5.5", "2026-10-03T20:00:00Z")
    assert first != second
    assert sorted(path.name for path in dist.glob("*.pdf")) == [second]
    data = json.loads((dist / "data.json").read_text())
    assert data["analysis"]["file"] == second and data["analysis"]["generated_at"] == "2026-10-03T20:00:00Z"
    assert first not in json.loads((dist / "manifest.json").read_text())["files"]


def test_the_same_analysis_keeps_its_name(tmp_path):
    dist = built(tmp_path)
    assert add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN) == add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)


def test_an_analysis_needs_a_built_dist(tmp_path):
    with pytest.raises(BuildError, match="Run refresh first"):
        add_analysis(tmp_path / "dist", PDF, "Claude Opus 5.5", WRITTEN)
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "data.json").write_text("not json")
    with pytest.raises(BuildError, match="Run refresh first"):
        add_analysis(tmp_path / "dist", PDF, "Claude Opus 5.5", WRITTEN)


def test_a_failure_while_adding_an_analysis_leaves_dist_alone(tmp_path, monkeypatch):
    dist = built(tmp_path)
    before = {path.name: path.read_bytes() for path in dist.iterdir()}

    def broken(folder, snapshot_id):
        raise OSError("disk full")

    monkeypatch.setattr("macro.build.write_manifest", broken)
    with pytest.raises(OSError, match="disk full"):
        add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == before


def test_a_hidden_file_left_in_dist_is_neither_listed_nor_a_reason_to_stop(tmp_path):
    dist = built(tmp_path)
    (dist / ".DS_Store").write_bytes(b"left by Finder")
    write_manifest(dist, SNAPSHOT["snapshot_id"])
    assert ".DS_Store" not in json.loads((dist / "manifest.json").read_text())["files"]
    name = add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)
    assert sorted(json.loads((dist / "manifest.json").read_text())["files"]) == sorted([name, "data.json", "index.html"])
    assert not (dist / ".DS_Store").exists()


def test_nothing_is_left_behind_after_adding_an_analysis(tmp_path):
    dist = built(tmp_path)
    add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["dist", "site"]
