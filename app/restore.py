"""`python -m app.restore <snapshot>` — put the vault back as it was at one backup (S10).

Run it with the vault stopped:

    docker compose down
    docker compose run --rm vault python -m app.restore                        (lists snapshots)
    docker compose run --rm vault python -m app.restore vault-2026-09-15_0200.db
    docker compose up -d

It checks everything before touching anything: the snapshot passes an integrity check, and
every file it names is in backups/files-mirror at the right size. Then it moves the current
data into data/before-restore-<time>/ (never deletes it), copies the snapshot in as vault.db
and copies back only the files that snapshot names, checking each one's hash. If anything
fails part-way, the moved data is put back exactly as it was. Thumbnails are made again.
"""
import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app import storage
from app.backup import BackupError, check_database, copy_checked, db_dir, files_in, mirror_path, snapshots
from app.config import ConfigError, Settings
from app.web import size

ASIDE_PREFIX = "before-restore-"


def find_snapshot(settings: Settings, name: str) -> Path:
    """A path, or just the snapshot's file name (looked up in backups/db)."""
    for candidate in (Path(name), db_dir(settings) / Path(name).name):
        if candidate.is_file():
            return candidate
    raise BackupError(f"no snapshot called {name}. Run `python -m app.restore` with no name to list them.")


def list_snapshots(settings: Settings) -> int:
    found = snapshots(settings)
    if not found:
        print(f"No snapshots in {db_dir(settings)}. Run a backup first.")
        return 1
    print("Snapshots, newest last:")
    for path in found:
        print(f"  {path.name}  ({size(path.stat().st_size)})")
    print("Restore one with:  python -m app.restore <name>")
    return 0


def run_restore(settings: Settings, name: str) -> int:
    snapshot = find_snapshot(settings, name)
    if snapshot.name.endswith("-INCOMPLETE.db"):
        raise BackupError(f"{snapshot.name} is from a backup that didn't finish; some of its files are missing. "
                          "Pick an earlier snapshot.")

    # 1. Check everything first. Nothing has been touched yet.
    check_database(snapshot)
    wanted = files_in(snapshot)
    gaps = [fid for fid, fsize, _ in wanted
            if not (path := mirror_path(settings, fid)).is_file() or path.stat().st_size != fsize]
    if gaps:
        raise BackupError(f"{len(gaps)} of the {len(wanted)} files this snapshot needs are missing from "
                          "backups/files-mirror (or the wrong size). Nothing was changed. Copy the mirror back "
                          "from your external drive, or pick another snapshot.")
    total = sum(fsize for _, fsize, _ in wanted) + snapshot.stat().st_size
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(settings.data_dir).free
    if total > free:
        raise BackupError(f"restoring needs {size(total)} and the data disk has {size(free)} free. Nothing was changed.")

    # 2. Move the current data aside (a rename: instant, no extra space). /data is a mount point,
    #    so its contents move into a subfolder rather than the folder itself being renamed.
    stamp = datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d_%H%M%S")
    aside = settings.data_dir / f"{ASIDE_PREFIX}{stamp}"
    aside.mkdir()
    moved = [p for p in settings.data_dir.iterdir() if p != aside and not p.name.startswith(ASIDE_PREFIX)]
    for path in moved:
        os.replace(path, aside / path.name)

    # 3. Copy the snapshot and its files in. Any failure puts the old data back.
    try:
        shutil.copyfile(snapshot, settings.db_path)
        check_database(settings.db_path)
        for file_id, _, sha in wanted:
            copy_checked(mirror_path(settings, file_id), storage.path_for(settings.files_dir, file_id), sha)
    except BaseException:
        for path in list(settings.data_dir.iterdir()):
            if path == aside or path.name.startswith(ASIDE_PREFIX):
                continue
            shutil.rmtree(path) if path.is_dir() else path.unlink()
        for path in aside.iterdir():
            os.replace(path, settings.data_dir / path.name)
        aside.rmdir()
        print("Restore stopped part-way; your data was put back as it was.")
        raise

    print(f"Restored {snapshot.name}: {len(wanted)} files ({size(total - snapshot.stat().st_size)}).")
    print(f"Your previous data is in data/{aside.name}/ — delete it once you've checked the vault.")
    print("Start the vault again with:  docker compose up -d")
    return 0


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.restore", description="Restore the vault from a backup.")
    parser.add_argument("snapshot", nargs="?", help="a snapshot file name from backups/db (omit to list them)")
    args = parser.parse_args(argv)
    try:
        settings = settings or Settings.from_env()
        if not args.snapshot:
            return list_snapshots(settings)
        return run_restore(settings, args.snapshot)
    except (ConfigError, BackupError) as exc:
        print(f"Restore FAILED: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Restore FAILED: {exc.strerror or exc}.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
