# Macros Page, Plan 2b: The Page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python -m macro preview` shows the finished page: the two linked yield charts with their sliders and two curve modes, the rate odds with the countdown, and the Fed funds rate with its target range. The "Explain Macros" button is in place and stays disabled until Plan 3 supplies the PDF.

**Architecture:** The page is plain files in `site/`: one HTML file, one stylesheet and three JavaScript modules. `lib.js` holds the arithmetic (dates, ranges, positions, labels), touches nothing on the page, and is tested under Node. `charts.js` draws: the two history charts on canvas with uPlot, the curve and the odds as SVG. `app.js` keeps the visitor's four choices (range, date, tenor, curve mode) and redraws what each one affects. The page loads `data.json` once and asks no other site for anything.

**Tech Stack:** Browser JavaScript as ES modules, with no build step and no npm packages. uPlot 1.6.32 (MIT licence), copied into `site/vendor/`. Python 3.14 on the Mac, with all code kept compatible with Python 3.12; pytest 9.1.1. Node 20 or newer runs the helpers' tests (this Mac has 25.8.2). Without Node that one test is skipped.

**Spec:** `docs/superpowers/specs/2026-10-04-macros-page-design.md`, sections 5 (the page), 8.2 (the cache rule) and 13 (testing). The spec was updated alongside this plan.

**Supersedes:** for every file listed below, the content in Plan 2a.

---

## Roadmap

| Plan | Delivers | Status |
|---|---|---|
| 1 and 1b. Data pipeline | `python -m macro refresh` | Done |
| 2a. Server and preview | `python -m macro preview`, serving a placeholder page | Done |
| 2b. The page (this file) | The charts, sliders, odds and countdown | This plan |
| 3. Analysis PDF | `python -m macro analysis`, and a working "Explain Macros" button | Next |
| 4. Publish and rollout | `publish`, `rollback`, the box install, tunnel and DNS | Later, each step gated on the owner's go |

## Rules for whoever executes this plan

- **Never run `git add`, `commit`, `push`, `stash`, `reset`, `checkout` or `restore`.** The owner makes every commit. Each task ends with a checkpoint. Stop there and report.
- **Tests never touch a real service.** Do not run `python -m macro refresh` or `python -m macro preview` unless a step says so.
- **Task 2 downloads one file:** a pinned version of uPlot from the npm registry, checked against a checksum. No other task before Task 5 uses the network.
- **Nothing in this plan touches the box or Cloudflare.** Do not run `ssh`.
- Run every command from the project root, `/Users/himanshusrivastava/Projects/Macros`, with `.venv/bin/python`.
- Each file below is shown in full. It **replaces** an existing file of the same path, or creates it. Copy it exactly.
- Keep the Python code compatible with Python 3.12. `server/serve.py` must import nothing outside the standard library.
- The page must have no inline script or style, must not use `innerHTML`, and must load nothing from another site. The server's content security policy blocks all three, and Task 4's tests check for them.

## File structure

| File | Responsibility |
|---|---|
| `macro/build.py` | Now also writes the build id into the page's own scripts |
| `server/serve.py` | Now logs nothing for a connection that was only closed for being silent |
| `site/vendor/uPlot.iife.min.js`, `site/vendor/uPlot.min.css`, `site/vendor/uPlot-LICENSE.txt` | The chart library and its licence, exactly as published |
| `site/lib.js` | Pure helpers: dates, ranges, tenor positions, labels, the countdown. No page access |
| `site/charts.js` | Drawing: the time chart with its marker and tooltip, the curve, the odds columns |
| `site/app.js` | The visitor's choices, the events that change them, and what each one redraws |
| `site/index.html` | The page's structure and fixed text |
| `site/style.css` | Layout, and the colour roles for light and dark |
| `tests/js/lib.test.js` | The helpers' tests, run by Node |
| `tests/test_site_vendor.py` | The vendored files match their published checksums |
| `tests/test_site_helpers.py` | Runs the helpers' tests as part of the Python suite |
| `tests/test_site_page.py` | Static checks on the page files |
| `tests/test_build.py`, `tests/test_serve.py` | Updated for the two small changes in Task 1 |

## How the page works

The page keeps four choices and redraws what each one affects.

| Choice | Set by | Redraws |
|---|---|---|
| Range | The preset buttons, or the two date inputs | The time axis of both history charts, and the span of the date slider |
| Date | The date slider | The marker on both history charts, the curve, and the readouts |
| Tenor | The tenor slider, or a click on a curve point | The history line and its title, and the highlighted curve point |
| Curve mode | The two mode buttons | Where the tenors sit along the curve's axis, and whether the tenor slider is locked |

Three details are easy to get wrong, so each is handled in one place:

- **Sliders line up with their charts.** A slider's thumb is 16px wide, so its centre stops 8px short of each end of the slider. `placeSlider` in `app.js` therefore makes the slider 8px longer at each end than the stretch it follows. The date slider follows the plot area of the history chart. uPlot only knows that area after its first layout, so `timeChart` reports it through an `onLayout` callback. The tenor slider follows the first and last tenor positions, which `drawCurve` returns.
- **Colours are defined once.** `style.css` defines each colour role for light and for dark. The SVG charts use the roles through CSS classes. A canvas cannot, so `charts.js` reads the roles from the page each time it builds a time chart, and `app.js` rebuilds those charts when the system switches between light and dark.
- **Addresses change with every build.** Every file the page asks for carries `?v=<build id>`, including the modules' imports of each other. The source files say `{{BUILD_ID}}` and the build fills it in (Task 1).

---

### Task 1: The build stamps the page's scripts, and the server's log stays quiet

**Files:**
- Replace: `tests/test_build.py`, `tests/test_serve.py`
- Replace: `macro/build.py`, `server/serve.py`

Two small changes. The page needs the first. Testing the page in a browser turned up the second.

| Change | Why |
|---|---|
| The build fills in `{{BUILD_ID}}` in `index.html` and in every `.js` file in the top folder of `site/`. Stylesheets and everything under `vendor/` are left alone | The page's scripts import each other. Without a version on those addresses, a visitor could get the new `app.js` together with a `lib.js` cached from the build before |
| The server logs nothing when it closes a silent connection | Browsers open spare connections and leave them idle. Each one was logged as `note Request?timed?out...`. That line says nothing useful, and it is not the method, path and status that the spec promises |

- [ ] **Step 1: Replace the two test files**

**File: `tests/test_build.py`**

```python
import hashlib
import json

import pytest

from macro.build import build_dist, write_manifest
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
```

**File: `tests/test_serve.py`**

```python
import http.client
import json
import os
import socket
import threading
import time

import pytest

from macro.build import write_manifest
from server import serve

FILES = {
    "index.html": "<!doctype html><title>t</title>",
    "app.js": "console.log(1)",
    "vendor/lib.js": "// lib",
    "data.json": '{"snapshot_id": "A"}',
    "analysis.pdf": "%PDF-1.4",
    "robots.txt": "User-agent: *\nDisallow: /\n",
}


def make_release(folder, snapshot_id="A", files=FILES):
    for name, text in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    write_manifest(folder, snapshot_id)
    return folder


class Running:
    """A server on a free localhost port, with its log lines collected."""

    def __init__(self, site, **options):
        self.lines = []
        self.server = serve.Server(site, 0, log=self.lines.append, **options)
        self.port = self.server.server_port
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()

    def request(self, method, path, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
        finally:
            connection.close()

    def get(self, path, headers=None):
        return self.request("GET", path, headers)

    def raw(self, data, wait=2.0):
        with socket.create_connection(("127.0.0.1", self.port), timeout=wait) as sock:
            if data:
                sock.sendall(data)
            chunks = []
            try:
                while chunk := sock.recv(4096):
                    chunks.append(chunk)
            except TimeoutError:
                chunks.append(b"<<still open>>")
            return b"".join(chunks)

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def release(tmp_path):
    return make_release(tmp_path / "releases" / "A")


@pytest.fixture
def running(release):
    server = Running(serve.DiskSite(release))
    yield server
    server.close()


# --- which files a release may serve


@pytest.mark.parametrize("name", ["index.html", "vendor/lib.js", "a-b_c.1.json"])
def test_plain_relative_paths_are_safe(name):
    assert serve.safe_name(name)


@pytest.mark.parametrize(
    "name",
    ["", "/etc/passwd", "../x", "a/../x", "a//b", "a/", "./a", "a\\b", "a%2e", "a?b", "a#b", "a\nb", "manifest.json", "SHA256SUMS", 7, None],
)
def test_anything_else_is_not(name):
    assert not serve.safe_name(name)


def test_load_release_lists_the_manifest_files(release):
    loaded = serve.load_release(release)
    assert loaded.snapshot_id == "A"
    assert sorted(loaded.files) == sorted(FILES)
    assert loaded.files["index.html"].content_type == "text/html; charset=utf-8"
    assert loaded.files["index.html"].etag.startswith('"') and len(loaded.files["index.html"].etag) == 18


def rewrite_manifest(release, change):
    path = release / "manifest.json"
    manifest = json.loads(path.read_text())
    change(manifest)
    path.write_text(json.dumps(manifest))


def test_a_folder_without_a_manifest_is_not_a_release(tmp_path):
    assert serve.load_release(tmp_path) is None


def test_a_manifest_that_is_not_json_is_not_a_release(release):
    (release / "manifest.json").write_text("not json")
    assert serve.load_release(release) is None


def test_a_manifest_naming_a_path_outside_the_folder_is_rejected(release):
    rewrite_manifest(release, lambda m: m["files"].update({"../secret.txt": m["files"]["robots.txt"]}))
    assert serve.load_release(release) is None


def test_a_manifest_naming_a_missing_file_is_rejected(release):
    (release / "app.js").unlink()
    assert serve.load_release(release) is None


def test_a_link_that_leaves_the_folder_is_rejected(release, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    (release / "robots.txt").unlink()
    (release / "robots.txt").symlink_to(secret)
    assert serve.load_release(release) is None


def test_a_content_type_that_could_split_a_header_is_rejected(release):
    rewrite_manifest(release, lambda m: m["files"]["app.js"].update(content_type="text/plain\r\nX-Evil: 1"))
    assert serve.load_release(release) is None


# --- what the server answers


def test_the_root_serves_the_page_with_its_headers(running):
    status, headers, body = running.get("/")
    assert status == 200
    assert body == FILES["index.html"].encode()
    assert headers["content-type"] == "text/html; charset=utf-8"
    assert headers["content-security-policy"] == serve.CSP
    assert headers["cache-control"] == "public, max-age=60"
    assert headers["x-robots-tag"] == "noindex, nofollow"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["content-length"] == str(len(body))


def test_other_files_get_their_type_and_no_page_policy(running):
    status, headers, body = running.get("/vendor/lib.js")
    assert (status, body) == (200, b"// lib")
    assert headers["content-type"] == "text/javascript; charset=utf-8"
    assert "content-security-policy" not in headers
    assert running.get("/data.json")[1]["content-type"] == "application/json"
    assert running.get("/robots.txt")[2] == FILES["robots.txt"].encode()


def test_the_pdf_opens_inline(running):
    headers = running.get("/analysis.pdf")[1]
    assert headers["content-type"] == "application/pdf"
    assert headers["content-disposition"] == 'inline; filename="macro-analysis.pdf"'


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/app.js?v=20261004T101500Z", "public, max-age=31536000, immutable"),
        ("/app.js?x=1&v=2", "public, max-age=31536000, immutable"),
        ("/app.js", "public, max-age=60"),
        ("/app.js?v=", "public, max-age=60"),
        ("/app.js?version=2", "public, max-age=60"),
    ],
)
def test_only_a_versioned_address_is_cached_for_long(running, path, expected):
    assert running.get(path)[1]["cache-control"] == expected


def test_an_unchanged_file_answers_304(running):
    etag = running.get("/app.js")[1]["etag"]
    for header in (etag, "W/" + etag, f'"other", {etag}', "*"):
        status, headers, body = running.get("/app.js", {"If-None-Match": header})
        assert (status, body) == (304, b"")
        assert headers["etag"] == etag
    assert running.get("/app.js", {"If-None-Match": '"something-else"'})[0] == 200


def test_head_sends_headers_only(running):
    status, headers, body = running.request("HEAD", "/")
    assert (status, body) == (200, b"")
    assert headers["content-length"] == str(len(FILES["index.html"]))


@pytest.mark.parametrize(
    "path",
    ["/nope", "/manifest.json", "/SHA256SUMS", "/../data.json", "/vendor/../data.json", "/%2e%2e/data.json", "/vendor", "/vendor/", "/index.html/"],
)
def test_anything_not_in_the_manifest_is_a_plain_404(running, path):
    status, headers, body = running.get(path)
    assert (status, body) == (404, b"Not Found\n")
    assert headers["content-type"] == "text/plain; charset=utf-8"
    assert headers["cache-control"] == "no-store"
    assert headers["x-robots-tag"] == "noindex, nofollow"


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def test_other_methods_are_refused(running, method):
    status, headers, body = running.request(method, "/")
    assert (status, body) == (405, b"Method Not Allowed\n")
    assert headers["allow"] == "GET, HEAD"
    assert headers["connection"] == "close"


def test_the_health_check_answers_even_without_a_release(tmp_path):
    server = Running(serve.DiskSite(tmp_path / "missing"))
    try:
        assert server.get("/healthz")[:1] == (200,)
        assert server.get("/healthz")[2] == b"ok\n"
        status, _, body = server.get("/")
        assert (status, body) == (503, b"Service Unavailable\n")
    finally:
        server.close()


def test_no_version_string_is_sent(running):
    for path in ("/", "/nope", "/healthz"):
        headers = running.get(path)[1]
        assert "server" not in headers
        assert "python" not in json.dumps(headers).lower()


def test_two_requests_can_share_one_connection(running):
    connection = http.client.HTTPConnection("127.0.0.1", running.port, timeout=5)
    try:
        for path in ("/", "/app.js"):
            connection.request("GET", path)
            response = connection.getresponse()
            assert response.status == 200
            response.read()
    finally:
        connection.close()


# --- releases changing underneath it


def test_switching_the_link_serves_the_new_release_without_a_restart(tmp_path):
    make_release(tmp_path / "releases" / "A")
    make_release(tmp_path / "releases" / "B", "B", {**FILES, "data.json": '{"snapshot_id": "B"}'})
    current = tmp_path / "current"
    current.symlink_to("releases/A")
    server = Running(serve.DiskSite(current))
    try:
        assert json.loads(server.get("/data.json")[2])["snapshot_id"] == "A"
        replacement = tmp_path / "current.new"
        replacement.symlink_to("releases/B")
        os.replace(replacement, current)
        assert json.loads(server.get("/data.json")[2])["snapshot_id"] == "B"
    finally:
        server.close()


def test_a_folder_rebuilt_in_place_is_read_again(release, running):
    before = running.get("/data.json")[1]["etag"]
    (release / "data.json").write_text('{"snapshot_id": "A2", "more": true}')
    write_manifest(release, "A2")
    status, headers, body = running.get("/data.json")
    assert json.loads(body)["snapshot_id"] == "A2"
    assert headers["etag"] != before


def test_a_file_that_vanishes_gives_a_plain_500_and_no_traceback(release, running):
    assert running.get("/app.js")[0] == 200
    (release / "app.js").unlink()
    status, headers, body = running.get("/app.js")
    assert (status, body) == (500, b"Internal Server Error\n")
    assert "error FileNotFoundError" in running.lines


# --- logs and connections


def test_the_log_has_method_path_and_status_and_nothing_about_the_visitor(running):
    running.get("/app.js?v=1", {"User-Agent": "secret-agent", "CF-Connecting-IP": "203.0.113.9"})
    running.get("/nope")
    assert running.lines == ["GET /app.js 200", "GET /nope 404"]


def test_a_request_that_is_not_http_gets_a_plain_refusal(running):
    reply = running.raw(b"NOT HTTP\r\n\r\n")
    assert b"Bad Request" in reply
    assert b"Traceback" not in reply and b"Python" not in reply


def test_a_silent_connection_is_closed_and_leaves_nothing_in_the_log(release):
    server = Running(serve.DiskSite(release), idle_timeout=0.3)
    try:
        started = time.monotonic()
        assert server.raw(b"", wait=3.0) == b""
        assert time.monotonic() - started < 2.5
        time.sleep(0.1)  # the handler thread finishes just after the socket closes
        assert server.lines == []
    finally:
        server.close()


# --- the self-test and the command line


def test_the_self_test_passes_and_reports_each_check():
    lines = []
    assert serve.self_test(log=lines.append) is True
    assert lines[-1] == "self-test passed"
    assert all(line.startswith("ok ") for line in lines[:-1])
    assert len(lines) > 15


def test_main_runs_the_self_test(capsys):
    assert serve.main(["--self-test"]) == 0
    assert "self-test passed" in capsys.readouterr().out


def test_main_needs_a_site(monkeypatch, capsys):
    monkeypatch.delenv("MACRO_SITE_DIR", raising=False)
    assert serve.main([]) == 2
    assert "MACRO_SITE_DIR" in capsys.readouterr().err


def test_main_rejects_a_port_that_is_not_a_number(tmp_path, capsys):
    assert serve.main(["--site", str(tmp_path), "--port", "eighty"]) == 2
    assert "port" in capsys.readouterr().err


def test_main_reports_a_port_it_cannot_use(release, running, capsys):
    assert serve.main(["--site", str(release), "--port", str(running.port)]) == 2
    assert "cannot listen" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_build.py tests/test_serve.py`

Expected: `3 failed, 72 passed`. The failures are the two build-id tests and the silent-connection test.

- [ ] **Step 3: Replace the two modules**

**File: `macro/build.py`**

```python
"""Writes dist/: the page files, data.json, and a manifest and checksum list of everything in it."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from macro.errors import BuildError

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
}
INTERNAL = ("manifest.json", "SHA256SUMS")
BUILD_ID_MARK = "{{BUILD_ID}}"  # replaced with the build id, so asset addresses change with every build
STAMPED = ("index.html", "*.js")  # where the mark is filled in: the site's top folder only, never vendor/


def write_manifest(dist: Path, snapshot_id: str) -> None:
    """Lists every file the server may serve. Rerun it after adding a file to dist/."""
    files: dict[str, dict] = {}
    for path in sorted(item for item in dist.rglob("*") if item.is_file()):
        name = path.relative_to(dist).as_posix()
        if name in INTERNAL:
            continue
        content_type = CONTENT_TYPES.get(path.suffix.lower())
        if content_type is None:
            raise BuildError(f"build: no content type for {name}")
        data = path.read_bytes()
        files[name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "content_type": content_type,
        }
    manifest = dist / "manifest.json"
    manifest.write_text(json.dumps({"snapshot_id": snapshot_id, "files": files}, indent=2) + "\n", encoding="utf-8")
    lines = [f"{meta['sha256']}  {name}\n" for name, meta in files.items()]
    lines.append(f"{hashlib.sha256(manifest.read_bytes()).hexdigest()}  manifest.json\n")
    (dist / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


def build_dist(dist: Path, site: Path, snapshot: dict) -> None:
    """Builds in a temporary folder and swaps it in, so a failure leaves the old dist/ in place."""
    staging = dist.with_name(dist.name + ".tmp")
    previous = dist.with_name(dist.name + ".old")
    if previous.exists() and not dist.exists():
        previous.rename(dist)  # an earlier run stopped between the two renames: put the old folder back
    for leftover in (staging, previous):
        if leftover.exists():
            shutil.rmtree(leftover)
    if site.is_dir():
        shutil.copytree(site, staging, ignore=shutil.ignore_patterns(".*"))
    else:
        staging.mkdir(parents=True)
    try:
        data = json.dumps(snapshot, separators=(",", ":"), allow_nan=False)
    except ValueError as exc:
        raise BuildError(f"build: the data cannot be written as JSON: {exc}") from None
    (staging / "data.json").write_text(data, encoding="utf-8")
    build_id = str(snapshot.get("build_id", snapshot["snapshot_id"]))
    for pattern in STAMPED:
        for path in staging.glob(pattern):
            text = path.read_text(encoding="utf-8")
            if BUILD_ID_MARK in text:
                path.write_text(text.replace(BUILD_ID_MARK, build_id), encoding="utf-8")
    write_manifest(staging, snapshot["snapshot_id"])

    # Two renames, so dist/ is never missing for longer than the gap between them.
    if dist.exists():
        dist.rename(previous)
    try:
        staging.rename(dist)
    except OSError:
        if previous.exists():
            previous.rename(dist)
        raise
    shutil.rmtree(previous, ignore_errors=True)
```

**File: `server/serve.py`**

```python
#!/usr/bin/env python3
"""Static file server for the macros page.

Standard library only, so it runs on the box's system Python with nothing installed.
It serves the files listed in the current release's manifest and nothing else.
See section 8.2 of the design spec.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import socketserver
import sys
import threading
from dataclasses import dataclass
from email.utils import formatdate
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

HOST = "127.0.0.1"  # never listens on anything but loopback
DEFAULT_PORT = 8081
IDLE_TIMEOUT = 15.0  # seconds of silence before a connection is closed
INTERNAL = ("manifest.json", "SHA256SUMS")  # part of a release, never served
SHORT_CACHE = "public, max-age=60"
LONG_CACHE = "public, max-age=31536000, immutable"
NO_CACHE = "no-store"
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
ALWAYS = {
    "X-Robots-Tag": "noindex, nofollow",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


@dataclass(frozen=True)
class Entry:
    """One file that may be served. Its bytes are on disk, or in memory for the self-test."""

    content_type: str
    etag: str
    path: Path | None = None
    data: bytes | None = None


@dataclass(frozen=True)
class Release:
    snapshot_id: str
    files: dict[str, Entry]


def read_entry(entry: Entry) -> bytes:
    return entry.data if entry.data is not None else entry.path.read_bytes()


def safe_name(name: object) -> bool:
    """True for a plain relative path such as "vendor/uplot.js": no "..", no escapes, not internal."""
    if not isinstance(name, str) or not name or name in INTERNAL:
        return False
    if name.startswith("/") or any(char in name for char in "\\%?#") or any(ord(char) < 32 for char in name):
        return False
    parts = PurePosixPath(name).parts
    return ".." not in parts and name == "/".join(parts)


def load_release(folder: Path) -> Release | None:
    """Reads a release folder's manifest. None when the folder is not a usable release."""
    try:
        root = folder.resolve()
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        files: dict[str, Entry] = {}
        for name, meta in manifest["files"].items():
            content_type = meta["content_type"]
            path = (root / name).resolve() if safe_name(name) else None
            if path is None or not path.is_relative_to(root) or not path.is_file():
                return None
            if not isinstance(content_type, str) or any(ord(char) < 32 for char in content_type):
                return None
            files[name] = Entry(content_type, '"' + str(meta["sha256"])[:16] + '"', path=path)
        return Release(str(manifest["snapshot_id"]), files)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


class DiskSite:
    """The release that `location` points at. It is read again whenever it changes."""

    def __init__(self, location: Path) -> None:
        self._location = location
        self._lock = threading.Lock()
        self._key: tuple | None = None
        self._release: Release | None = None

    def current(self) -> Release | None:
        folder = Path(os.path.realpath(self._location))
        try:
            stat = (folder / "manifest.json").stat()
            key = (str(folder), stat.st_mtime_ns, stat.st_size)
        except OSError:
            key = None
        with self._lock:
            if key != self._key:
                self._release = load_release(folder) if key else None
                self._key = key
            return self._release


class MemorySite:
    """A fixed release held in memory. Used by the self-test, which must write nothing."""

    def __init__(self, files: dict[str, tuple[str, bytes]]) -> None:
        entries = {
            name: Entry(content_type, f'"{len(data):016x}"', data=data)
            for name, (content_type, data) in files.items()
        }
        self._release = Release("self-test", entries)

    def current(self) -> Release | None:
        return self._release


def say(line: str) -> None:
    """The default log: one line to standard output, flushed so the journal sees it at once."""
    print(line, flush=True)


def plain(status: HTTPStatus, text: str | None = None) -> tuple[HTTPStatus, dict[str, str], bytes]:
    body = ((text or status.phrase) + "\n").encode()
    return status, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": NO_CACHE}, body


def etag_matches(header: str | None, etag: str) -> bool:
    """If-None-Match against our tag. A cache may have turned the tag into a weak one."""
    if not header:
        return False
    candidates = [item.strip().removeprefix("W/") for item in header.split(",")]
    return "*" in candidates or etag in candidates


def printable(text: str, limit: int = 120) -> str:
    return "".join(char if 32 < ord(char) < 127 else "?" for char in text)[:limit]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        self.timeout = self.server.idle_timeout
        super().setup()

    def do_GET(self) -> None:
        self._answer()

    def do_HEAD(self) -> None:
        self._answer()

    def _answer(self) -> None:
        try:
            status, headers, body = self._resolve()
        except Exception as exc:  # a bug or a vanished file must never become a traceback
            self.server.log(f"error {type(exc).__name__}")
            status, headers, body = plain(HTTPStatus.INTERNAL_SERVER_ERROR)
        self._send(status, headers, body)

    def _resolve(self) -> tuple[HTTPStatus, dict[str, str], bytes]:
        path, _, query = self.path.partition("?")
        if path == "/healthz":
            return plain(HTTPStatus.OK, "ok")
        release = self.server.site.current()
        if release is None:
            return plain(HTTPStatus.SERVICE_UNAVAILABLE)
        entry = release.files.get("index.html" if path == "/" else path[1:]) if path.startswith("/") else None
        if entry is None:
            return plain(HTTPStatus.NOT_FOUND)
        versioned = any(part.startswith("v=") and len(part) > 2 for part in query.split("&"))
        headers = {
            "Content-Type": entry.content_type,
            "ETag": entry.etag,
            "Cache-Control": LONG_CACHE if versioned else SHORT_CACHE,
        }
        if entry.content_type.startswith("text/html"):
            headers["Content-Security-Policy"] = CSP
        if entry.content_type == "application/pdf":
            headers["Content-Disposition"] = 'inline; filename="macro-analysis.pdf"'
        if etag_matches(self.headers.get("If-None-Match"), entry.etag):
            return HTTPStatus.NOT_MODIFIED, headers, b""
        return HTTPStatus.OK, headers, read_entry(entry)

    def _send(self, status: HTTPStatus, headers: dict[str, str], body: bytes) -> None:
        self.send_response_only(status)
        self.send_header("Date", formatdate(usegmt=True))
        for name, value in {**headers, **ALWAYS}.items():
            self.send_header(name, value)
        if status != HTTPStatus.NOT_MODIFIED:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)
        path = printable(getattr(self, "path", "") or "").partition("?")[0]
        self.server.log(f"{printable(self.command or '-', 12)} {path or '-'} {int(status)}")

    def send_error(self, code, message=None, explain=None) -> None:
        """Every error the base class raises: a plain body, no version string, connection closed."""
        try:
            status = HTTPStatus(code)
        except ValueError:
            status = HTTPStatus.BAD_REQUEST
        if status == HTTPStatus.NOT_IMPLEMENTED:  # a method other than GET or HEAD
            status = HTTPStatus.METHOD_NOT_ALLOWED
        status, headers, body = plain(status)
        if status == HTTPStatus.METHOD_NOT_ALLOWED:
            headers["Allow"] = "GET, HEAD"
        headers["Connection"] = "close"
        self.close_connection = True
        self._send(status, headers, body)

    def log_message(self, format, *args) -> None:
        """Nothing: the base class uses this only to say an idle connection timed out, which is routine."""


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, site, port: int, log=say, idle_timeout: float = IDLE_TIMEOUT) -> None:
        self.site = site
        self.log = log
        self.idle_timeout = idle_timeout
        super().__init__((HOST, port), Handler)

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)  # skip the hostname lookup HTTPServer would do
        self.server_name = "localhost"
        self.server_port = self.server_address[1]

    def handle_error(self, request, client_address) -> None:
        self.log(f"error {type(sys.exception()).__name__}")


def run(location: Path, port: int, log=say) -> int:
    """Serves until interrupted."""
    server = Server(DiskSite(location), port, log)
    log(f"serving {location} on http://{HOST}:{server.server_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


SAMPLE = {
    "index.html": ("text/html; charset=utf-8", b"<!doctype html><title>self-test</title>"),
    "app.js": ("text/javascript; charset=utf-8", b"// self-test"),
    "data.json": ("application/json", b'{"snapshot_id":"self-test"}'),
    "analysis.pdf": ("application/pdf", b"%PDF-1.4 self-test"),
}


def self_test(log=say) -> bool:
    """Starts the server on a free port against a sample held in memory and checks its rules."""
    server = Server(MemorySite(SAMPLE), 0, log=lambda line: None)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    failures: list[str] = []

    def fetch(method: str, path: str, headers: dict[str, str] | None = None):
        connection = http.client.HTTPConnection(HOST, server.server_port, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
        finally:
            connection.close()

    def check(name: str, passed: bool) -> None:
        log(("ok    " if passed else "FAIL  ") + name)
        if not passed:
            failures.append(name)

    try:
        status, headers, body = fetch("GET", "/")
        check("the page is served", status == 200 and body == SAMPLE["index.html"][1])
        check("the page carries the content security policy", headers.get("content-security-policy") == CSP)
        check("the page is cached for a minute", headers.get("cache-control") == SHORT_CACHE)
        check("search engines are told not to index", headers.get("x-robots-tag") == "noindex, nofollow")
        check("content sniffing is off", headers.get("x-content-type-options") == "nosniff")
        check("no server version is sent", "server" not in headers)
        etag = headers.get("etag", "")
        check("an unchanged file answers 304", fetch("GET", "/", {"If-None-Match": etag})[0] == 304)
        status, headers, body = fetch("HEAD", "/")
        check("HEAD sends headers only", status == 200 and body == b"" and headers.get("content-length") == "39")
        status, headers, _ = fetch("GET", "/app.js?v=1")
        check("a versioned file is cached for a year", status == 200 and headers.get("cache-control") == LONG_CACHE)
        check("scripts carry no page policy", "content-security-policy" not in headers)
        status, headers, _ = fetch("GET", "/analysis.pdf")
        check("the PDF opens inline", status == 200 and headers.get("content-disposition", "").startswith("inline"))
        check("the data file is served", fetch("GET", "/data.json")[0] == 200)
        check("an unknown path is 404", fetch("GET", "/nope")[0] == 404)
        check("the manifest is not served", fetch("GET", "/manifest.json")[0] == 404)
        check("a path that climbs out is 404", fetch("GET", "/../etc/passwd")[0] == 404)
        status, headers, _ = fetch("POST", "/")
        check("other methods are refused", status == 405 and headers.get("allow") == "GET, HEAD")
        status, _, body = fetch("GET", "/healthz")
        check("the health check answers", status == 200 and body == b"ok\n")
    except Exception as exc:
        check(f"the self-test ran without {type(exc).__name__}", False)
    finally:
        server.shutdown()
        server.server_close()
    log("self-test passed" if not failures else f"self-test FAILED: {len(failures)} check(s)")
    return not failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Static file server for the macros page.")
    parser.add_argument("--self-test", action="store_true", help="check the server's rules and exit")
    parser.add_argument("--site", default=os.environ.get("MACRO_SITE_DIR"), help="the release folder or a link to it")
    parser.add_argument("--port", default=os.environ.get("MACRO_PORT", str(DEFAULT_PORT)), help="port on 127.0.0.1")
    args = parser.parse_args(argv)
    if args.self_test:
        return 0 if self_test() else 1
    if not args.site:
        print("serve: set MACRO_SITE_DIR or pass --site", file=sys.stderr)
        return 2
    if not str(args.port).isdigit():
        print(f"serve: the port must be a number, not {args.port!r}", file=sys.stderr)
        return 2
    try:
        return run(Path(args.site), int(args.port))
    except OSError as exc:
        print(f"serve: cannot listen on {HOST}:{args.port}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_build.py tests/test_serve.py`

Expected: `75 passed`

- [ ] **Step 5: Run the self-test and the whole suite**

Run:

```bash
.venv/bin/python server/serve.py --self-test
.venv/bin/python -m pytest
```

Expected: seventeen lines starting `ok`, then `self-test passed`; and `230 passed`.

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: the four above. Suggested message: `feat: build id in the page's scripts; no log line for an idle connection`.

---

### Task 2: Copy uPlot into the project

**Files:**
- Create: `tests/test_site_vendor.py`
- Create: `site/vendor/uPlot.iife.min.js`, `site/vendor/uPlot.min.css`, `site/vendor/uPlot-LICENSE.txt`

uPlot draws the two history charts. It is one script of about 50 KB and a small stylesheet, under the MIT licence. The page may load nothing from another site, so the files are copied into the project, and the licence file travels with them.

The files are too long to print here. This task downloads the published package and checks it against checksums recorded when the page was written and tested. The test added here keeps checking the three files from then on, so a changed or swapped file fails the suite.

- [ ] **Step 1: Write the failing test**

**File: `tests/test_site_vendor.py`**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_site_vendor.py`

Expected: `4 failed`, each with `FileNotFoundError`, because `site/vendor/` does not exist yet.

- [ ] **Step 3: Download the package, check it, and copy the three files**

Run:

```bash
mkdir -p .cache/vendor
curl -fsSL -o .cache/vendor/uplot-1.6.32.tgz https://registry.npmjs.org/uplot/-/uplot-1.6.32.tgz
echo "4b8a8191e425658e3ea8c8c1314b0fc679c861ee3a1af2b20c7b16ba50b5133d  .cache/vendor/uplot-1.6.32.tgz" | shasum -a 256 -c -
```

Expected: `.cache/vendor/uplot-1.6.32.tgz: OK`

If the line does not end in `OK`, stop. Copy nothing and report what was printed.

Then run:

```bash
tar -xzf .cache/vendor/uplot-1.6.32.tgz -C .cache/vendor
mkdir -p site/vendor
cp .cache/vendor/package/dist/uPlot.iife.min.js site/vendor/uPlot.iife.min.js
cp .cache/vendor/package/dist/uPlot.min.css site/vendor/uPlot.min.css
cp .cache/vendor/package/LICENSE site/vendor/uPlot-LICENSE.txt
ls site/vendor
```

Expected: `uPlot-LICENSE.txt`, `uPlot.iife.min.js` and `uPlot.min.css`.

The download stays in `.cache/vendor/`, which git ignores. Delete nothing.

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_site_vendor.py`

Expected: `4 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `234 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: the test and the three files in `site/vendor/`. Suggested message: `chore: vendor uPlot 1.6.32 with a checksum test`.

---

### Task 3: The page's helpers

**Files:**
- Create: `tests/js/lib.test.js`, `tests/test_site_helpers.py`
- Create: `site/lib.js`

Everything the page works out lives in `site/lib.js`. It imports nothing and never touches the page, so Node can test it without a browser.

| Helpers | What they answer |
|---|---|
| `dateToSeconds`, `formatDate`, `formatDayMonth` | Dates as the charts and the text need them |
| `indexOnOrBefore`, `indexOnOrAfter`, `visibleSpan`, `clampIndex` | Which rows of a sorted date list fall inside a range |
| `yearsBefore`, `presetRange`, `customRange` | The range a preset or a typed pair of dates stands for |
| `tenorPositions`, `curveOn`, `tenorName` | Where each tenor sits along the curve's axis in either mode, and the curve on one date |
| `tenorLabelOrder`, `labelsThatFit` | Which tenor labels to draw when there is not room for all of them |
| `niceTicks`, `formatPercent`, `formatRange` | Round axis values and number formats |
| `nextMeeting`, `countdownParts`, `ageInDays`, `oddsAreOutdated`, `publishedTargetLags` | The countdown and the page's three notices |

The tests are JavaScript, run by Node's built-in test runner. `tests/test_site_helpers.py` runs them from pytest, so one command still runs every test in the project.

- [ ] **Step 1: Write the failing tests**

**File: `tests/js/lib.test.js`**

```javascript
import assert from "node:assert/strict";
import { test } from "node:test";

import * as lib from "../../site/lib.js";

const DATES = ["2026-09-24", "2026-09-25", "2026-10-01", "2026-10-02"];

test("dateToSeconds is midnight UTC", () => {
  assert.equal(lib.dateToSeconds("1970-01-02"), 86400);
  assert.equal(lib.dateToSeconds("2026-10-02"), Date.UTC(2026, 9, 2) / 1000);
});

test("formatDate drops the leading zero and names the month", () => {
  assert.equal(lib.formatDate("2026-10-02"), "2 Oct 2026");
  assert.equal(lib.formatDate("1990-01-31"), "31 Jan 1990");
});

test("formatDayMonth is the short form for a tight column", () => {
  assert.equal(lib.formatDayMonth("2026-10-02"), "2 Oct");
  assert.equal(lib.formatDayMonth("2026-09-25"), "25 Sep");
});

test("indexOnOrBefore finds the last date not after the target", () => {
  assert.equal(lib.indexOnOrBefore(DATES, "2026-09-27"), 1);
  assert.equal(lib.indexOnOrBefore(DATES, "2026-09-25"), 1);
  assert.equal(lib.indexOnOrBefore(DATES, "2030-01-01"), 3);
  assert.equal(lib.indexOnOrBefore(DATES, "2026-01-01"), -1);
});

test("indexOnOrAfter finds the first date not before the target", () => {
  assert.equal(lib.indexOnOrAfter(DATES, "2026-09-27"), 2);
  assert.equal(lib.indexOnOrAfter(DATES, "2026-09-25"), 1);
  assert.equal(lib.indexOnOrAfter(DATES, "2026-01-01"), 0);
  assert.equal(lib.indexOnOrAfter(DATES, "2030-01-01"), 4);
});

test("visibleSpan covers the dates inside a range, or is null", () => {
  assert.deepEqual(lib.visibleSpan(DATES, "2026-09-25", "2026-10-01"), { first: 1, last: 2 });
  assert.deepEqual(lib.visibleSpan(DATES, "2020-01-01", "2030-01-01"), { first: 0, last: 3 });
  assert.equal(lib.visibleSpan(DATES, "2026-09-26", "2026-09-30"), null);
});

test("clampIndex snaps to the nearer end of the span", () => {
  const span = { first: 10, last: 20 };
  assert.equal(lib.clampIndex(5, span), 10);
  assert.equal(lib.clampIndex(15, span), 15);
  assert.equal(lib.clampIndex(99, span), 20);
});

test("yearsBefore keeps the day and handles 29 February", () => {
  assert.equal(lib.yearsBefore("2026-10-02", 10), "2016-10-02");
  assert.equal(lib.yearsBefore("2024-02-29", 1), "2023-02-28");
  assert.equal(lib.yearsBefore("2024-02-29", 4), "2020-02-29");
});

test("presetRange stays inside the data", () => {
  assert.deepEqual(lib.presetRange("10Y", "1990-01-02", "2026-10-02"), { from: "2016-10-02", to: "2026-10-02" });
  assert.deepEqual(lib.presetRange("5Y", "2024-01-02", "2026-10-02"), { from: "2024-01-02", to: "2026-10-02" });
  assert.deepEqual(lib.presetRange("MAX", "1990-01-02", "2026-10-02"), { from: "1990-01-02", to: "2026-10-02" });
});

test("customRange clamps, orders, and rejects half-typed dates", () => {
  const first = "1990-01-02";
  const last = "2026-10-02";
  assert.deepEqual(lib.customRange("2008-01-01", "2010-12-31", first, last), { from: "2008-01-01", to: "2010-12-31" });
  assert.deepEqual(lib.customRange("1980-01-01", "2030-01-01", first, last), { from: first, to: last });
  assert.deepEqual(lib.customRange("2020-01-01", "2010-01-01", first, last), { from: "2010-01-01", to: "2020-01-01" });
  assert.equal(lib.customRange("", "2010-01-01", first, last), null);
  assert.equal(lib.customRange("2010-1-1", "2010-01-01", first, last), null);
});

test("customRange rejects a range with no width", () => {
  const first = "1990-01-02";
  const last = "2026-10-02";
  assert.equal(lib.customRange("2010-01-01", "2010-01-01", first, last), null);
  assert.equal(lib.customRange("1980-01-01", "1985-01-01", first, last), null);
  assert.deepEqual(lib.customRange("2010-01-01", "2010-01-02", first, last), { from: "2010-01-01", to: "2010-01-02" });
});

const TENORS = [
  { label: "3M", years: 0.25 },
  { label: "2Y", years: 2 },
  { label: "10Y", years: 10 },
  { label: "30Y", years: 30 },
];

test("tenorPositions are even in one mode and by years in the other", () => {
  assert.deepEqual(lib.tenorPositions(TENORS, "even"), [0, 1 / 3, 2 / 3, 1]);
  assert.deepEqual(lib.tenorPositions(TENORS, "scale"), [0.25 / 30, 2 / 30, 10 / 30, 1]);
  assert.deepEqual(lib.tenorPositions([TENORS[0]], "even"), [0.5]);
});

test("curveOn keeps only the tenors published that day", () => {
  const yields = { tenors: TENORS, values: [[null, 4.19], [3.5, 4.83], [4.1, 5.28], [4.8, 5.63]] };
  assert.deepEqual(lib.curveOn(yields, 0).map((point) => point.label), ["2Y", "10Y", "30Y"]);
  assert.deepEqual(lib.curveOn(yields, 1)[0], { index: 0, label: "3M", years: 0.25, value: 4.19 });
});

test("tenorName, formatPercent and formatRange", () => {
  assert.equal(lib.tenorName("10Y"), "10-year");
  assert.equal(lib.tenorName("1.5M"), "1.5-month");
  assert.equal(lib.formatPercent(5.28), "5.28%");
  assert.equal(lib.formatPercent(77.9, 1), "77.9%");
  assert.equal(lib.formatPercent(0, 1), "0.0%");
  assert.equal(lib.formatPercent(null), "n/a");
  assert.equal(lib.formatRange([3.75, 4]), "3.75–4.00%");
});

test("niceTicks are round and cover the values", () => {
  assert.deepEqual(lib.niceTicks(4.04, 5.67), [4, 4.5, 5, 5.5, 6]);
  assert.deepEqual(lib.niceTicks(0.05, 1.9), [0, 0.5, 1, 1.5, 2]);
  assert.deepEqual(lib.niceTicks(3, 3), [2.4, 2.6, 2.8, 3, 3.2, 3.4, 3.6]);
  const ticks = lib.niceTicks(6.63, 8.26);
  assert.ok(ticks[0] <= 6.63 && ticks.at(-1) >= 8.26);
});

const ALL_TENORS = ["1M", "1.5M", "2M", "3M", "4M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"].map((label) => ({
  label,
  years: label.endsWith("Y") ? Number(label.slice(0, -1)) : Number(label.slice(0, -1)) / 12,
}));

test("tenorLabelOrder puts the most watched tenors first and the rest in data order", () => {
  const order = lib.tenorLabelOrder(ALL_TENORS).map((index) => ALL_TENORS[index].label);
  assert.deepEqual(order, ["10Y", "2Y", "30Y", "5Y", "3M", "1Y", "20Y", "7Y", "3Y", "6M", "1M", "1.5M", "2M", "4M"]);
  assert.deepEqual(lib.tenorLabelOrder(TENORS), [2, 1, 3, 0]);
});

test("labelsThatFit takes labels in order of importance and skips the ones that would collide", () => {
  assert.deepEqual(lib.labelsThatFit([0, 50, 100], 20, [0, 1, 2]), [0, 1, 2]);
  assert.deepEqual(lib.labelsThatFit([0, 10, 20, 30, 40], 20, [4, 3, 2, 1, 0]), [0, 2, 4]);
  assert.deepEqual(lib.labelsThatFit([0, 10, 20, 30, 40], 20, [1, 0, 2, 3, 4]), [1, 3]);
});

test("a narrow curve keeps the tenors people look for, at both ends of the axis", () => {
  const label = (positions, gap) =>
    lib.labelsThatFit(positions, gap, lib.tenorLabelOrder(ALL_TENORS)).map((index) => ALL_TENORS[index].label);
  const even = lib.tenorPositions(ALL_TENORS, "even").map((share) => share * 280);
  assert.deepEqual(label(even, 32), ["1M", "3M", "6M", "2Y", "5Y", "10Y", "30Y"]);
  const scale = lib.tenorPositions(ALL_TENORS, "scale").map((share) => share * 508);
  assert.deepEqual(label(scale, 28), ["3M", "2Y", "5Y", "7Y", "10Y", "20Y", "30Y"]);
  const wide = lib.tenorPositions(ALL_TENORS, "even").map((share) => share * 508);
  assert.equal(label(wide, 32).length, 14);
});

const MEETINGS = [
  { end: "2026-10-28", statement_at: "2026-10-28T18:00:00Z" },
  { end: "2026-12-09", statement_at: "2026-12-09T19:00:00Z" },
];

test("nextMeeting is the first whose statement is still ahead", () => {
  assert.equal(lib.nextMeeting(MEETINGS, Date.parse("2026-10-28T17:59:00Z")).end, "2026-10-28");
  assert.equal(lib.nextMeeting(MEETINGS, Date.parse("2026-10-28T18:00:00Z")).end, "2026-12-09");
  assert.equal(lib.nextMeeting(MEETINGS, Date.parse("2027-01-01T00:00:00Z")), null);
});

test("countdownParts splits the time left and stops at zero", () => {
  const target = "2026-10-28T18:00:00Z";
  assert.deepEqual(lib.countdownParts(Date.parse("2026-10-04T01:55:00Z"), target), { days: 24, hours: 16, minutes: 5, past: false });
  assert.deepEqual(lib.countdownParts(Date.parse("2026-10-28T17:59:30Z"), target), { days: 0, hours: 0, minutes: 0, past: false });
  assert.deepEqual(lib.countdownParts(Date.parse("2026-10-29T00:00:00Z"), target), { days: 0, hours: 0, minutes: 0, past: true });
});

test("ageInDays counts whole days and never goes negative", () => {
  assert.equal(lib.ageInDays("2026-10-03T18:15:00Z", Date.parse("2026-10-07T18:14:00Z")), 3);
  assert.equal(lib.ageInDays("2026-10-03T18:15:00Z", Date.parse("2026-10-07T18:15:00Z")), 4);
  assert.equal(lib.ageInDays("2026-10-03T18:15:00Z", Date.parse("2026-10-01T00:00:00Z")), 0);
});

test("oddsAreOutdated once the meeting's statement is out, or the meeting is off the list", () => {
  const odds = { meeting: "2026-10-28" };
  assert.equal(lib.oddsAreOutdated(odds, MEETINGS, Date.parse("2026-10-28T17:00:00Z")), false);
  assert.equal(lib.oddsAreOutdated(odds, MEETINGS, Date.parse("2026-10-28T18:00:00Z")), true);
  assert.equal(lib.oddsAreOutdated({ meeting: "2026-09-16" }, MEETINGS, Date.parse("2026-10-01T00:00:00Z")), true);
});

test("publishedTargetLags compares the last published range with the current one", () => {
  const fed = { dates: ["a", "b"], target_lower: [3.5, 3.75], target_upper: [3.75, 4.0] };
  assert.equal(lib.publishedTargetLags(fed, { current_range: [3.75, 4.0] }), false);
  assert.equal(lib.publishedTargetLags(fed, { current_range: [4.0, 4.25] }), true);
});
```

**File: `tests/test_site_helpers.py`**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
node --test tests/js/lib.test.js
.venv/bin/python -m pytest tests/test_site_helpers.py
```

Expected: Node reports `ERR_MODULE_NOT_FOUND` for `site/lib.js`; pytest reports `2 failed`.

Give Node the file path, as written. On recent Node versions, passing the folder fails.

- [ ] **Step 3: Write the helpers**

**File: `site/lib.js`**

```javascript
// Pure helpers for the page: no DOM and no network, so they run under `node --test`.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
// Which tenors get an axis label first when there is not room for all of them.
const TENOR_LABEL_ORDER = ["10Y", "2Y", "30Y", "5Y", "3M", "1Y", "20Y", "7Y", "3Y", "6M", "1M"];

export const PRESET_YEARS = { "1Y": 1, "5Y": 5, "10Y": 10 };

/** "2026-10-02" as seconds since the epoch at midnight UTC. */
export function dateToSeconds(iso) {
  return Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10))) / 1000;
}

/** "2026-10-02" becomes "2 Oct 2026". */
export function formatDate(iso) {
  return `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}`;
}

/** "2026-10-02" becomes "2 Oct": the short form, for a tight table column. */
export function formatDayMonth(iso) {
  return `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]}`;
}

/** Index of the last date not after `target` in a sorted list of ISO dates, or -1. */
export function indexOnOrBefore(dates, target) {
  let low = 0;
  let high = dates.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (dates[middle] <= target) low = middle + 1;
    else high = middle;
  }
  return low - 1;
}

/** Index of the first date not before `target`, or `dates.length`. */
export function indexOnOrAfter(dates, target) {
  let low = 0;
  let high = dates.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (dates[middle] < target) low = middle + 1;
    else high = middle;
  }
  return low;
}

/** The first and last indexes of the dates inside [from, to], or null when there are none. */
export function visibleSpan(dates, from, to) {
  const first = indexOnOrAfter(dates, from);
  const last = indexOnOrBefore(dates, to);
  return first <= last ? { first, last } : null;
}

/** An index kept inside a span, snapping to the nearer end. */
export function clampIndex(index, span) {
  return Math.min(span.last, Math.max(span.first, index));
}

/** The ISO date `years` years before `iso`. 29 February falls back to the 28th. */
export function yearsBefore(iso, years) {
  const year = Number(iso.slice(0, 4)) - years;
  const month = iso.slice(5, 7);
  const day = iso.slice(8, 10);
  const leap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
  const safeDay = month === "02" && day === "29" && !leap ? "28" : day;
  return `${String(year).padStart(4, "0")}-${month}-${safeDay}`;
}

/** The date range a preset stands for, kept inside the data's first and last dates. */
export function presetRange(preset, first, last) {
  if (!(preset in PRESET_YEARS)) return { from: first, to: last };
  const from = yearsBefore(last, PRESET_YEARS[preset]);
  return { from: from < first ? first : from, to: last };
}

/**
 * A typed range, kept inside the data and put in order.
 * Null unless both are full ISO dates and, once inside the data, they are different days.
 */
export function customRange(from, to, first, last) {
  if (!ISO_DATE.test(from) || !ISO_DATE.test(to)) return null;
  const inside = (value) => (value < first ? first : value > last ? last : value);
  const start = inside(from);
  const end = inside(to);
  if (start === end) return null;
  return start < end ? { from: start, to: end } : { from: end, to: start };
}

/** Where each tenor sits along the curve's axis, from 0 to 1. */
export function tenorPositions(tenors, mode) {
  if (tenors.length === 1) return [0.5];
  if (mode === "scale") {
    const longest = tenors[tenors.length - 1].years;
    return tenors.map((tenor) => tenor.years / longest);
  }
  return tenors.map((_, index) => index / (tenors.length - 1));
}

/** The curve on one date: a point for each tenor that has a value. */
export function curveOn(yields, dateIndex) {
  const points = [];
  yields.tenors.forEach((tenor, index) => {
    const value = yields.values[index][dateIndex];
    if (value !== null && value !== undefined) points.push({ index, label: tenor.label, years: tenor.years, value });
  });
  return points;
}

/** "10Y" becomes "10-year" and "3M" becomes "3-month". */
export function tenorName(label) {
  return `${label.slice(0, -1)}-${label.endsWith("Y") ? "year" : "month"}`;
}

export function formatPercent(value, digits = 2) {
  return value === null || value === undefined ? "n/a" : `${value.toFixed(digits)}%`;
}

/** [3.75, 4] becomes "3.75–4.00%". */
export function formatRange(range) {
  return `${range[0].toFixed(2)}–${range[1].toFixed(2)}%`;
}

/** Round axis values covering [min, max], roughly `count` of them. */
export function niceTicks(min, max, count = 5) {
  let low = min;
  let high = max;
  if (low === high) {
    low -= 0.5;
    high += 0.5;
  }
  const rough = (high - low) / count;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((factor) => factor * power).find((candidate) => candidate >= rough - 1e-12);
  const start = Math.floor(low / step + 1e-9) * step;
  const end = Math.ceil(high / step - 1e-9) * step;
  const ticks = [];
  for (let value = start; value <= end + step / 2; value += step) ticks.push(Number(value.toFixed(6)));
  return ticks;
}

/** Tenor indexes in the order their axis labels matter: the most watched first, the rest in data order. */
export function tenorLabelOrder(tenors) {
  const rank = (index) => {
    const place = TENOR_LABEL_ORDER.indexOf(tenors[index].label);
    return place < 0 ? TENOR_LABEL_ORDER.length : place;
  };
  return tenors.map((_, index) => index).sort((a, b) => rank(a) - rank(b) || a - b);
}

/** The labels to draw: taken in `order`, skipping any that would sit within `gap` pixels of one already taken. */
export function labelsThatFit(positions, gap, order) {
  const taken = [];
  for (const index of order) {
    if (taken.every((other) => Math.abs(positions[index] - positions[other]) >= gap)) taken.push(index);
  }
  return taken.sort((a, b) => a - b);
}

/** The first meeting whose statement is still ahead of `nowMs`, or null. */
export function nextMeeting(meetings, nowMs) {
  return meetings.find((meeting) => Date.parse(meeting.statement_at) > nowMs) ?? null;
}

/** Whole days, hours and minutes from `nowMs` to an instant. All zero once it has passed. */
export function countdownParts(nowMs, target) {
  const left = Math.max(0, Date.parse(target) - nowMs);
  const minutes = Math.floor(left / 60000);
  return {
    days: Math.floor(minutes / 1440),
    hours: Math.floor((minutes % 1440) / 60),
    minutes: minutes % 60,
    past: left === 0,
  };
}

/** Whole days since the data was generated. */
export function ageInDays(generatedAt, nowMs) {
  return Math.max(0, Math.floor((nowMs - Date.parse(generatedAt)) / 86400000));
}

/** True once the statement of the meeting the odds were calculated for has come out. */
export function oddsAreOutdated(odds, meetings, nowMs) {
  const meeting = meetings.find((candidate) => candidate.end === odds.meeting);
  return !meeting || Date.parse(meeting.statement_at) <= nowMs;
}

/** True when the published target range is not the one the odds treat as current. */
export function publishedTargetLags(fedFunds, odds) {
  const last = fedFunds.dates.length - 1;
  return fedFunds.target_lower[last] !== odds.current_range[0] || fedFunds.target_upper[last] !== odds.current_range[1];
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
node --test tests/js/lib.test.js
.venv/bin/python -m pytest tests/test_site_helpers.py
```

Expected: Node reports `pass 23` and `fail 0`; pytest reports `2 passed`.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `236 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `tests/js/lib.test.js`, `tests/test_site_helpers.py`, `site/lib.js`. Suggested message: `feat: page helpers with tests`.

---

### Task 4: The page

**Files:**
- Create: `tests/test_site_page.py`, `site/charts.js`
- Replace: `site/index.html`, `site/style.css`, `site/app.js`

This replaces the placeholder page. What each file holds:

- **`index.html`:** the structure and the fixed text. Everything that depends on the data is an empty element with an `id`, filled in by `app.js`. Sections that need data stay hidden until it has loaded.
- **`style.css`:** layout and colour. Colours are named roles, defined at the top for light and again for dark.
- **`charts.js`:** three drawing functions. `timeChart` wraps uPlot for the two history charts. `drawCurve` and `drawOdds` build SVG.
- **`app.js`:** loads `data.json`, keeps the four choices, and wires the controls.

The charts follow the project's chart rules (spec section 5.8):

- One axis per chart. Lines are 2px. Dots are at least 8px across with a 2px rim in the surface colour. Columns are at most 24px wide with a rounded top and a square base. Gridlines are solid hairlines.
- Text is never in a series colour. A value label carries a rim in the surface colour, so it stays readable where a line runs behind it.
- Only the Fed funds chart has two series, so only it has a legend.
- Every chart has a tooltip on hover and on keyboard focus. Nothing is readable only from a tooltip: the readouts, the curve table and the odds table carry the same numbers.
- The two series colours were checked with the dataviz skill's validator against both surfaces: `#2a78d6` and `#eb6834` in light, `#3987e5` and `#d95926` in dark. Every check passed.

These files were tested in Chrome before this plan was written: light and dark, at 1280px and 390px wide, with every control exercised and no console or security-policy errors.

The tests in this task read the page files as text. They catch the mistakes that would otherwise show only in a browser: a missing element, something the security policy would block, an address without the build id, and a colour role that is not defined for both themes.

- [ ] **Step 1: Write the failing test**

**File: `tests/test_site_page.py`**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_site_page.py`

Expected: `6 failed`, because the placeholder page has none of this.

- [ ] **Step 3: Write the page**

**File: `site/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="color-scheme" content="light dark">
<title>Macros</title>
<link rel="icon" href="data:,">
<link rel="stylesheet" href="vendor/uPlot.min.css?v={{BUILD_ID}}">
<link rel="stylesheet" href="style.css?v={{BUILD_ID}}">
</head>
<body>
<header class="top">
  <div class="top-main">
    <h1>Macros</h1>
    <a id="explain" class="button" target="_blank" rel="noopener" hidden>Explain Macros</a>
    <span id="explain-off" class="button is-off" aria-disabled="true" hidden>Explain Macros</span>
    <span id="explain-note" class="quiet"></span>
  </div>
  <p id="refreshed" class="quiet"></p>
</header>

<div class="alerts">
  <p id="load-error" class="notice" role="alert" hidden></p>
  <noscript><p class="notice">This page needs JavaScript to draw its charts.</p></noscript>
</div>

<main id="page" hidden>
  <div class="filters" role="group" aria-label="Date range for the two history charts">
    <span class="filters-label">Range</span>
    <div class="segmented" id="presets">
      <button type="button" data-preset="1Y" aria-pressed="false">1Y</button>
      <button type="button" data-preset="5Y" aria-pressed="false">5Y</button>
      <button type="button" data-preset="10Y" aria-pressed="true">10Y</button>
      <button type="button" data-preset="MAX" aria-pressed="false">Max</button>
    </div>
    <label>From <input type="date" id="from"></label>
    <label>To <input type="date" id="to"></label>
  </div>

  <section aria-labelledby="yields-heading">
    <h2 id="yields-heading">US Treasury yields</h2>
    <div class="pair">
      <figure class="card">
        <figcaption>
          <h3 id="history-title">Yield history</h3>
          <p id="history-readout" class="readout"></p>
        </figcaption>
        <div id="history-chart" class="plot" role="img" aria-labelledby="history-title"></div>
        <div class="slider">
          <input type="range" id="date-slider" step="1">
          <label for="date-slider">Date shown on the yield curve</label>
        </div>
      </figure>

      <figure class="card">
        <figcaption class="with-control">
          <div>
            <h3 id="curve-title">Yield curve</h3>
            <p id="curve-readout" class="readout"></p>
          </div>
          <div class="segmented" id="modes" role="group" aria-label="Horizontal axis">
            <button type="button" data-mode="even" aria-pressed="true">Even spacing</button>
            <button type="button" data-mode="scale" aria-pressed="false">True scale</button>
          </div>
        </figcaption>
        <div id="curve-chart" class="plot"></div>
        <div class="slider" id="tenor-slider-wrap" data-hint="Switch to even spacing to pick a tenor">
          <input type="range" id="tenor-slider" step="1">
          <label for="tenor-slider">Tenor shown on the yield history</label>
        </div>
        <details>
          <summary>Show table</summary>
          <table id="curve-table">
            <thead><tr><th scope="col">Tenor</th><th scope="col">Yield</th></tr></thead>
            <tbody></tbody>
          </table>
        </details>
      </figure>
    </div>
  </section>

  <section aria-labelledby="fomc-heading">
    <h2 id="fomc-heading">Next FOMC decision</h2>
    <p id="odds-outdated" class="notice" hidden></p>
    <div class="pair">
      <div class="card glance">
        <div>
          <p class="label">Time to the next statement</p>
          <p id="countdown" class="hero"></p>
          <p id="countdown-when" class="quiet"></p>
        </div>
        <div>
          <h3 id="odds-title">Odds for the decision</h3>
          <div class="tiles" id="odds-tiles"></div>
          <p id="odds-readout" class="readout"></p>
        </div>
      </div>

      <figure class="card">
        <figcaption>
          <h3>Odds by target range</h3>
          <p class="readout">Where the target range would be after the decision, in percent</p>
        </figcaption>
        <div id="odds-chart" class="plot"></div>
      </figure>
    </div>

    <div class="card below">
      <h3>How the odds have moved</h3>
      <div class="aside">
        <div class="scroll">
          <table id="odds-table">
            <thead></thead>
            <tbody></tbody>
          </table>
        </div>
        <p class="quiet">Own calculation from 30-Day Federal Funds futures prices, using the method CME Group publishes for its FedWatch tool. These are not CME FedWatch figures.</p>
      </div>
    </div>
  </section>

  <section aria-labelledby="fed-heading">
    <h2 id="fed-heading">Fed funds rate and target range</h2>
    <figure class="card">
      <figcaption class="with-control">
        <p id="fed-readout" class="readout"></p>
        <ul class="legend">
          <li><span class="key line series-1"></span>Effective rate (EFFR)</li>
          <li><span class="key box series-2"></span>Target range</li>
        </ul>
      </figcaption>
      <div id="fed-chart" class="plot" role="img" aria-labelledby="fed-heading"></div>
      <p id="fed-lag" class="notice" hidden></p>
    </figure>
  </section>
</main>

<footer id="notices" hidden>
  <h2>Sources and notices</h2>
  <ul>
    <li>Yields: U.S. Department of the Treasury, Daily Treasury Par Yield Curve Rates.</li>
    <li>The EFFR is subject to the Terms of Use posted at newyorkfed.org. The New York Fed is not responsible for publication of the EFFR by theta-markets.com, does not sanction or endorse any particular republication, and has no liability for your use.</li>
    <li>Rate odds: own calculation from futures prices. Not investment advice.</li>
    <li id="ai-notice" hidden></li>
  </ul>
</footer>

<script src="vendor/uPlot.iife.min.js?v={{BUILD_ID}}" defer></script>
<script type="module" src="app.js?v={{BUILD_ID}}"></script>
</body>
</html>
```

**File: `site/style.css`**

```css
/* Colours are roles, defined once for light and once for dark. The charts read them from here. */
:root {
  color-scheme: light dark;
  --page: #f9f9f7;
  --surface: #fcfcfb;
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --muted: #898781;
  --grid: #e1e0d9;
  --axis: #c3c2b7;
  --border: rgba(11, 11, 11, 0.1);
  --series-1: #2a78d6;
  --series-2: #eb6834;
  --series-2-wash: rgba(235, 104, 52, 0.14);
  --thumb: 16px;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}

@media (prefers-color-scheme: dark) {
  :root {
    --page: #0d0d0d;
    --surface: #1a1a19;
    --ink: #ffffff;
    --ink-2: #c3c2b7;
    --muted: #898781;
    --grid: #2c2c2a;
    --axis: #383835;
    --border: rgba(255, 255, 255, 0.1);
    --series-1: #3987e5;
    --series-2: #d95926;
    --series-2-wash: rgba(217, 89, 38, 0.22);
  }
}

* {
  box-sizing: border-box;
}

/* `hidden` must win over any class that sets `display`. */
[hidden] {
  display: none !important;
}

body {
  margin: 0;
  background: var(--page);
  color: var(--ink);
  font-size: 15px;
  line-height: 1.45;
}

.top,
.alerts,
main,
footer {
  max-width: 1240px;
  margin: 0 auto;
  padding: 0 20px;
}

.top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 24px;
  padding-top: 20px;
  padding-bottom: 12px;
}

.top-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
}

h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
}

h2 {
  margin: 28px 0 10px;
  font-size: 17px;
  font-weight: 650;
}

h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

p {
  margin: 0;
}

.quiet {
  color: var(--ink-2);
  font-size: 13px;
}

.readout {
  color: var(--ink-2);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  min-height: 19px;
}

.notice {
  margin-top: 10px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink-2);
  font-size: 13px;
}

/* Buttons and the two-or-more-way switches */
.button {
  display: inline-block;
  padding: 8px 16px;
  border: 1px solid var(--ink);
  border-radius: 8px;
  background: var(--ink);
  color: var(--surface);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
}

.button:hover {
  opacity: 0.88;
}

.button.is-off {
  border-color: var(--border);
  background: transparent;
  color: var(--muted);
  cursor: not-allowed;
}

.segmented {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.segmented button {
  padding: 5px 12px;
  border: 0;
  background: var(--surface);
  color: var(--ink-2);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.segmented button + button {
  border-left: 1px solid var(--border);
}

.segmented button[aria-pressed="true"] {
  background: var(--ink);
  color: var(--surface);
  font-weight: 600;
}

:focus-visible {
  outline: 2px solid var(--series-1);
  outline-offset: 2px;
}

/* The one filter row, above everything it scopes */
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  margin-top: 4px;
  color: var(--ink-2);
  font-size: 13px;
}

.filters-label {
  font-weight: 600;
}

.filters input[type="date"] {
  margin-left: 4px;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--ink);
  font: inherit;
}

/* Cards and layout */
.pair {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}

.card {
  min-width: 0;
  margin: 0;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
}

.card.below {
  margin-top: 16px;
}

/* The numbers to take in at a glance: two groups, spread over the card's height. */
.glance {
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  gap: 20px;
}

section > .notice {
  margin: 0 0 12px;
}

figcaption {
  margin-bottom: 8px;
}

figcaption.with-control {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px 16px;
}

.plot {
  position: relative;
  overflow: hidden;
}

.plot svg {
  display: block;
}

/* Sliders: a fixed 16px thumb, so their travel can be lined up with the chart above */
.slider {
  position: relative;
  margin-top: 6px;
}

.slider label {
  display: block;
  color: var(--ink-2);
  font-size: 12px;
}

input[type="range"] {
  display: block;
  height: 28px;
  margin: 0;
  background: transparent;
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
}

input[type="range"]::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: 2px;
  background: var(--axis);
}

input[type="range"]::-moz-range-track {
  height: 4px;
  border-radius: 2px;
  background: var(--axis);
}

input[type="range"]::-webkit-slider-thumb {
  box-sizing: border-box;
  width: var(--thumb);
  height: var(--thumb);
  margin-top: -6px;
  border: 2px solid var(--surface);
  border-radius: 50%;
  background: var(--series-1);
  -webkit-appearance: none;
  appearance: none;
}

input[type="range"]::-moz-range-thumb {
  box-sizing: border-box;
  width: var(--thumb);
  height: var(--thumb);
  border: 2px solid var(--surface);
  border-radius: 50%;
  background: var(--series-1);
}

input[type="range"]:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.slider.is-locked {
  cursor: not-allowed;
}

.slider.is-locked::after {
  content: attr(data-hint);
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--ink);
  color: var(--surface);
  font-size: 12px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
}

.slider.is-locked:hover::after,
.slider.is-locked:focus::after {
  opacity: 1;
}

/* SVG charts take their colours from the same roles */
.grid {
  stroke: var(--grid);
  stroke-width: 1;
}

.axis {
  stroke: var(--axis);
  stroke-width: 1;
}

.tick {
  fill: var(--muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.tick.strong {
  fill: var(--ink-2);
}

.line {
  fill: none;
  stroke: var(--series-1);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.dot {
  fill: var(--series-1);
  stroke: var(--surface);
  stroke-width: 2;
}

.column {
  fill: var(--series-1);
}

/* A value label keeps a rim of the surface colour, so it stays readable where a line runs behind it. */
.point-label {
  fill: var(--ink);
  stroke: var(--surface);
  stroke-width: 4px;
  stroke-linejoin: round;
  paint-order: stroke;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

/* Hit targets are invisible until the pointer or the keyboard is on them. */
.hit {
  fill: var(--ink);
  fill-opacity: 0;
  outline: none;
}

.hit:hover {
  fill-opacity: 0.06;
}

.hit.pick {
  cursor: pointer;
}

.hit:focus-visible {
  stroke: var(--series-1);
  stroke-width: 2;
}

/* uPlot's cursor line: a solid hairline, not its default dashes */
.u-hz .u-cursor-x {
  border-right: 1px solid var(--axis);
}

/* Tooltip, legend and their colour keys */
.tip {
  position: absolute;
  z-index: 2;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
  font-size: 12px;
  white-space: nowrap;
  pointer-events: none;
}

.tip-title {
  color: var(--ink-2);
}

.tip-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-variant-numeric: tabular-nums;
}

.tip-row span:last-child {
  color: var(--ink-2);
}

.key {
  display: inline-block;
  flex: none;
}

.key.line {
  width: 14px;
  height: 2px;
  border-radius: 1px;
}

.key.box {
  width: 12px;
  height: 10px;
  border-radius: 2px;
}

.key.series-1 {
  background: var(--series-1);
}

.key.series-2 {
  background: var(--series-2);
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--ink-2);
  font-size: 13px;
}

.legend li {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Numbers that stand alone */
.label {
  color: var(--ink-2);
  font-size: 13px;
}

.hero {
  margin: 2px 0 6px;
  font-size: 56px;
  font-weight: 650;
  line-height: 1.1;
}

.tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 28px;
  margin: 8px 0;
}

.tile {
  display: flex;
  flex-direction: column;
}

.tile .value {
  font-size: 24px;
  font-weight: 650;
}

/* Tables: the same numbers without the chart */
table {
  width: 100%;
  margin-top: 8px;
  border-collapse: collapse;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

th,
td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--grid);
  text-align: right;
  white-space: nowrap;
}

/* A table too wide for a narrow screen scrolls inside its card, not the page. */
.scroll {
  overflow-x: auto;
}

th:first-child {
  text-align: left;
}

thead th {
  color: var(--ink-2);
  font-weight: 600;
  vertical-align: bottom;
}

tbody th {
  font-weight: 600;
}

.sub {
  display: block;
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 400;
}

details {
  margin-top: 8px;
}

summary {
  width: max-content;
  color: var(--ink-2);
  font-size: 13px;
  cursor: pointer;
}

#curve-table {
  max-width: 260px;
}

/* A table with a note beside it, or under it when there is no room. */
.aside {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 40px;
}

.aside .scroll {
  flex: 1 1 420px;
  max-width: 620px;
}

.aside .quiet {
  flex: 1 1 260px;
}

footer {
  margin-top: 32px;
  padding-bottom: 40px;
  color: var(--ink-2);
  font-size: 13px;
}

footer h2 {
  margin-top: 0;
  font-size: 14px;
}

footer ul {
  margin: 0;
  padding-left: 18px;
}

footer li + li {
  margin-top: 4px;
}

@media (max-width: 900px) {
  .pair {
    grid-template-columns: minmax(0, 1fr);
  }

  .hero {
    font-size: 44px;
  }
}

@media (max-width: 480px) {
  .top,
  .alerts,
  main,
  footer {
    padding-left: 12px;
    padding-right: 12px;
  }

  .card {
    padding: 12px;
  }

  th,
  td {
    padding: 5px 4px;
  }
}
```

**File: `site/charts.js`**

```javascript
// Drawing: the two history charts with uPlot, and the curve and odds charts in SVG.
// Everything here touches the page; the arithmetic lives in lib.js.
/* global uPlot */
import { formatPercent, labelsThatFit, niceTicks, tenorLabelOrder, tenorPositions } from "./lib.js?v={{BUILD_ID}}";

const SVG_NS = "http://www.w3.org/2000/svg";
const FONT = '12px system-ui, -apple-system, "Segoe UI", sans-serif';
const TIME_CHART_HEIGHT = 280;
const CURVE = { height: 280, left: 48, right: 18, top: 24, bottom: 50 }; // the same baseline as the time chart beside it
const ODDS = { plot: 156, left: 44, right: 12, top: 28, column: 24, oneLine: 72 }; // oneLine: the room a range label needs
const LABEL_GAP = { even: 32, scale: 28 }; // the least distance between two tenor labels, in pixels

// Time axis: ticks never finer than a day, and dates written day first ("2 Oct", not "10/2").
const DAY = 86400;
const X_STEPS = [
  ...[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15].map((days) => days * DAY),
  ...[1, 2, 3, 4, 6].map((months) => months * 30 * DAY),
  ...[1, 2, 5, 10, 25, 50, 100].map((years) => years * 365 * DAY),
];
const X_LABELS = [
  [365 * DAY, "{YYYY}", null, null, null, null, null, null, 1],
  [28 * DAY, "{MMM}", "\n{YYYY}", null, null, null, null, null, 1],
  [DAY, "{D} {MMM}", "\n{YYYY}", null, null, null, null, null, 1],
];

/** The colours in force, read from the stylesheet so light and dark are defined in one place. */
function readTheme() {
  const style = getComputedStyle(document.documentElement);
  const value = (name) => style.getPropertyValue(name).trim();
  return {
    surface: value("--surface"),
    ink2: value("--ink-2"),
    muted: value("--muted"),
    grid: value("--grid"),
    axis: value("--axis"),
    series1: value("--series-1"),
    series2: value("--series-2"),
    wash2: value("--series-2-wash"),
  };
}

function svg(name, attributes = {}, text = null) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  if (text !== null) node.textContent = text;
  return node;
}

const tips = new WeakMap();

/**
 * One tooltip per chart host: a title, then rows with the value first and its label after.
 * It sits `gap` pixels to the right of x, or to the left when there is no room on the right.
 */
function tipFor(host) {
  if (tips.has(host)) return tips.get(host);
  const box = document.createElement("div");
  box.className = "tip";
  box.hidden = true;
  host.append(box);
  const tip = {
    show(title, rows, x, y, gap = 14) {
      box.replaceChildren();
      const heading = document.createElement("div");
      heading.className = "tip-title";
      heading.textContent = title;
      box.append(heading);
      for (const row of rows) {
        const line = document.createElement("div");
        line.className = "tip-row";
        if (row.key) {
          const key = document.createElement("span");
          key.className = `key ${row.key}`;
          line.append(key);
        }
        const value = document.createElement("strong");
        value.textContent = row.value;
        const label = document.createElement("span");
        label.textContent = row.label;
        line.append(value, label);
        box.append(line);
      }
      box.hidden = false;
      const width = box.offsetWidth;
      const left = x + gap + width > host.clientWidth ? x - gap - width : x + gap;
      box.style.left = `${Math.max(0, left)}px`;
      box.style.top = `${Math.max(0, y)}px`;
    },
    hide() {
      box.hidden = true;
    },
  };
  tips.set(host, tip);
  return tip;
}

/**
 * A uPlot time chart with a marker at one date and a tooltip that follows the pointer.
 *
 * `describe(theme)` returns `{ series, bands }` for the data columns after x.
 * `tooltip(index)` returns `{ title, rows }` for the data row under the pointer.
 * `onLayout()` is called once the plot area has its place, and again whenever that changes.
 */
export function timeChart(host, describe, tooltip, onLayout = null) {
  const tip = tipFor(host);
  let chart = null;
  let theme = null;
  let data = null;
  let range = null;
  let marker = null;

  function drawMarker(plot) {
    if (!marker) return;
    const box = plot.bbox;
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round(ratio));
    const centre = Math.round(plot.valToPos(marker.x, "x", true));
    if (centre < box.left || centre > box.left + box.width) return;
    const x = centre + (width % 2) / 2; // an odd-width line is sharp only when centred on a pixel
    const context = plot.ctx;
    context.save();
    context.strokeStyle = theme.ink2;
    context.lineWidth = width;
    context.beginPath();
    context.moveTo(x, box.top);
    context.lineTo(x, box.top + box.height);
    context.stroke();
    if (marker.y !== null && marker.y !== undefined) {
      const y = plot.valToPos(marker.y, "y", true);
      if (y >= box.top && y <= box.top + box.height) {
        context.fillStyle = theme.surface;
        context.beginPath();
        context.arc(x, y, 6 * ratio, 0, 2 * Math.PI);
        context.fill();
        context.fillStyle = theme.series1;
        context.beginPath();
        context.arc(x, y, 4 * ratio, 0, 2 * Math.PI);
        context.fill();
      }
    }
    context.restore();
  }

  function followPointer(plot) {
    const { idx, left } = plot.cursor;
    if (idx === null || idx === undefined || left === undefined || left < 0) {
      tip.hide();
      return;
    }
    const content = tooltip(idx);
    if (!content) {
      tip.hide();
      return;
    }
    tip.show(content.title, content.rows, plot.over.offsetLeft + left, plot.over.offsetTop + 8);
  }

  function build() {
    if (chart) chart.destroy();
    chart = null;
    if (!data || host.clientWidth === 0) return;
    theme = readTheme();
    const { series, bands } = describe(theme);
    const axis = {
      stroke: theme.muted,
      font: FONT,
      grid: { stroke: theme.grid, width: 1 },
      ticks: { stroke: theme.axis, width: 1, size: 4 },
    };
    chart = new uPlot(
      {
        width: host.clientWidth,
        height: TIME_CHART_HEIGHT,
        tzDate: (seconds) => uPlot.tzDate(new Date(seconds * 1000), "UTC"),
        legend: { show: false },
        cursor: {
          y: false,
          drag: { x: false, y: false },
          points: {
            size: 10,
            width: 2,
            stroke: () => theme.surface,
            fill: (plot, index) => series[index - 1].stroke,
          },
        },
        scales: { x: { time: true } },
        axes: [
          { ...axis, incrs: X_STEPS, values: X_LABELS },
          { ...axis, size: 52, values: (plot, splits) => splits.map((value) => `${Number(value.toFixed(2))}%`) },
        ],
        series: [{}, ...series.map((entry) => ({ spanGaps: false, points: { show: false }, ...entry }))],
        bands,
        hooks: { draw: [drawMarker], setCursor: [followPointer], setSize: [() => onLayout?.()] },
      },
      data,
      host,
    );
    if (range) chart.setScale("x", range);
  }

  return {
    setData(next) {
      data = next;
      if (!chart) {
        build();
        return;
      }
      chart.setData(data);
      if (range) chart.setScale("x", range);
    },
    setRange(min, max) {
      range = { min, max };
      if (chart) chart.setScale("x", range);
    },
    setMarker(next) {
      marker = next;
      if (chart) chart.redraw(false);
    },
    /** Rebuilds the chart for a new width or a new colour scheme. */
    rebuild: build,
    /** The plot area inside the host, in CSS pixels: used to line a slider up with the x-axis. */
    plotBox() {
      return chart ? { left: chart.over.offsetLeft, width: chart.over.offsetWidth } : null;
    },
  };
}

/** A fresh SVG for the host. Whatever its tooltip said belonged to the drawing this one replaces. */
function frame(host, label, height) {
  host.querySelector("svg")?.remove();
  tipFor(host).hide();
  const width = host.clientWidth;
  const root = svg("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "img", "aria-label": label });
  host.prepend(root);
  return { root, width };
}

function watch(target, host, show) {
  const tip = tipFor(host);
  target.addEventListener("pointerenter", show);
  target.addEventListener("focus", show);
  target.addEventListener("pointerleave", () => tip.hide());
  target.addEventListener("blur", () => tip.hide());
}

/**
 * The yield curve on one date.
 *
 * `tenors` is every tenor in the data, so the axis stays put from date to date; `points` are
 * the tenors published that day; `selected` is a tenor index; `onPick(index)` is called when a
 * point is clicked or chosen with the keyboard. Returns the x of the first and last tenor in
 * CSS pixels, so the slider underneath can line up with them.
 */
export function drawCurve(host, { tenors, points, mode, selected, title, onPick }) {
  const { height, left, right, top, bottom } = CURVE;
  // A redraw replaces every node, so note which point has the focus and give it back afterwards.
  const focused = host.contains(document.activeElement) ? document.activeElement.dataset.tenor : undefined;
  const { root, width } = frame(host, title, height);
  const tip = tipFor(host);
  const plotWidth = width - left - right;
  const baseline = height - bottom;
  const xs = tenorPositions(tenors, mode).map((share) => left + share * plotWidth);
  const span = { first: xs[0], last: xs[xs.length - 1] };

  if (points.length === 0) {
    root.append(svg("text", { x: width / 2, y: height / 2, class: "tick", "text-anchor": "middle" }, "No yields were published on this date."));
    return span;
  }

  const ticks = niceTicks(Math.min(...points.map((p) => p.value)), Math.max(...points.map((p) => p.value)));
  const low = ticks[0];
  const high = ticks[ticks.length - 1];
  const y = (value) => top + (1 - (value - low) / (high - low)) * (baseline - top);

  for (const tick of ticks) {
    root.append(svg("line", { x1: left, x2: width - right, y1: y(tick), y2: y(tick), class: "grid" }));
    root.append(svg("text", { x: left - 8, y: y(tick) + 4, class: "tick", "text-anchor": "end" }, `${tick}%`));
  }
  root.append(svg("line", { x1: left, x2: width - right, y1: baseline, y2: baseline, class: "axis" }));
  xs.forEach((x) => root.append(svg("line", { x1: x, x2: x, y1: baseline, y2: baseline + 4, class: "axis" })));

  for (const index of labelsThatFit(xs, LABEL_GAP[mode], tenorLabelOrder(tenors))) {
    root.append(svg("text", { x: xs[index], y: baseline + 20, class: "tick", "text-anchor": "middle" }, tenors[index].label));
  }

  const path = points.map((point, order) => `${order === 0 ? "M" : "L"}${xs[point.index].toFixed(1)} ${y(point.value).toFixed(1)}`).join(" ");
  root.append(svg("path", { d: path, class: "line" }));

  for (const point of points) {
    const chosen = point.index === selected;
    const x = xs[point.index];
    const cy = y(point.value);
    root.append(svg("circle", { cx: x, cy, r: chosen ? 6 : 4, class: chosen ? "dot is-selected" : "dot" }));
    if (chosen) {
      const anchor = x > width - 60 ? "end" : x < left + 30 ? "start" : "middle";
      root.append(svg("text", { x, y: cy - 12, class: "point-label", "text-anchor": anchor }, formatPercent(point.value)));
    }
  }
  // Hit targets go on top, and are much larger than the dots they stand for.
  for (const point of points) {
    const x = xs[point.index];
    const cy = y(point.value);
    const hit = svg("circle", {
      cx: x, cy, r: 12, class: "hit pick", tabindex: 0, role: "button", "data-tenor": point.index,
      "aria-pressed": point.index === selected, "aria-label": `${point.label}: ${formatPercent(point.value)}`,
    });
    watch(hit, host, () => tip.show(point.label, [{ key: "line series-1", value: formatPercent(point.value), label: "yield" }], x, Math.max(0, cy - 44)));
    hit.addEventListener("click", () => onPick(point.index));
    hit.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      onPick(point.index);
    });
    root.append(hit);
  }
  if (focused !== undefined) root.querySelector(`[data-tenor="${focused}"]`)?.focus();
  return span;
}

/**
 * Probability by target range as columns: one colour, the value on the cap, the current range
 * named in words. Where a range will not fit under its column on one line, it is written on two.
 */
export function drawOdds(host, { outcomes, current, title }) {
  const { plot, left, right, top, column, oneLine } = ODDS;
  const slot = (host.clientWidth - left - right) / outcomes.length;
  const stacked = slot < oneLine;
  const baseline = top + plot;
  const { root, width } = frame(host, title, baseline + (stacked ? 60 : 46));
  const tip = tipFor(host);
  const y = (percent) => top + (1 - percent / 100) * plot;
  const thick = Math.min(column, slot - 2);

  for (const tick of [0, 25, 50, 75, 100]) {
    root.append(svg("line", { x1: left, x2: width - right, y1: y(tick), y2: y(tick), class: tick === 0 ? "axis" : "grid" }));
    root.append(svg("text", { x: left - 8, y: y(tick) + 4, class: "tick", "text-anchor": "end" }, `${tick}%`));
  }

  outcomes.forEach((outcome, index) => {
    const centre = left + slot * (index + 0.5);
    const value = outcome.now ?? 0;
    const cap = y(value);
    const radius = Math.min(4, baseline - cap);
    const x0 = centre - thick / 2;
    const x1 = centre + thick / 2;
    if (value > 0) {
      const d = `M${x0} ${baseline} V${cap + radius} Q${x0} ${cap} ${x0 + radius} ${cap} H${x1 - radius} Q${x1} ${cap} ${x1} ${cap + radius} V${baseline} Z`;
      root.append(svg("path", { d, class: "column" }));
    }
    const low = outcome.range[0].toFixed(2);
    const high = outcome.range[1].toFixed(2);
    const range = `${low}–${high}`;
    const isCurrent = outcome.range[0] === current[0];
    const lines = stacked ? [`${low}–`, high] : [range];
    root.append(svg("text", { x: centre, y: cap - 8, class: "point-label", "text-anchor": "middle" }, formatPercent(outcome.now, 1)));
    lines.forEach((line, row) => {
      root.append(svg("text", { x: centre, y: baseline + 18 + 15 * row, class: "tick strong", "text-anchor": "middle" }, line));
    });
    if (isCurrent) root.append(svg("text", { x: centre, y: baseline + 19 + 15 * lines.length, class: "tick", "text-anchor": "middle" }, "current"));
    const label = `${range}%${isCurrent ? ", the current range" : ""}: ${formatPercent(outcome.now, 1)}`;
    const hit = svg("rect", { x: centre - slot / 2, y: top, width: slot, height: plot, class: "hit", tabindex: 0, role: "img", "aria-label": label });
    // Beside the column and clear of its value label, whatever the column's height.
    watch(hit, host, () => tip.show(`${range}%`, [{ key: "line series-1", value: formatPercent(outcome.now, 1), label: isCurrent ? "current range" : "probability" }], centre, top + 8, thick / 2 + 10));
    root.append(hit);
  });
}
```

**File: `site/app.js`**

```javascript
// The page: loads data.json once, keeps the few choices a visitor makes, and redraws.
import * as lib from "./lib.js?v={{BUILD_ID}}";
import { drawCurve, drawOdds, timeChart } from "./charts.js?v={{BUILD_ID}}";

const THUMB = 16; // the slider thumb's width in CSS pixels; style.css sets the same size
const COLUMN_NAMES = { now: "Now", d1: "1 day", w1: "1 week", m1: "1 month" };
const $ = (id) => document.getElementById(id);

const state = { preset: "10Y", range: null, dateIndex: 0, tenorIndex: 0, mode: "even" };
let data;
let yieldSeconds;
let historyChart;
let fedChart;
let lastWidth = 0;

function make(tag, text = null, className = null) {
  const node = document.createElement(tag);
  if (text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function press(group, attribute, value) {
  for (const button of group.querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.dataset[attribute] === value));
  }
}

/** Lines a slider's travel up with a stretch of the chart above it. */
function placeSlider(slider, left, width) {
  slider.style.marginLeft = `${left - THUMB / 2}px`;
  slider.style.width = `${width + THUMB}px`;
}

function renderHeader() {
  const when = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(data.generated_at));
  const age = lib.ageInDays(data.generated_at, Date.now());
  $("refreshed").textContent = age > 3 ? `Refreshed ${when}. The data is ${age} days old.` : `Refreshed ${when}`;
  if (data.analysis) {
    const link = $("explain");
    link.href = `${data.analysis.file}?v=${encodeURIComponent(data.snapshot_id)}`;
    link.hidden = false;
    $("explain-note").textContent = `AI-written analysis of this data · ${lib.formatDate(data.analysis.generated_at.slice(0, 10))}`;
    const notice = $("ai-notice");
    notice.textContent = `The analysis was written by an AI model (${data.analysis.model}) from the data on this page. It can be wrong. Not investment advice.`;
    notice.hidden = false;
  } else {
    $("explain-off").hidden = false;
    $("explain-note").textContent = "No analysis for this snapshot yet";
  }
}

function renderFed(iso) {
  const fed = data.fed_funds;
  const index = lib.indexOnOrBefore(fed.dates, iso);
  if (index < 0) {
    $("fed-readout").textContent = `No data before ${lib.formatDate(fed.dates[0])}`;
    fedChart.setMarker({ x: lib.dateToSeconds(iso), y: null });
    return;
  }
  const lower = fed.target_lower[index];
  const upper = fed.target_upper[index];
  const target = lower === upper ? lib.formatPercent(lower) : lib.formatRange([lower, upper]);
  $("fed-readout").textContent = `${lib.formatDate(fed.dates[index])} · EFFR ${lib.formatPercent(fed.effr[index])} · target ${target}`;
  fedChart.setMarker({ x: lib.dateToSeconds(iso), y: fed.dates[index] === iso ? fed.effr[index] : null });
}

function renderCurve() {
  const yields = data.yields;
  const day = lib.formatDate(yields.dates[state.dateIndex]);
  const points = lib.curveOn(yields, state.dateIndex);
  const title = `Yield curve on ${day}`;
  $("curve-title").textContent = title;
  const chosen = points.find((point) => point.index === state.tenorIndex);
  const label = yields.tenors[state.tenorIndex].label;
  $("curve-readout").textContent = chosen ? `${label} · ${lib.formatPercent(chosen.value)}` : `${label} was not published on this date`;
  const span = drawCurve($("curve-chart"), { tenors: yields.tenors, points, mode: state.mode, selected: state.tenorIndex, title, onPick: pickTenor });
  placeSlider($("tenor-slider"), span.first, span.last - span.first);
  const rows = points.map((point) => {
    const row = make("tr");
    row.append(make("th", point.label), make("td", lib.formatPercent(point.value)));
    row.firstChild.scope = "row";
    return row;
  });
  $("curve-table").tBodies[0].replaceChildren(...rows);
}

function renderDate() {
  const yields = data.yields;
  const iso = yields.dates[state.dateIndex];
  const value = yields.values[state.tenorIndex][state.dateIndex];
  const label = yields.tenors[state.tenorIndex].label;
  $("date-slider").setAttribute("aria-valuetext", lib.formatDate(iso));
  $("history-readout").textContent =
    value === null ? `${lib.formatDate(iso)} · ${label} was not published` : `${lib.formatDate(iso)} · ${lib.formatPercent(value)}`;
  historyChart.setMarker({ x: yieldSeconds[state.dateIndex], y: value });
  renderCurve();
  renderFed(iso);
}

function renderTenor() {
  const tenor = data.yields.tenors[state.tenorIndex];
  $("history-title").textContent = `${lib.tenorName(tenor.label)} Treasury yield`;
  const slider = $("tenor-slider");
  slider.value = String(state.tenorIndex);
  slider.setAttribute("aria-valuetext", tenor.label);
  historyChart.setData([yieldSeconds, data.yields.values[state.tenorIndex]]);
}

function pickTenor(index) {
  state.tenorIndex = index;
  renderTenor();
  renderDate();
}

function alignDateSlider() {
  const box = historyChart.plotBox();
  if (box) placeSlider($("date-slider"), box.left, box.width);
}

function applyRange(range) {
  const dates = data.yields.dates;
  state.range = range;
  $("from").value = range.from;
  $("to").value = range.to;
  press($("presets"), "preset", state.preset);
  const fallback = Math.max(0, lib.indexOnOrBefore(dates, range.to));
  const span = lib.visibleSpan(dates, range.from, range.to) ?? { first: fallback, last: fallback };
  state.dateIndex = lib.clampIndex(state.dateIndex, span);
  const slider = $("date-slider");
  slider.min = String(span.first);
  slider.max = String(span.last);
  slider.value = String(state.dateIndex);
  const min = lib.dateToSeconds(range.from);
  const max = lib.dateToSeconds(range.to);
  historyChart.setRange(min, max);
  fedChart.setRange(min, max);
  renderDate();
}

function setMode(mode) {
  state.mode = mode;
  press($("modes"), "mode", mode);
  const locked = mode === "scale";
  const wrap = $("tenor-slider-wrap");
  $("tenor-slider").disabled = locked;
  wrap.classList.toggle("is-locked", locked);
  if (locked) wrap.setAttribute("tabindex", "0");
  else wrap.removeAttribute("tabindex");
}

function drawOddsChart() {
  const odds = data.odds;
  const title = `Odds for the ${lib.formatDate(odds.meeting)} decision, by target range`;
  drawOdds($("odds-chart"), { outcomes: odds.outcomes, current: odds.current_range, title });
}

function renderOdds() {
  const odds = data.odds;
  $("odds-title").textContent = `Odds for the ${lib.formatDate(odds.meeting)} decision`;
  $("odds-readout").textContent = `Current range ${lib.formatRange(odds.current_range)} · priced on ${lib.formatDate(odds.priced_on)}`;

  const tiles = [["Cut", odds.summary.cut], ["Hold", odds.summary.hold], ["Hike", odds.summary.hike]].map(([name, value]) => {
    const tile = make("div", null, "tile");
    tile.append(make("span", name, "label"), make("span", lib.formatPercent(value, 1), "value"));
    return tile;
  });
  $("odds-tiles").replaceChildren(...tiles);

  drawOddsChart();

  const head = make("tr");
  head.append(make("th", "Target range"));
  head.firstChild.scope = "col";
  for (const column of odds.columns) {
    const cell = make("th", COLUMN_NAMES[column.key]);
    cell.scope = "col";
    cell.append(make("span", column.date ? lib.formatDayMonth(column.date) : "no data", "sub"));
    head.append(cell);
  }
  $("odds-table").tHead.replaceChildren(head);
  const rows = odds.outcomes.map((outcome) => {
    const row = make("tr");
    const name = make("th", lib.formatRange(outcome.range));
    name.scope = "row";
    if (outcome.range[0] === odds.current_range[0]) name.append(make("span", "current", "sub"));
    row.append(name);
    for (const column of odds.columns) row.append(make("td", lib.formatPercent(outcome[column.key], 1)));
    return row;
  });
  $("odds-table").tBodies[0].replaceChildren(...rows);
}

function renderClock() {
  const now = Date.now();
  const meeting = lib.nextMeeting(data.fomc.meetings, now);
  if (!meeting) {
    $("countdown").textContent = "–";
    $("countdown-when").textContent = "No upcoming meeting is listed.";
  } else {
    const { days, hours, minutes } = lib.countdownParts(now, meeting.statement_at);
    $("countdown").textContent = `${days}d ${String(hours).padStart(2, "0")}h ${String(minutes).padStart(2, "0")}m`;
    // The same instant twice: in New York, and where the visitor is, which can be the next day.
    const at = new Date(meeting.statement_at);
    const parts = { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", hour12: true };
    const newYork = new Intl.DateTimeFormat("en-GB", { ...parts, timeZone: "America/New_York" }).format(at);
    const local = new Intl.DateTimeFormat(undefined, { ...parts, timeZoneName: "short" }).format(at);
    $("countdown-when").textContent = `${newYork} in New York · ${local} your time`;
  }
  const outdated = $("odds-outdated");
  outdated.hidden = !lib.oddsAreOutdated(data.odds, data.fomc.meetings, now);
  outdated.textContent = `These odds were calculated before the ${lib.formatDate(data.odds.meeting)} decision.`;
}

/** After a change of width or colour scheme. The history chart realigns its own slider. */
function redraw() {
  historyChart.rebuild();
  fedChart.rebuild();
  renderCurve();
  drawOddsChart();
}

function start(loaded) {
  data = loaded;
  const yields = data.yields;
  const fed = data.fed_funds;
  const first = yields.dates[0];
  const last = yields.dates[yields.dates.length - 1];
  yieldSeconds = yields.dates.map(lib.dateToSeconds);
  const tenYear = yields.tenors.findIndex((tenor) => tenor.label === "10Y");
  state.tenorIndex = tenYear >= 0 ? tenYear : yields.tenors.length - 1;
  state.dateIndex = yields.dates.length - 1;

  $("page").hidden = false;
  $("notices").hidden = false;
  lastWidth = $("page").clientWidth;

  const tenorSlider = $("tenor-slider");
  tenorSlider.min = "0";
  tenorSlider.max = String(yields.tenors.length - 1);
  for (const id of ["from", "to"]) {
    $(id).min = first;
    $(id).max = last;
  }

  historyChart = timeChart(
    $("history-chart"),
    (theme) => ({ series: [{ stroke: theme.series1, width: 2 }] }),
    (index) => ({
      title: lib.formatDate(yields.dates[index]),
      rows: [{ key: "line series-1", value: lib.formatPercent(yields.values[state.tenorIndex][index]), label: yields.tenors[state.tenorIndex].label }],
    }),
    alignDateSlider,
  );
  fedChart = timeChart(
    $("fed-chart"),
    (theme) => ({
      series: [{ stroke: theme.series1, width: 2 }, { stroke: theme.series2, width: 1 }, { stroke: theme.series2, width: 1 }],
      bands: [{ series: [2, 3], fill: theme.wash2 }],
    }),
    (index) => {
      const lower = fed.target_lower[index];
      const upper = fed.target_upper[index];
      return {
        title: lib.formatDate(fed.dates[index]),
        rows: [
          { key: "line series-1", value: lib.formatPercent(fed.effr[index]), label: "EFFR" },
          { key: "line series-2", value: lower === upper ? lib.formatPercent(lower) : lib.formatRange([lower, upper]), label: "target" },
        ],
      };
    },
  );
  fedChart.setData([fed.dates.map(lib.dateToSeconds), fed.effr, fed.target_upper, fed.target_lower]);

  renderHeader();
  setMode("even");
  renderTenor();
  applyRange(lib.presetRange(state.preset, first, last));
  renderOdds();
  renderClock();
  setInterval(renderClock, 30000);

  if (lib.publishedTargetLags(fed, data.odds)) {
    const note = $("fed-lag");
    note.textContent = `The Fed has moved the target range to ${lib.formatRange(data.odds.current_range)}. The published series shown here catches up within a day or two.`;
    note.hidden = false;
  }

  $("presets").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    state.preset = button.dataset.preset;
    applyRange(lib.presetRange(state.preset, first, last));
  });
  for (const id of ["from", "to"]) {
    $(id).addEventListener("change", () => {
      const range = lib.customRange($("from").value, $("to").value, first, last);
      if (!range) {
        // Not a usable range: put back the one in force.
        $("from").value = state.range.from;
        $("to").value = state.range.to;
        return;
      }
      state.preset = null;
      applyRange(range);
    });
  }
  $("date-slider").addEventListener("input", (event) => {
    state.dateIndex = Number(event.target.value);
    renderDate();
  });
  tenorSlider.addEventListener("input", (event) => pickTenor(Number(event.target.value)));
  $("modes").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    setMode(button.dataset.mode);
    renderCurve();
  });

  let pending = 0;
  new ResizeObserver(() => {
    const width = $("page").clientWidth;
    if (width === lastWidth) return;
    lastWidth = width;
    cancelAnimationFrame(pending);
    pending = requestAnimationFrame(redraw);
  }).observe($("page"));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw);
}

async function main() {
  const response = await fetch("data.json", { cache: "no-cache" });
  if (!response.ok) throw new Error(`data.json answered ${response.status}`);
  start(await response.json());
}

main().catch((error) => {
  const note = $("load-error");
  note.textContent = `The data could not be loaded (${error.message}). Try again in a minute.`;
  note.hidden = false;
});
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_site_page.py`

Expected: `6 passed`

- [ ] **Step 5: Check the scripts parse, and run the whole suite**

Run:

```bash
node --check site/lib.js && node --check site/charts.js && node --check site/app.js && echo "scripts parse"
.venv/bin/python -m pytest
```

Expected: `scripts parse`, then `242 passed`.

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `tests/test_site_page.py` and the four files in `site/`. Suggested message: `feat: the page, with linked yield charts, rate odds and the Fed funds chart`.

---

### Task 5: Try it

This task runs the real commands. It adds no code. The refresh makes six read-only requests: the current Treasury year, the New York Fed and four futures contracts.

- [ ] **Step 1: Build**

Run: `.venv/bin/python -m macro refresh`

Expected: the five summary lines, ending `Built dist/ (no analysis yet) and work/facts.json`.

- [ ] **Step 2: Start the preview in one terminal**

Run: `.venv/bin/python -m macro preview`

Expected: `serving .../dist on http://127.0.0.1:8081/`, and it keeps running.

- [ ] **Step 3: Check the answers from a second terminal**

Run:

```bash
for p in / /style.css /app.js /charts.js /lib.js /vendor/uPlot.iife.min.js /vendor/uPlot.min.css /vendor/uPlot-LICENSE.txt /data.json /manifest.json; do
  printf "%-28s " "$p"
  curl -s -o /dev/null -w "%{http_code} %{content_type}\n" "http://127.0.0.1:8081$p"
done
curl -s http://127.0.0.1:8081/ | grep -oE '(href|src)="[^"]+"'
curl -s http://127.0.0.1:8081/app.js http://127.0.0.1:8081/charts.js | grep '^import'
curl -s -o /dev/null -w "%header{cache-control}\n" "http://127.0.0.1:8081/lib.js?v=1"
```

Expected:

- Every address answers 200 except `/manifest.json`, which answers 404.
- The page lists five addresses: the empty icon `data:,` and four files, each ending `?v=` and the snapshot id.
- The three `import` lines end `?v=` and the same snapshot id. None still says `{{BUILD_ID}}`.
- The last line is `public, max-age=31536000, immutable`.

- [ ] **Step 4: Look at it**

Open `http://127.0.0.1:8081/` in a browser, with the developer console open. Check each of these:

| Try | Expect |
|---|---|
| Load the page | No errors in the console. Four charts, the countdown and the odds table |
| The range buttons and the two date inputs | Both history charts change their time axis together |
| Drag the date slider | The marker follows on both history charts, the curve and its title change, and the thumb stays under the marker from one end of the plot to the other |
| Drag the tenor slider | The history title and line change, and the thumb stays under the highlighted point |
| Press "True scale" | The curve takes its real shape. The tenor slider greys out and shows "Switch to even spacing to pick a tenor" when the pointer is on it. Clicking a point on the curve still picks that tenor |
| Hover each chart | A tooltip with the date or label first, then each value |
| "Show table" | The tenors and yields for the selected date |
| The header | "Explain Macros" is greyed out, beside "No analysis for this snapshot yet" |
| Switch the system between light and dark | The page follows, charts included |
| Narrow the window to phone width | One column, and nothing scrolls sideways |

The first terminal shows one line per request, such as `GET /app.js 200`, and nothing else.

- [ ] **Step 5: Stop the preview**

Press Ctrl-C in the first terminal.

- [ ] **Step 6: Checkpoint**

Stop and report what the owner saw. Nothing new to commit.
