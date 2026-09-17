"""Settings, read once from the environment (Compose loads .env into it).

Nothing else in the app reads os.environ: create_app() takes a Settings, so tests can
build an app with any values.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EXAMPLE_SECRET = "replace-me-with-the-output-of-the-command-above"
SECRET_HELP = (
    'Generate one with:  python3 -c "import secrets; print(secrets.token_urlsafe(48))"\n'
    "and put it in .env as SESSION_SECRET=<the output>."
)


class ConfigError(Exception):
    """A setting is missing or wrong. The message is shown to the user as-is."""


@dataclass(frozen=True)
class Settings:
    session_secret: str
    data_dir: Path = Path("/data")
    backup_dir: Path = Path("/backups")
    max_upload_size_mb: int = 2048
    cookie_secure: bool = False
    allowed_origins: tuple[str, ...] = ()
    session_days: int = 30
    backup_keep: int = 30
    timezone: str = "Asia/Kolkata"

    def __post_init__(self) -> None:
        # Never put the secret itself in a message.
        if not self.session_secret:
            raise ConfigError(f"SESSION_SECRET is not set.\n{SECRET_HELP}")
        if self.session_secret == EXAMPLE_SECRET:
            raise ConfigError(f"SESSION_SECRET is still the example value from .env.example.\n{SECRET_HELP}")
        if len(self.session_secret) < 32:
            raise ConfigError(f"SESSION_SECRET is too short (it needs at least 32 characters).\n{SECRET_HELP}")
        for name in ("max_upload_size_mb", "session_days", "backup_keep"):
            if getattr(self, name) < 1:
                raise ConfigError(f"{name.upper()} must be 1 or more.")
        for origin in self.allowed_origins:
            if not origin.startswith(("http://", "https://")) or origin.endswith("/"):
                raise ConfigError(
                    f"VAULT_ALLOWED_ORIGINS entry {origin!r} must look like https://host.example "
                    "(scheme and host, no path, no trailing slash)."
                )
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ConfigError(f"VAULT_TIMEZONE {self.timezone!r} is not a known time zone, e.g. Asia/Kolkata.") from None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "vault.db"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ

        def text(name: str, default: str) -> str:
            value = env.get(name, "").strip()
            return value or default

        def number(name: str, default: int) -> int:
            value = text(name, str(default))
            try:
                return int(value)
            except ValueError:
                raise ConfigError(f"{name} must be a whole number, not {value!r}.") from None

        def flag(name: str, default: bool) -> bool:
            value = text(name, "true" if default else "false").lower()
            if value in ("true", "1", "yes"):
                return True
            if value in ("false", "0", "no"):
                return False
            raise ConfigError(f"{name} must be true or false, not {value!r}.")

        origins = tuple(o.strip().rstrip("/") for o in env.get("VAULT_ALLOWED_ORIGINS", "").split(",") if o.strip())
        return cls(
            session_secret=env.get("SESSION_SECRET", "").strip(),
            data_dir=Path(text("VAULT_DATA_DIR", "/data")),
            backup_dir=Path(text("VAULT_BACKUP_DIR", "/backups")),
            max_upload_size_mb=number("MAX_UPLOAD_SIZE_MB", 2048),
            cookie_secure=flag("VAULT_COOKIE_SECURE", False),
            allowed_origins=origins,
            session_days=number("SESSION_DAYS", 30),
            backup_keep=number("BACKUP_KEEP", 30),
            timezone=text("VAULT_TIMEZONE", "Asia/Kolkata"),
        )
