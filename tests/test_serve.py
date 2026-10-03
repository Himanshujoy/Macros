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


def test_a_silent_connection_is_closed(release):
    server = Running(serve.DiskSite(release), idle_timeout=0.3)
    try:
        started = time.monotonic()
        assert server.raw(b"", wait=3.0) == b""
        assert time.monotonic() - started < 2.5
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
