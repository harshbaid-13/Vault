"""Image thumbnails: made with Pillow on first request, cached as data/thumbs/<id>.webp (S8).

A thumbnail that can't be made (HEIC, a corrupt file, a pixel bomb) leaves an empty
<id>.none marker so the next request doesn't try again, and the page shows the type icon.
Nothing here raises: the worst case is "no thumbnail" (TECH_PLAN §8 gotchas 3, 4; §5 #22).
"""
import logging
import os
import threading
from pathlib import Path

from PIL import Image, ImageOps

from app import storage

log = logging.getLogger("vault.thumbs")

SIZE = 400                    # long side, in pixels
MAX_PIXELS = 80_000_000       # 80 MP: bigger than any phone photo, far below a pixel bomb
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

# A grid asks for 60 thumbnails at once. Two decodes at a time keeps memory flat on the
# office computer; the rest wait their turn.
_working = threading.BoundedSemaphore(2)


def path_for(thumbs_dir: Path, file_id: str) -> Path:
    """Same id check as storage.path_for: only a generated id ever becomes a path."""
    if not storage.ID_PATTERN.fullmatch(file_id):
        raise ValueError("not a file id")
    return thumbs_dir.resolve() / f"{file_id}.webp"


def get(settings, file_id: str) -> Path | None:
    """The cached thumbnail for an image file, making it first if needed. None if there can't be one."""
    thumb = path_for(settings.thumbs_dir, file_id)
    failed = thumb.with_suffix(".none")
    if thumb.is_file():
        return thumb
    if failed.exists():
        return None
    with _working:
        if thumb.is_file():  # made by another request while this one waited
            return thumb
        if make(storage.path_for(settings.files_dir, file_id), thumb, settings.data_dir / "tmp"):
            return thumb
    failed.touch()
    return None


def make(source: Path, target: Path, tmp_dir: Path) -> bool:
    part = tmp_dir / f"{target.stem}.thumb"
    try:
        with Image.open(source) as img:
            if img.width * img.height > MAX_PIXELS:
                log.warning("File %s is too many pixels for a thumbnail", target.stem)
                return False
            img.draft("RGB", (SIZE * 2, SIZE * 2))  # JPEG: decode at a smaller scale, much faster
            img = ImageOps.exif_transpose(img)
            img.thumbnail((SIZE, SIZE))
            if img.mode not in ("RGB", "RGBA"):
                has_alpha = img.mode in ("LA", "PA") or (img.mode == "P" and "transparency" in img.info)
                img = img.convert("RGBA" if has_alpha else "RGB")
            img.save(part, "WEBP", quality=80)
        os.replace(part, target)
        return True
    except Exception as exc:  # noqa: BLE001 — any failure means "no thumbnail", never a 500
        log.info("No thumbnail for file %s (%s)", target.stem, type(exc).__name__)
        part.unlink(missing_ok=True)
        return False


def remove(thumbs_dir: Path, file_id: str) -> None:
    thumb = path_for(thumbs_dir, file_id)
    thumb.unlink(missing_ok=True)
    thumb.with_suffix(".none").unlink(missing_ok=True)
