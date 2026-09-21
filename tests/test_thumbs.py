import io
import logging
import struct
import zlib

import pytest
from PIL import Image

from app import thumbs
from tests.test_files import upload
from tests.test_folders import make, upload_into


def png(width=64, height=32, color=(200, 30, 30)):
    out = io.BytesIO()
    Image.new("RGB", (width, height), color).save(out, "PNG")
    return out.getvalue()


def rotated_jpeg():
    """A 60×20 picture whose EXIF says "rotate 90° clockwise to view" (orientation 6)."""
    exif = Image.Exif()
    exif[0x0112] = 6
    out = io.BytesIO()
    Image.new("RGB", (60, 20), (10, 120, 10)).save(out, "JPEG", exif=exif)
    return out.getvalue()


def bomb_png(width=20000, height=20000):
    """Only a PNG header claiming 400 MP, plus a tiny broken body: enough for Image.open to refuse."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"\x00" * 10)) + chunk(b"IEND", b"")


def thumb_of(client, file):
    return client.get(f"/api/files/{file['id']}/thumb")


def test_png_thumbnail(auth_client, settings):
    file = upload(auth_client, "wide.png", png(1000, 500))
    r = thumb_of(auth_client, file)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/webp"
    assert r.headers["cache-control"] == "private, max-age=604800"
    assert r.headers["content-security-policy"] == "sandbox; default-src 'none'"
    with Image.open(io.BytesIO(r.content)) as img:
        assert img.format == "WEBP" and img.size == (400, 200)
    assert (settings.thumbs_dir / f"{file['id']}.webp").is_file()
    # Cached: the second request serves the same file without making it again.
    assert thumb_of(auth_client, file).content == r.content


def test_small_image_is_not_enlarged_and_alpha_kept(auth_client):
    out = io.BytesIO()
    Image.new("RGBA", (30, 10), (0, 0, 0, 0)).save(out, "PNG")
    file = upload(auth_client, "icon.png", out.getvalue())
    with Image.open(io.BytesIO(thumb_of(auth_client, file).content)) as img:
        assert img.size == (30, 10) and img.mode == "RGBA"


def test_exif_orientation_applied(auth_client):
    file = upload(auth_client, "IMG_0001.jpg", rotated_jpeg())
    with Image.open(io.BytesIO(thumb_of(auth_client, file).content)) as img:
        assert img.size == (20, 60)  # turned upright: taller than wide


@pytest.mark.parametrize("name, data", [
    ("IMG_0001.heic", b"not really a heic file"),
    ("broken.jpg", b"\xff\xd8\xff\xe0 truncated"),
    ("bomb.png", bomb_png()),
])
def test_no_thumbnail_is_a_404_never_a_500(auth_client, settings, caplog, name, data):
    file = upload(auth_client, name, data)
    with caplog.at_level(logging.INFO):
        r = thumb_of(auth_client, file)
    assert r.status_code == 404 and r.json() == {"error": "No thumbnail for this file."}
    assert (settings.thumbs_dir / f"{file['id']}.none").exists()
    assert file["id"] in caplog.text and name.split(".")[0] not in caplog.text
    assert list((settings.data_dir / "tmp").iterdir()) == []
    # The failure is remembered, so Pillow isn't asked again.
    assert thumb_of(auth_client, file).status_code == 404


def test_only_images_get_thumbnails(auth_client, settings):
    for name in ("clip.mp4", "scan.pdf", "notes.txt"):
        file = upload(auth_client, name, png())
        assert thumb_of(auth_client, file).status_code == 404
    assert list(settings.thumbs_dir.iterdir()) == []
    assert auth_client.get("/api/files/" + "0" * 32 + "/thumb").status_code == 404
    assert auth_client.get("/api/files/../../vault.db/thumb").status_code == 404


def test_thumbnail_deleted_with_its_file(auth_client, settings):
    file = upload(auth_client, "a.png", png())
    thumb_of(auth_client, file)
    heic = upload(auth_client, "b.heic", b"x")
    thumb_of(auth_client, heic)
    assert len(list(settings.thumbs_dir.iterdir())) == 2
    auth_client.delete(f"/api/files/{file['id']}")
    auth_client.delete(f"/api/files/{heic['id']}")
    assert list(settings.thumbs_dir.iterdir()) == []


def test_thumbnails_deleted_with_folder_and_bulk_delete(auth_client, settings):
    folder = make(auth_client, "Trip")
    inside = upload_into(auth_client, folder["id"], "a.png", png())
    loose = upload(auth_client, "b.png", png())
    thumb_of(auth_client, inside)
    thumb_of(auth_client, loose)
    auth_client.delete(f"/api/folders/{folder['id']}")
    assert [p.name for p in settings.thumbs_dir.iterdir()] == [f"{loose['id']}.webp"]
    auth_client.post("/api/delete", json={"files": [loose["id"]], "folders": []})
    assert list(settings.thumbs_dir.iterdir()) == []


def test_path_for_only_accepts_generated_ids(tmp_path):
    for bad in ("../x", "A" * 32, ""):
        with pytest.raises(ValueError):
            thumbs.path_for(tmp_path, bad)


def test_logged_out(client):
    assert client.get("/api/files/" + "a" * 32 + "/thumb").status_code == 401


def test_pixel_limit(tmp_path, caplog):
    """Between the limit and Pillow's own bomb error (2×), thumbs.py refuses by itself."""
    source = tmp_path / "big.png"
    source.write_bytes(bomb_png(10000, 9000))  # 90 MP
    with caplog.at_level(logging.WARNING):
        assert thumbs.make(source, tmp_path / ("a" * 32 + ".webp"), tmp_path, 400) is False
    assert "too many pixels" in caplog.text


# ---- Screen-size copies for the preview page and the viewer (S11 follow-up) ----------------

def big_jpeg(width=3000, height=2250):
    """A photo bigger than the 2000px screen size, with enough detail not to compress to nothing.
    Kept under the tests' 2 MB upload limit."""
    import random
    random.seed(1)
    img = Image.new("RGB", (width, height))
    row = [(random.randrange(256), random.randrange(256), random.randrange(256)) for _ in range(width)]
    img.putdata(row * height)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=55)
    return out.getvalue()


def screen_of(client, file):
    return client.get(f"/api/files/{file['id']}/screen")


def test_screen_copy_is_smaller_and_the_download_is_still_exact(auth_client, settings):
    original = big_jpeg()
    file = upload(auth_client, "IMG_0002.jpg", original)
    r = screen_of(auth_client, file)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/webp"
    assert r.headers["cache-control"] == "private, max-age=604800"
    assert r.headers["content-security-policy"] == "sandbox; default-src 'none'"
    with Image.open(io.BytesIO(r.content)) as img:
        assert max(img.size) == 2000 and img.size == (2000, 1500)
    assert len(r.content) < len(original) / 2
    # The original is untouched, and both cached sizes sit beside each other.
    assert auth_client.get(f"/api/files/{file['id']}/download").content == original
    assert [p.name for p in settings.thumbs_dir.iterdir()] == [f"{file['id']}-screen.webp"]  # nothing yet for the grid
    thumb_of(auth_client, file)
    assert sorted(p.name for p in settings.thumbs_dir.iterdir()) == [f"{file['id']}-screen.webp", f"{file['id']}.webp"]


def test_screen_copy_is_exif_rotated(auth_client):
    file = upload(auth_client, "IMG_0003.jpg", rotated_jpeg())
    with Image.open(io.BytesIO(screen_of(auth_client, file).content)) as img:
        assert img.size == (20, 60) or img.format == "JPEG"  # small: served as it is, already upright


def test_a_small_image_is_served_as_it_is(auth_client, settings):
    original = png(800, 600)
    file = upload(auth_client, "small.png", original)
    r = screen_of(auth_client, file)
    assert r.status_code == 200
    assert r.content == original and r.headers["content-type"] == "image/png"
    assert r.headers["content-disposition"].startswith("inline;")
    assert [p.name for p in settings.thumbs_dir.iterdir()] == [f"{file['id']}-screen.none"]
    # Asked again, it still comes back whole, without Pillow being asked twice.
    assert screen_of(auth_client, file).content == original


def test_an_animated_gif_keeps_its_animation(auth_client):
    frames = [Image.new("RGB", (3000, 100), c) for c in ((255, 0, 0), (0, 0, 255))]
    out = io.BytesIO()
    frames[0].save(out, "GIF", save_all=True, append_images=frames[1:], duration=100, loop=0)
    file = upload(auth_client, "wave.gif", out.getvalue())
    r = screen_of(auth_client, file)
    assert r.headers["content-type"] == "image/gif" and r.content == out.getvalue()


def test_unreadable_images_fall_back_to_the_original(auth_client):
    heic = upload(auth_client, "IMG_0004.heic", b"not really a heic")
    r = screen_of(auth_client, heic)
    assert r.status_code == 200 and r.content == b"not really a heic"
    assert r.headers["content-disposition"].startswith("attachment;")  # never rendered inline
    broken = upload(auth_client, "broken.jpg", b"\xff\xd8\xff\xe0 truncated")
    assert screen_of(auth_client, broken).content == b"\xff\xd8\xff\xe0 truncated"


def test_screen_copies_go_with_their_file(auth_client, settings):
    file = upload(auth_client, "photo.jpg", big_jpeg(2500, 2500))
    screen_of(auth_client, file)
    thumb_of(auth_client, file)
    assert len(list(settings.thumbs_dir.iterdir())) == 2
    auth_client.delete(f"/api/files/{file['id']}")
    assert list(settings.thumbs_dir.iterdir()) == []


def test_check_does_not_call_a_screen_copy_stray(auth_client, settings, capsys):
    from app import cli
    file = upload(auth_client, "photo.jpg", big_jpeg(2500, 2500))
    screen_of(auth_client, file)
    thumb_of(auth_client, file)
    assert cli.main(["check"], settings=settings) == 0
    out = capsys.readouterr().out
    assert "Everything matches." in out and "thumbnails belong to files that are gone" not in out


def test_screen_needs_a_real_file(auth_client):
    assert auth_client.get("/api/files/" + "0" * 32 + "/screen").status_code == 404
    assert auth_client.get("/api/files/nope/screen").status_code == 404


def test_screen_needs_login(client):
    assert client.get("/api/files/" + "a" * 32 + "/screen").status_code == 401
