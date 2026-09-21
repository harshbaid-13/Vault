"""The vault's command line (run inside the container).

    python -m app.cli set-password   set or change the vault password
    python -m app.cli check [--fix]  compare the database with what's on disk

`set-password` prompts twice with hidden input, stores only the Argon2id hash and logs every
device out. Both commands are safe to run while the vault is running.
"""
import argparse
import getpass
import sys

from app import auth, db, storage, thumbs
from app.config import ConfigError, Settings
from app.web import size


def set_password(settings: Settings) -> int:
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        # Not db.prepare(): that empties tmp/, which would break an upload in progress.
        db.migrate(settings.db_path)
    except OSError:
        print(f"Cannot write to the data folder {settings.data_dir}.", file=sys.stderr)
        return 1

    try:
        password = getpass.getpass("New vault password: ")
        if len(password) < auth.MIN_PASSWORD_LENGTH:
            print(f"Not changed: the password needs at least {auth.MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
            return 1
        if getpass.getpass("Type it again: ") != password:
            print("Not changed: the two passwords don't match.", file=sys.stderr)
            return 1
    except (KeyboardInterrupt, EOFError):
        print("\nNot changed.", file=sys.stderr)
        return 1

    auth.set_password(settings.db_path, password)
    print("Password set. Any device that was logged in has to log in again.")
    return 0


def stored_files(data_dir):
    """Every file on disk under data/files, by id."""
    files = data_dir / "files"
    return {p.name: p for p in files.glob("*/*") if p.is_file() and storage.ID_PATTERN.fullmatch(p.name)} if files.is_dir() else {}


def check(settings: Settings, fix: bool = False) -> int:
    """List what the database and the disk disagree about (TECH_PLAN §7).

    Orphans — bytes with no row — are what a crash between the two deletes leaves behind, and
    `--fix` removes them. A row whose bytes are missing is never "fixed" away: the row is the
    only record that the file existed, and a restore can bring the bytes back.
    """
    if not settings.db_path.is_file():
        print(f"No database at {settings.db_path}.", file=sys.stderr)
        return 1
    with db.connect(settings.db_path) as conn:
        rows = {row[0]: row[1] for row in conn.execute("SELECT id, size FROM files")}
    on_disk = stored_files(settings.data_dir)
    orphans = sorted(set(on_disk) - set(rows))
    missing = sorted(fid for fid in rows if fid not in on_disk)
    wrong_size = sorted(fid for fid, path in on_disk.items()
                        if fid in rows and path.stat().st_size != rows[fid])
    thumbs_dir = settings.thumbs_dir
    stray_thumbs = sorted(p for p in thumbs_dir.glob("*.*") if p.stem not in rows) if thumbs_dir.is_dir() else []
    freed = sum(on_disk[fid].stat().st_size for fid in orphans) + sum(p.stat().st_size for p in stray_thumbs)

    print(f"{len(rows)} files in the database, {len(on_disk)} on disk.")
    for fid in orphans:
        print(f"  orphan: {fid} is on disk with no row ({size(on_disk[fid].stat().st_size)})")
    for fid in missing:
        print(f"  MISSING: {fid} has a row but no bytes on disk")
    for fid in wrong_size:
        print(f"  MISSING: {fid} is on disk at the wrong size")
    if stray_thumbs:
        print(f"  {len(stray_thumbs)} thumbnails belong to files that are gone")
    if fix:
        for fid in orphans:
            storage.remove(settings.files_dir, fid)
            thumbs.remove(thumbs_dir, fid)
        for path in stray_thumbs:
            path.unlink(missing_ok=True)
        print(f"Removed {len(orphans)} orphan files and {len(stray_thumbs)} thumbnails; freed {size(freed)}.")
    elif orphans or stray_thumbs:
        print(f"Run `python -m app.cli check --fix` to delete them and free {size(freed)}.")
    if missing or wrong_size:
        print("Files are missing from the disk. Restore them from a backup: see README.md → Restore.",
              file=sys.stderr)
        return 1
    if not orphans and not stray_thumbs:
        print("Everything matches.")
    return 0


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("set-password", help="set or change the vault password")
    checker = commands.add_parser("check", help="compare the database with the files on disk")
    checker.add_argument("--fix", action="store_true", help="delete files on disk that no row points at")
    args = parser.parse_args(argv)

    try:
        settings = settings or Settings.from_env()
    except ConfigError as exc:
        print(f"Vault settings problem: {exc}", file=sys.stderr)
        return 1

    if args.command == "set-password":
        return set_password(settings)
    if args.command == "check":
        return check(settings, args.fix)
    return 2


if __name__ == "__main__":
    sys.exit(main())
