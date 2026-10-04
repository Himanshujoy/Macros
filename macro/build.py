"""Writes dist/: the page files, data.json, the analysis PDF, and a manifest and checksum list of it all."""
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
ANALYSIS_FILES = "analysis-*.pdf"  # an analysis PDF is named after its own checksum


def write_manifest(dist: Path, snapshot_id: str) -> None:
    """Lists every file the server may serve. Rerun it after adding a file to dist/."""
    files: dict[str, dict] = {}
    for path in sorted(item for item in dist.rglob("*") if item.is_file()):
        inside = path.relative_to(dist)
        name = inside.as_posix()
        if name in INTERNAL or any(part.startswith(".") for part in inside.parts):
            continue  # the manifest and checksum list themselves, and hidden files such as .DS_Store
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


def work_folders(dist: Path) -> tuple[Path, Path]:
    """The folder to build in and the folder the old dist/ is parked in, both made ready for a new run."""
    staging = dist.with_name(dist.name + ".tmp")
    previous = dist.with_name(dist.name + ".old")
    if previous.exists() and not dist.exists():
        previous.rename(dist)  # an earlier run stopped between the two renames: put the old folder back
    for leftover in (staging, previous):
        if leftover.exists():
            shutil.rmtree(leftover)
    return staging, previous


def swap_in(staging: Path, dist: Path, previous: Path) -> None:
    """Two renames, so dist/ is never missing for longer than the gap between them."""
    if dist.exists():
        dist.rename(previous)
    try:
        staging.rename(dist)
    except OSError:
        if previous.exists():
            previous.rename(dist)
        raise
    shutil.rmtree(previous, ignore_errors=True)


def as_json(snapshot: dict) -> str:
    try:
        return json.dumps(snapshot, separators=(",", ":"), allow_nan=False)
    except ValueError as exc:
        raise BuildError(f"build: the data cannot be written as JSON: {exc}") from None


def build_dist(dist: Path, site: Path, snapshot: dict) -> None:
    """Builds in a temporary folder and swaps it in, so a failure leaves the old dist/ in place."""
    staging, previous = work_folders(dist)
    if site.is_dir():
        shutil.copytree(site, staging, ignore=shutil.ignore_patterns(".*"))
    else:
        staging.mkdir(parents=True)
    (staging / "data.json").write_text(as_json(snapshot), encoding="utf-8")
    build_id = str(snapshot.get("build_id", snapshot["snapshot_id"]))
    for pattern in STAMPED:
        for path in staging.glob(pattern):
            text = path.read_text(encoding="utf-8")
            if BUILD_ID_MARK in text:
                path.write_text(text.replace(BUILD_ID_MARK, build_id), encoding="utf-8")
    write_manifest(staging, snapshot["snapshot_id"])
    swap_in(staging, dist, previous)


def add_analysis(dist: Path, pdf: bytes, model: str, generated_at: str) -> str:
    """Puts the analysis PDF into dist/ and records it in data.json. Returns the PDF's file name.

    The name holds the start of the PDF's checksum. A rewritten analysis therefore gets a new
    address, and no browser shows an old copy it has cached. The work is done on a copy of dist/
    that is swapped in at the end, so a failure leaves dist/ as it was.
    """
    staging, previous = work_folders(dist)
    try:
        snapshot = json.loads((dist / "data.json").read_text(encoding="utf-8"))
        snapshot_id = snapshot["snapshot_id"]
    except (OSError, ValueError, KeyError, TypeError):
        raise BuildError("build: dist/ holds no snapshot to add an analysis to. Run refresh first") from None
    shutil.copytree(dist, staging, ignore=shutil.ignore_patterns(".*"))
    for earlier in staging.glob(ANALYSIS_FILES):
        earlier.unlink()
    name = f"analysis-{hashlib.sha256(pdf).hexdigest()[:12]}.pdf"
    (staging / name).write_bytes(pdf)
    snapshot["analysis"] = {"file": name, "model": model, "generated_at": generated_at}
    (staging / "data.json").write_text(as_json(snapshot), encoding="utf-8")
    write_manifest(staging, snapshot_id)
    swap_in(staging, dist, previous)
    return name
