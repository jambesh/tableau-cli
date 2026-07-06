"""Authentication and connection management.

The design goal is: authenticate once with ``tab-cli login``, then let every
other command silently reuse the cached token. Because Tableau personal access
tokens allow only a single active session, re-signing in on every command would
invalidate the previous session -- so caching and reusing the token is not just
an optimization, it is the correct behavior.

``Session.connect()`` returns a ready-to-use, signed-in :class:`TSC.Server`. It
prefers the cached token and only performs a fresh sign-in when the cache is
missing or has expired.
"""

from __future__ import annotations

import time
from typing import Optional

import tableauserverclient as TSC

from .config import Config, SessionCache
from .errors import NotLoggedInError, TabCliError


class Session:
    """Owns the connection lifecycle for a single CLI invocation."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config.load()
        self._server: Optional[TSC.Server] = None

    # ------------------------------------------------------------------ #
    # Sign in
    # ------------------------------------------------------------------ #
    def _new_server(self) -> TSC.Server:
        server = TSC.Server(self.config.server)
        if not self.config.ssl_verify:
            server.add_http_options({"verify": False})
        return server

    def _auth_object(self):
        cfg = self.config
        site = cfg.site or ""
        if cfg.auth_method == "pat":
            if not (cfg.token_name and cfg.token_value):
                raise NotLoggedInError(
                    "No personal access token configured. Run `tab-cli login`."
                )
            return TSC.PersonalAccessTokenAuth(cfg.token_name, cfg.token_value, site_id=site)
        if not (cfg.username and cfg.password):
            raise NotLoggedInError(
                "No username/password configured. Run `tab-cli login`."
            )
        return TSC.TableauAuth(cfg.username, cfg.password, site_id=site)

    def sign_in(self) -> TSC.Server:
        """Perform a fresh sign-in and refresh the on-disk session cache."""
        if not self.config.server:
            raise NotLoggedInError()
        server = self._new_server()
        try:
            server.use_server_version()
            server.auth.sign_in(self._auth_object())
        except TSC.ServerResponseError as exc:
            raise TabCliError(f"Sign-in failed: {_fmt(exc)}") from exc
        except Exception as exc:  # network errors, bad URL, etc.
            raise TabCliError(f"Could not reach server: {exc}") from exc

        SessionCache(
            server=self.config.server,
            site=self.config.site,
            auth_token=server.auth_token,
            site_id=server.site_id,
            user_id=server.user_id,
            site_url=server.site_url or "",
            server_version=str(server.version),
            signed_in_at=time.time(),
        ).save()
        self._server = server
        return server

    # ------------------------------------------------------------------ #
    # Restore from cache
    # ------------------------------------------------------------------ #
    def _restore(self, cache: SessionCache) -> TSC.Server:
        server = self._new_server()
        server.version = cache.server_version or server.version
        server._set_auth(cache.site_id, cache.user_id, cache.auth_token, cache.site_url)
        return server

    @staticmethod
    def _is_valid(server: TSC.Server) -> bool:
        """Cheap authenticated probe to confirm the token is still alive."""
        try:
            server.users.get_by_id(server.user_id)
            return True
        except (TSC.NotSignedInError, TSC.ServerResponseError, TSC.EndpointUnavailableError):
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #
    def connect(self) -> TSC.Server:
        """Return a signed-in server, reusing the cached token when possible."""
        if self._server is not None:
            return self._server

        cache = SessionCache.load()
        if cache and cache.is_usable() and cache.server == self.config.server:
            server = self._restore(cache)
            if self._is_valid(server):
                self._server = server
                return server
            # Token expired -- fall through to a fresh sign-in if we can.

        if not self.config.has_credentials():
            raise NotLoggedInError()
        return self.sign_in()

    def sign_out(self) -> None:
        """Invalidate the server-side session and drop the local cache."""
        cache = SessionCache.load()
        if cache and cache.is_usable() and cache.server == self.config.server:
            try:
                server = self._restore(cache)
                server.auth.sign_out()
            except Exception:
                pass  # Best-effort; we still clear local state below.
        SessionCache.clear()
        self._server = None


def _fmt(exc: TSC.ServerResponseError) -> str:
    summary = getattr(exc, "summary", None)
    detail = getattr(exc, "detail", None)
    if summary and detail:
        return f"{summary} - {detail}"
    return str(exc)
