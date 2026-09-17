"""SQLite: connections, startup preparation and numbered migrations. Plain sqlite3, no ORM."""
import logging
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.config import ConfigError, Settings

log = logging.getLogger("vault.db")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
DATA_SUBDIRS = ("files", "thumbs", "tmp")


def now() -> str:
    """The only timestamp format stored: fixed width, UTC, so text order is time order."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def like_pattern(term: str) -> str:
    """A LIKE pattern matching `term` anywhere, literally. Use with ESCAPE '\\'."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    """One short-lived connection: commits on success, rolls back on error, always closes."""
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def prepare(settings: Settings) -> int:
    """Make the data folders, empty tmp/, switch on WAL and migrate. Returns the schema version."""
    data_dir = settings.data_dir
    try:
        for name in DATA_SUBDIRS:
            (data_dir / name).mkdir(parents=True, exist_ok=True)
        probe = data_dir / "tmp" / ".write-test"
        probe.write_bytes(b"")
        probe.unlink()
    except OSError:
        raise ConfigError(
            f"cannot write to the data folder {data_dir}. With Docker, create it first "
            "(`mkdir -p data backups`) so it is owned by you, not root."
        ) from None

    # Anything left in tmp/ is a partial upload from before a restart.
    for leftover in (data_dir / "tmp").iterdir():
        if leftover.is_dir():
            shutil.rmtree(leftover)
        else:
            leftover.unlink()

    with connect(settings.db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
    return migrate(settings.db_path)


def migrate(path: Path, migrations_dir: Path = MIGRATIONS_DIR) -> int:
    """Apply every NNN_*.sql above the recorded version, each in its own transaction.

    Safe to run on every start. A failing migration rolls back completely and raises.
    """
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            " version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL) STRICT"
        )
        current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
        for file in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
            version = int(file.name[:3])
            if version <= current:
                continue
            # executescript commits anything pending before it starts, so the transaction
            # has to be part of the script itself.
            script = (
                "BEGIN IMMEDIATE;\n"
                f"{file.read_text(encoding='utf-8')}\n"
                f"INSERT INTO schema_version (version, applied_at) VALUES ({version}, '{now()}');\n"
                "COMMIT;"
            )
            try:
                conn.executescript(script)
            except sqlite3.Error:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                log.error("Migration %s failed and was rolled back", file.name)
                raise
            log.info("Applied migration %s", file.name)
            current = version
        return current
    finally:
        conn.close()
