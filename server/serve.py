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
        self.server.log("note " + printable(format % args))


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
