"""`python -m app.cli set-password` — set or change the vault password.

Prompts twice with hidden input. Only the Argon2id hash is stored. Every logged-in device is
logged out. Safe to run while the vault is running.
"""
import argparse
import getpass
import sys

from app import auth, db
from app.config import ConfigError, Settings


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("set-password", help="set or change the vault password")
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(f"Vault settings problem: {exc}", file=sys.stderr)
        return 1

    if args.command == "set-password":
        return set_password(settings)
    return 2


if __name__ == "__main__":
    sys.exit(main())
