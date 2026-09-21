"""Fill a throw-away vault with a lot of everything, to see how the pages hold up (S11).

    VAULT_DATA_DIR=./demo-data SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))") \
      .venv/bin/python scripts/seed_demo.py --files 2000 --notes 500

It refuses to touch a data folder that already holds a vault unless you pass --force, so it
can never land on your real one by mistake. Files get a few real bytes each, photos get a real
(tiny) JPEG so thumbnails work; everything else is generated text.
"""
import argparse
import hashlib
import io
import os
import random
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, storage  # noqa: E402
from app.config import Settings  # noqa: E402

WORDS = ("electricity bill rent insurance passport scan invoice receipt warranty lease salary "
         "tax medical prescription vaccination travel ticket booking hotel flight recipe manual "
         "router wifi bank upi ifsc aadhaar pan license vehicle photo holiday goa manali").split()
EXTENSIONS = [("jpg", 25), ("png", 10), ("pdf", 25), ("txt", 10), ("mp4", 5), ("docx", 10), ("zip", 5), ("mp3", 10)]


def words(n: int) -> str:
    return " ".join(random.choice(WORDS) for _ in range(n))


def jpeg(seed: int) -> bytes:
    from PIL import Image
    out = io.BytesIO()
    random.seed(seed)
    Image.new("RGB", (640, 480), (random.randrange(255), random.randrange(255), random.randrange(255))).save(out, "JPEG")
    return out.getvalue()


def seed(settings: Settings, n_files: int, n_notes: int, n_clips: int, n_links: int, n_folders: int) -> None:
    started = time.time()
    db.prepare(settings)
    extensions = [ext for ext, weight in EXTENSIONS for _ in range(weight)]
    with db.connect(settings.db_path) as conn:
        now = db.now()
        folder_ids: list[int | None] = [None]
        for i in range(n_folders):
            parent = random.choice(folder_ids)
            cursor = conn.execute(
                "INSERT INTO folders (parent_id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (parent, f"{random.choice(WORDS).title()} {i}", now, now))
            folder_ids.append(cursor.lastrowid)

        for i in range(n_files):
            ext = random.choice(extensions)
            file_id = uuid.uuid4().hex
            body = jpeg(i) if ext == "jpg" else (words(50) + f" {i}").encode()
            path = storage.path_for(settings.files_dir, file_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            kind, mime = storage.kind_and_mime(f"x.{ext}")
            stamp = f"2026-{random.randrange(1, 10):02}-{random.randrange(1, 29):02}T{random.randrange(24):02}:{random.randrange(60):02}:00Z"
            conn.execute(
                "INSERT INTO files (id, folder_id, name, size, sha256, mime, kind, favorite, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (file_id, random.choice(folder_ids), f"{words(2).replace(' ', '-')}-{i}.{ext}", len(body),
                 hashlib.sha256(body).hexdigest(), mime, kind, int(random.random() < 0.02), stamp, stamp))

        for i in range(n_notes):
            conn.execute("INSERT INTO notes (title, body, favorite, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                         (f"{words(3).title()} {i}", "\n".join(words(20) for _ in range(8)),
                          int(random.random() < 0.02), now, now))
        for i in range(n_clips):
            conn.execute("INSERT INTO clips (title, content, hidden, favorite, created_at, updated_at)"
                         " VALUES (?, ?, ?, ?, ?, ?)",
                         (f"{words(2).title()} {i}", words(12), int(random.random() < 0.2),
                          int(random.random() < 0.05), now, now))
        for i in range(n_links):
            conn.execute("INSERT INTO links (title, url, description, favorite, created_at, updated_at)"
                         " VALUES (?, ?, ?, ?, ?, ?)",
                         (f"{words(2).title()} {i}", f"https://{random.choice(WORDS)}{i}.example.com/page",
                          words(6), int(random.random() < 0.05), now, now))
    total = sum(p.stat().st_size for p in settings.files_dir.rglob("*") if p.is_file())
    print(f"Seeded {n_files} files ({total / 1024 / 1024:.0f} MB), {n_notes} notes, {n_clips} clips, "
          f"{n_links} links, {n_folders} folders into {settings.data_dir} in {time.time() - started:.1f}s.")
    print("Start it with:  VAULT_DATA_DIR=%s python -m app" % settings.data_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill a throw-away vault with demo content.")
    parser.add_argument("--files", type=int, default=2000)
    parser.add_argument("--notes", type=int, default=500)
    parser.add_argument("--clips", type=int, default=200)
    parser.add_argument("--links", type=int, default=100)
    parser.add_argument("--folders", type=int, default=40)
    parser.add_argument("--force", action="store_true", help="seed even if the data folder already holds a vault")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    if settings.db_path.exists() and not args.force:
        print(f"{settings.db_path} already exists. Point VAULT_DATA_DIR at an empty folder "
              "(or pass --force if you really mean this one).", file=sys.stderr)
        return 1
    random.seed(os.environ.get("SEED", "vault"))
    seed(settings, args.files, args.notes, args.clips, args.links, args.folders)
    return 0


if __name__ == "__main__":
    sys.exit(main())
