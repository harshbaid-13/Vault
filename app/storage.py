"""Uploaded bytes on disk: id → path, display names, types, and streaming an upload into place.

Files live at data/files/<id[:2]>/<id>, where id is a generated uuid4 hex. A user-provided name
never touches a path (CLAUDE.md).
"""
import hashlib
import logging
import os
import re
import shutil
import unicodedata
import uuid
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect, Request

from app.web import ApiError

log = logging.getLogger("vault.storage")

ID_PATTERN = re.compile(r"[0-9a-f]{32}")
BIDI_CONTROLS = set("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200e\u200f")
CHUNK = 1024 * 1024
DISK_RESERVE = 512 * 1024 * 1024  # never fill the disk to the last byte (TECH_PLAN §7)

# extension → (kind, MIME). Fixed here rather than read from the OS, so the container and a
# local run agree. Anything missing is ("other", "application/octet-stream").
TYPES = {
    "jpg": ("image", "image/jpeg"), "jpeg": ("image", "image/jpeg"), "png": ("image", "image/png"),
    "gif": ("image", "image/gif"), "webp": ("image", "image/webp"), "avif": ("image", "image/avif"),
    "bmp": ("image", "image/bmp"), "heic": ("image", "image/heic"), "heif": ("image", "image/heif"),
    "mp4": ("video", "video/mp4"), "m4v": ("video", "video/mp4"), "webm": ("video", "video/webm"),
    "mov": ("video", "video/quicktime"), "mkv": ("video", "video/x-matroska"), "avi": ("video", "video/x-msvideo"),
    "mp3": ("audio", "audio/mpeg"), "m4a": ("audio", "audio/mp4"), "aac": ("audio", "audio/aac"),
    "ogg": ("audio", "audio/ogg"), "opus": ("audio", "audio/ogg"), "wav": ("audio", "audio/wav"),
    "flac": ("audio", "audio/flac"),
    "pdf": ("pdf", "application/pdf"),
    "txt": ("text", "text/plain"), "md": ("text", "text/markdown"), "csv": ("text", "text/csv"),
    "log": ("text", "text/plain"), "json": ("text", "application/json"),
    "html": ("other", "text/html"), "htm": ("other", "text/html"), "svg": ("other", "image/svg+xml"),
    "xml": ("other", "application/xml"), "js": ("other", "text/javascript"),
    "zip": ("other", "application/zip"), "doc": ("other", "application/msword"),
    "docx": ("other", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "xls": ("other", "application/vnd.ms-excel"),
    "xlsx": ("other", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
}

# The only extensions /view serves inline, and the Content-Type they are served as (TECH_PLAN
# §5 #11). Text goes out as text/plain so a browser never runs it. Not SVG, HTML, XML or JS.
INLINE = {
    **{ext: TYPES[ext][1] for ext in ("jpg", "jpeg", "png", "gif", "webp", "avif", "bmp")},
    "pdf": "application/pdf",
    "mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime",
    **{ext: TYPES[ext][1] for ext in ("mp3", "m4a", "ogg", "wav", "flac")},
    **{ext: "text/plain; charset=utf-8" for ext in ("txt", "md", "csv", "log", "json")},
}


def extension(name: str) -> str:
    _, dot, ext = name.rpartition(".")
    return ext.lower() if dot else ""


def kind_and_mime(name: str) -> tuple[str, str]:
    return TYPES.get(extension(name), ("other", "application/octet-stream"))


def inline_type(name: str) -> str | None:
    """The Content-Type to show this file inline with, or None to force a download."""
    return INLINE.get(extension(name))


def clean_name(raw: str) -> str:
    """Display text only: the last path segment, no control characters, no leading or trailing
    spaces and dots, at most 255 characters. "unnamed" when nothing is left."""
    name = re.split(r"[/\\]", raw)[-1]
    # Control characters (incl. NUL) and the bidi overrides that make "gpj.exe" read as "exe.jpg".
    # Zero-width joiners stay: Indic scripts need them.
    name = "".join(ch for ch in name if unicodedata.category(ch) != "Cc" and ch not in BIDI_CONTROLS)
    name = name.strip(" .")
    if len(name) > 255:
        # Keep the extension when cutting a long name.
        ext = extension(name)
        keep = f".{ext}" if ext and len(ext) <= 16 else ""
        name = name[: 255 - len(keep)].rstrip(" .") + keep
    return name or "unnamed"


def new_id() -> str:
    return uuid.uuid4().hex


def path_for(files_dir: Path, file_id: str) -> Path:
    """The only way to get a file's path. Raises ValueError for anything but a generated id."""
    if not ID_PATTERN.fullmatch(file_id):
        raise ValueError("not a file id")
    root = files_dir.resolve()
    path = (root / file_id[:2] / file_id).resolve()
    if not path.is_relative_to(root):
        raise ValueError("outside the files folder")
    return path


def max_upload_text(max_mb: int) -> str:
    return f"{max_mb // 1024} GB" if max_mb % 1024 == 0 else f"{max_mb} MB"


async def receive_upload(request: Request, data_dir: Path, max_mb: int) -> tuple[str, int, str]:
    """Stream the request body into data/files/<id[:2]>/<id>. Returns (id, size, sha256).

    The body goes to tmp/<id>.part in 1 MB writes, counted and hashed on the way; any failure
    removes the part file. Only a complete body is moved into place (atomic, same filesystem).
    The caller inserts the row, and calls remove() if that fails.
    """
    too_large = ApiError(f"Too large (max {max_upload_text(max_mb)})", 413)
    limit = max_mb * 1024 * 1024
    try:
        expected = int(request.headers["content-length"])
    except (KeyError, ValueError):
        raise ApiError("The upload didn't say how big it is. Try again.", 411) from None
    if expected > limit:
        raise too_large
    if shutil.disk_usage(data_dir).free < expected + DISK_RESERVE:
        raise ApiError("Vault disk full", 507)

    file_id = new_id()
    part = data_dir / "tmp" / f"{file_id}.part"
    hasher = hashlib.sha256()
    received = 0
    buffer = bytearray()
    try:
        with open(part, "wb") as out:
            async for chunk in request.stream():
                received += len(chunk)
                if received > expected or received > limit:
                    raise too_large
                hasher.update(chunk)
                buffer += chunk
                if len(buffer) >= CHUNK:
                    await run_in_threadpool(out.write, bytes(buffer))
                    buffer.clear()
            if received != expected:
                raise ApiError("Connection lost", 400)
            await run_in_threadpool(_finish, out, bytes(buffer))
        target = path_for(data_dir / "files", file_id)
        target.parent.mkdir(exist_ok=True)
        os.replace(part, target)
    except ClientDisconnect:
        raise ApiError("Connection lost", 400) from None
    finally:
        part.unlink(missing_ok=True)
    return file_id, received, hasher.hexdigest()


def _finish(out, rest: bytes) -> None:
    out.write(rest)
    out.flush()
    os.fsync(out.fileno())


def remove(files_dir: Path, file_id: str) -> None:
    """Delete a file's bytes. A file already missing is logged by id only."""
    try:
        path_for(files_dir, file_id).unlink()
    except FileNotFoundError:
        log.warning("File %s was already missing from disk", file_id)
