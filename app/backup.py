"""`python -m app.backup` — back up the vault while it runs (S10, TECH_PLAN §8 gotcha 16).

    backups/
    ├── files-mirror/<id[:2]>/<id>     every file ever backed up; a normal run never deletes
    └── db/vault-2026-09-15_0200.db   one integrity-checked database snapshot per run

A run: (1) snapshot the database with SQLite's online backup API and check the copy; (2) copy
every file the snapshot names that the mirror doesn't have yet, checking its sha256 on the way;
(3) check every file the snapshot names is in the mirror at the right size — if not, the snapshot
is kept but renamed …-INCOMPLETE.db and the exit code is 1; (4) keep the newest BACKUP_KEEP
snapshots. Files never change after upload, so each file's bytes are copied once, ever.

    python -m app.backup                 a backup
    python -m app.backup --verify        re-read every mirror file and check its hash (slow)
    python -m app.backup --prune-mirror  delete mirror files no kept snapshot needs

Prints ids, counts and sizes only — never a file name, note or clip.
"""
import argparse
import hashlib
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app import storage
from app.config import ConfigError, Settings
from app.web import size

CHUNK = 1024 * 1024
SPARE = 64 * 1024 * 1024  # never fill the backup disk to the last byte


class BackupError(Exception):
    """Something the person running the backup must fix. The message says what."""


def db_dir(settings: Settings) -> Path:
    return settings.backup_dir / "db"


def mirror_dir(settings: Settings) -> Path:
    return settings.backup_dir / "files-mirror"


def mirror_path(settings: Settings, file_id: str) -> Path:
    return storage.path_for(mirror_dir(settings), file_id)


SNAPSHOT_NAME = re.compile(r"vault-(\d{4}-\d\d-\d\d_\d{4})(?:-(\d+))?(?:-INCOMPLETE)?\.db")


def snapshot_order(path: Path) -> tuple[str, int]:
    """By time, then by the -2, -3 of a second run in the same minute."""
    match = SNAPSHOT_NAME.fullmatch(path.name)
    return (match[1], int(match[2] or 1)) if match else ("", 0)


def snapshots(settings: Settings) -> list[Path]:
    """Every snapshot, oldest first."""
    return sorted(db_dir(settings).glob("vault-*.db"), key=snapshot_order)


def check_database(path: Path) -> None:
    """Raise BackupError unless `path` is a sound vault database."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            conn.execute("SELECT id, size, sha256 FROM files LIMIT 1").fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise BackupError(f"{path.name} is not a readable vault database ({exc}).") from None
    if result != "ok":
        raise BackupError(f"{path.name} failed its integrity check: {result}")


def files_in(snapshot: Path) -> list[tuple[str, int, str]]:
    """(id, size, sha256) of every file the snapshot's database names."""
    conn = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    try:
        return [tuple(row) for row in conn.execute("SELECT id, size, sha256 FROM files ORDER BY id")]
    finally:
        conn.close()


def copy_checked(source: Path, target: Path, sha256: str) -> None:
    """Copy via target.part + fsync + rename, hashing on the way. The hash must match."""
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    hasher = hashlib.sha256()
    try:
        with open(source, "rb") as src, open(part, "wb") as out:
            while chunk := src.read(CHUNK):
                hasher.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if hasher.hexdigest() != sha256:
            raise BackupError(f"file {target.name} doesn't match its recorded hash: the copy on disk is damaged")
        os.replace(part, target)
    finally:
        part.unlink(missing_ok=True)


def hash_of(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            hasher.update(chunk)
    return hasher.hexdigest()


def snapshot_name(settings: Settings) -> Path:
    """vault-2026-09-15_0200.db; a second run in the same minute gets -2 (after the highest yet)."""
    stamp = datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d_%H%M")
    taken = [n for s, n in map(snapshot_order, snapshots(settings)) if s == stamp]
    return db_dir(settings) / (f"vault-{stamp}-{max(taken) + 1}.db" if taken else f"vault-{stamp}.db")


def snapshot_database(settings: Settings) -> Path:
    """Copy the live database with the online backup API (safe while the app writes), check the
    copy, then move it into place. Returns the snapshot's path."""
    if not settings.db_path.is_file():
        raise BackupError(f"there is no database at {settings.db_path}. Is VAULT_DATA_DIR right?")
    db_dir(settings).mkdir(parents=True, exist_ok=True)
    target = snapshot_name(settings)
    part = target.with_name(target.name + ".part")
    try:
        source = sqlite3.connect(settings.db_path, timeout=30)
        copy = sqlite3.connect(part)
        try:
            source.backup(copy)
            # The live database is in WAL mode, and the copy inherits it. A snapshot must be one
            # self-contained file, with no -wal/-shm beside it.
            copy.execute("PRAGMA journal_mode = DELETE")
        finally:
            copy.close()
            source.close()
        check_database(part)
        os.replace(part, target)
    finally:
        part.unlink(missing_ok=True)
    return target


def run_backup(settings: Settings) -> int:
    snapshot = snapshot_database(settings)
    wanted = files_in(snapshot)
    missing = [(fid, fsize, sha) for fid, fsize, sha in wanted if not mirror_path(settings, fid).is_file()]
    needed = sum(fsize for _, fsize, _ in missing)
    mirror_dir(settings).mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(settings.backup_dir).free
    if needed + SPARE > free:
        snapshot.unlink()
        raise BackupError(f"the backup disk has {size(free)} free, and this run needs {size(needed)}. Free some space.")

    problems: list[str] = []
    copied = 0
    for file_id, _, sha in missing:
        try:
            copy_checked(storage.path_for(settings.files_dir, file_id), mirror_path(settings, file_id), sha)
            copied += 1
        except FileNotFoundError:
            problems.append(f"file {file_id} is in the database but missing from data/files")
        except BackupError as exc:
            problems.append(str(exc))

    # Every file this snapshot names must be in the mirror, at its size, for a restore to work.
    gaps = [fid for fid, fsize, _ in wanted
            if not (path := mirror_path(settings, fid)).is_file() or path.stat().st_size != fsize]
    mirror_total = sum(fsize for _, fsize, _ in wanted)
    if gaps:
        incomplete = snapshot.with_name(snapshot.stem + "-INCOMPLETE.db")
        os.replace(snapshot, incomplete)
        prune_snapshots(settings)
        for problem in problems:
            print(f"  - {problem}")
        print(f"Backup INCOMPLETE: {len(gaps)} of {len(wanted)} files are not in the mirror. "
              f"Snapshot kept as {incomplete}.")
        return 1
    pruned = prune_snapshots(settings)
    print(f"Backup done: {snapshot} ({size(snapshot.stat().st_size)}).")
    print(f"Files: {copied} new copied ({size(needed)}); the mirror has all {len(wanted)} "
          f"({size(mirror_total)}).")
    if pruned:
        print(f"Removed {pruned} old snapshot{'s' if pruned > 1 else ''} (keeping {settings.backup_keep}).")
    return 0


def prune_snapshots(settings: Settings) -> int:
    old = snapshots(settings)[:-settings.backup_keep]
    for path in old:
        path.unlink()
    return len(old)


def needed_ids(settings: Settings) -> dict[str, str]:
    """id → sha256 of every file any kept snapshot names."""
    ids: dict[str, str] = {}
    for snapshot in snapshots(settings):
        try:
            ids.update({fid: sha for fid, _, sha in files_in(snapshot)})
        except sqlite3.Error:
            raise BackupError(f"{snapshot.name} can't be read, so it's unclear which files it needs. "
                              "Move it out of backups/db and try again.") from None
    return ids


def mirror_files(settings: Settings) -> list[Path]:
    root = mirror_dir(settings)
    return sorted(p for p in root.glob("*/*") if p.is_file() and storage.ID_PATTERN.fullmatch(p.name)) if root.is_dir() else []


def run_verify(settings: Settings) -> int:
    """Re-hash every mirror file against the hashes the snapshots recorded."""
    known = needed_ids(settings)
    damaged, checked = [], 0
    for path in mirror_files(settings):
        if path.name in known:
            checked += 1
            if hash_of(path) != known[path.name]:
                damaged.append(path.name)
    missing = [fid for fid in known if not mirror_path(settings, fid).is_file()]
    for fid in damaged:
        print(f"  - file {fid}: damaged in the mirror (hash differs)")
    for fid in missing:
        print(f"  - file {fid}: missing from the mirror")
    if damaged or missing:
        print(f"Verify FAILED: {len(damaged)} damaged, {len(missing)} missing, {checked} checked. "
              "Copy those files back from your external-drive copy of backups/.")
        return 1
    print(f"Verify OK: {checked} files re-read and match their hashes.")
    return 0


def run_prune_mirror(settings: Settings) -> int:
    """Delete mirror files that no kept snapshot names (files deleted before the oldest one)."""
    keep = needed_ids(settings)
    if not snapshots(settings):
        raise BackupError("there are no snapshots, so nothing says which files to keep. Run a backup first.")
    freed = removed = 0
    for path in mirror_files(settings):
        if path.name not in keep:
            freed += path.stat().st_size
            path.unlink()
            removed += 1
    print(f"Removed {removed} files no snapshot needs; freed {size(freed)}.")
    return 0


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.backup", description="Back up the vault.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true", help="re-read every mirror file and check its hash")
    mode.add_argument("--prune-mirror", action="store_true", help="delete mirror files no kept snapshot needs")
    args = parser.parse_args(argv)
    try:
        settings = settings or Settings.from_env()
        if args.verify:
            return run_verify(settings)
        if args.prune_mirror:
            return run_prune_mirror(settings)
        return run_backup(settings)
    except (ConfigError, BackupError) as exc:
        print(f"Backup FAILED: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Backup FAILED: {exc.strerror or exc} ({exc.filename or 'backup folder'}).", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
