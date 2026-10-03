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
