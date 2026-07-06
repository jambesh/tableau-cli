"""Configuration and credential storage for tab-cli.

All state lives under ``~/.tabcli`` (override with ``TABCLI_HOME``):

* ``config.json``  -- connection profile plus (optionally) the secret used to
  re-authenticate. Written with ``0600`` permissions.
* ``session.json`` -- the cached Tableau auth token so subsequent commands do
  not need to sign in again. Also ``0600``.

Every value in ``config.json`` can be overridden by an environment variable,
which is handy for CI / scripted use where writing secrets to disk is not
desirable.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

CONFIG_FILE = "config.json"
SESSION_FILE = "session.json"

_ENV = {
    "server": "TABCLI_SERVER",
    "site": "TABCLI_SITE",
    "auth_method": "TABCLI_AUTH_METHOD",
    "token_name": "TABCLI_TOKEN_NAME",
    "token_value": "TABCLI_TOKEN_VALUE",
    "username": "TABCLI_USERNAME",
    "password": "TABCLI_PASSWORD",
}


def home_dir() -> Path:
    """Directory where all tab-cli state is stored."""
    override = os.environ.get("TABCLI_HOME")
    base = Path(override).expanduser() if override else Path.home() / ".tabcli"
    return base


def _ensure_home() -> Path:
    d = home_dir()
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return d


def _write_private(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON with owner-only permissions."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    try:
        os.chmod(path, 0o600)
    except OSError:
        # Best-effort on platforms that don't support chmod semantics.
        pass


@dataclass
class Config:
    """A saved connection profile."""

    server: str = ""
    site: str = ""  # content URL; "" means the Default site
    auth_method: str = "pat"  # "pat" or "password"
    token_name: Optional[str] = None
    token_value: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl_verify: bool = True

    # ---- persistence -----------------------------------------------------
    @classmethod
    def path(cls) -> Path:
        return home_dir() / CONFIG_FILE

    @classmethod
    def load(cls) -> "Config":
        """Load config from disk, then layer environment overrides on top."""
        data: dict[str, Any] = {}
        p = cls.path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
            except (ValueError, OSError):
                data = {}

        cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

        for field_name, env_name in _ENV.items():
            env_val = os.environ.get(env_name)
            if env_val is not None:
                setattr(cfg, field_name, env_val)
        if os.environ.get("TABCLI_SSL_NO_VERIFY"):
            cfg.ssl_verify = False
        return cfg

    def save(self) -> Path:
        _ensure_home()
        p = self.path()
        _write_private(p, asdict(self))
        return p

    # ---- helpers ---------------------------------------------------------
    def is_configured(self) -> bool:
        return bool(self.server) and self.has_credentials()

    def has_credentials(self) -> bool:
        if self.auth_method == "pat":
            return bool(self.token_name and self.token_value)
        return bool(self.username and self.password)

    def redacted(self) -> dict[str, Any]:
        d = asdict(self)
        for secret in ("token_value", "password"):
            if d.get(secret):
                d[secret] = "********"
        return d


@dataclass
class SessionCache:
    """The cached, live auth token returned by a successful sign-in."""

    server: str = ""
    site: str = ""
    auth_token: str = ""
    site_id: str = ""
    user_id: str = ""
    site_url: str = ""
    server_version: str = ""
    signed_in_at: float = 0.0

    @classmethod
    def path(cls) -> Path:
        return home_dir() / SESSION_FILE

    @classmethod
    def load(cls) -> Optional["SessionCache"]:
        p = cls.path()
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text())
        except (ValueError, OSError):
            return None
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self) -> Path:
        _ensure_home()
        p = self.path()
        _write_private(p, asdict(self))
        return p

    @classmethod
    def clear(cls) -> None:
        p = cls.path()
        try:
            p.unlink()
        except FileNotFoundError:
            pass

    def is_usable(self) -> bool:
        return bool(self.auth_token and self.site_id and self.user_id)
