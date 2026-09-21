"""Scaled copies of images, made with Pillow on first request and cached in data/thumbs/:

    <id>.webp          400 px  — the Photos grid and the file rows        (S8)
    <id>-screen.webp  2000 px  — the preview page and the photo viewer    (S11 follow-up)

A phone photo is often 4 MB; the screen copy is a few hundred KB and still stands up to
pinch-zoom. Download and Open always serve the original bytes, untouched.

A copy that can't (or needn't) be made leaves an empty `.none` marker so the next request
doesn't try again: the grid then shows the type icon, and the preview falls back to the
original. Nothing here raises: the worst case is "no scaled copy" (TECH_PLAN §8 gotchas 3, 4;
§5 #22).
"""
import logging
import os
import threading
from pathlib import Path

from PIL import Image, ImageOps

from app import storage

log = logging.getLogger("vault.thumbs")

SIZES = {"thumb": 400, "screen": 2000}   # long side, in pixels
MAX_PIXELS = 80_000_000       # 80 MP: bigger than any phone photo, far below a pixel bomb
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

# A grid asks for 60 thumbnails at once. Two decodes at a time keeps memory flat on the
# office computer; the rest wait their turn.
_working = threading.BoundedSemaphore(2)


def path_for(thumbs_dir: Path, file_id: str, kind: str = "thumb") -> Path:
    """Same id check as storage.path_for: only a generated id ever becomes a path."""
    if not storage.ID_PATTERN.fullmatch(file_id) or kind not in SIZES:
        raise ValueError("not a file id")
    suffix = "" if kind == "thumb" else f"-{kind}"
    return thumbs_dir.resolve() / f"{file_id}{suffix}.webp"


def get(settings, file_id: str, kind: str = "thumb") -> Path | None:
    """The cached copy at this size, making it first if needed. None when there can't be one
    (or, at screen size, when the original is already the better thing to send)."""
    copy = path_for(settings.thumbs_dir, file_id, kind)
    failed = copy.with_suffix(".none")
    if copy.is_file():
        return copy
    if failed.exists():
        return None
    with _working:
        if copy.is_file():  # made by another request while this one waited
            return copy
        if make(storage.path_for(settings.files_dir, file_id), copy, settings.data_dir / "tmp", SIZES[kind],
                only_if_bigger=kind == "screen"):
            return copy
    failed.touch()
    return None


def make(source: Path, target: Path, tmp_dir: Path, size: int, only_if_bigger: bool = False) -> bool:
    """Write a WEBP copy of `source` no larger than `size` on its long side.

    `only_if_bigger` skips images that are already smaller than that, and animated GIFs, which
    would lose their animation: for those the original is what the page should show.
    """
    part = tmp_dir / f"{target.stem}.thumb"
    try:
        with Image.open(source) as img:
            if img.width * img.height > MAX_PIXELS:
                log.warning("File %s is too many pixels to scale", target.stem)
                return False
            if only_if_bigger and (max(img.width, img.height) <= size or getattr(img, "n_frames", 1) > 1):
                log.debug("File %s is served as it is", target.stem)
                return False
            img.draft("RGB", (size * 2, size * 2))  # JPEG: decode at a smaller scale, much faster
            img = ImageOps.exif_transpose(img)
            img.thumbnail((size, size))
            if img.mode not in ("RGB", "RGBA"):
                has_alpha = img.mode in ("LA", "PA") or (img.mode == "P" and "transparency" in img.info)
                img = img.convert("RGBA" if has_alpha else "RGB")
            img.save(part, "WEBP", quality=80 if size <= 400 else 82)
        os.replace(part, target)
        return True
    except Exception as exc:  # noqa: BLE001 — any failure means "no scaled copy", never a 500
        log.info("No scaled copy of file %s (%s)", target.stem, type(exc).__name__)
        part.unlink(missing_ok=True)
        return False


def remove(thumbs_dir: Path, file_id: str) -> None:
    """Every cached size of one file, and the markers that say a size can't be made."""
    for kind in SIZES:
        copy = path_for(thumbs_dir, file_id, kind)
        copy.unlink(missing_ok=True)
        copy.with_suffix(".none").unlink(missing_ok=True)
