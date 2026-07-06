"""Authentication commands: login, logout, whoami, status."""

from __future__ import annotations

import click

from .. import output
from ..cli import pass_app
from ..config import Config, SessionCache
from ..errors import TabCliError


@click.command()
@click.option("-s", "--server", help="Tableau Server / Cloud URL, e.g. https://10ax.online.tableau.com")
@click.option("--site", default=None, help="Site content URL. Empty for the Default site.")
@click.option(
    "-m",
    "--method",
    "auth_method",
    type=click.Choice(["pat", "password"]),
    default=None,
    help="Authentication method (default: pat).",
)
@click.option("--token-name", help="Personal access token name (pat auth).")
@click.option("--token-value", help="Personal access token secret (pat auth).")
@click.option("-u", "--username", help="Username (password auth).")
@click.option("-p", "--password", help="Password (password auth).")
@click.option("--no-verify-ssl", is_flag=True, help="Do not verify the server's SSL certificate.")
@click.option(
    "--save-secret/--no-save-secret",
    default=True,
    help="Persist the token/password to ~/.tabcli/config.json (0600). "
    "With --no-save-secret, supply it via env var on each run.",
)
@pass_app
def login(app, server, site, auth_method, token_name, token_value, username, password, no_verify_ssl, save_secret):
    """Sign in to Tableau and cache the session for later commands.

    \b
    Examples:
      tab-cli login -s https://my.tableau.com --token-name ci --token-value XXXX
      tab-cli login -s https://my.tableau.com -m password -u alice --site Marketing
    """
    existing = app.config

    server = server or existing.server or click.prompt("Server URL")
    auth_method = auth_method or (existing.auth_method or "pat")
    if site is None:
        site = existing.site or ""

    if auth_method == "pat":
        token_name = token_name or existing.token_name or click.prompt("Token name")
        token_value = token_value or click.prompt("Token value", hide_input=True)
        username = password = None
    else:
        username = username or existing.username or click.prompt("Username")
        password = password or click.prompt("Password", hide_input=True)
        token_name = token_value = None

    cfg = Config(
        server=server.rstrip("/"),
        site=site,
        auth_method=auth_method,
        token_name=token_name,
        token_value=token_value,
        username=username,
        password=password,
        ssl_verify=not no_verify_ssl,
    )

    # Validate the credentials by actually signing in before persisting.
    from ..session import Session

    session = Session(cfg)
    output.info(f"Signing in to {cfg.server} …")
    srv = session.sign_in()

    persisted = cfg
    if not save_secret:
        persisted = Config(**{**cfg.__dict__})
        persisted.token_value = None
        persisted.password = None
    persisted.save()

    site_label = cfg.site or "Default"
    output.success(
        f"Signed in to {cfg.server} (site: {site_label}) as user id {srv.user_id}. "
        f"Server version {srv.version}."
    )
    if not save_secret:
        env = "TABCLI_TOKEN_VALUE" if auth_method == "pat" else "TABCLI_PASSWORD"
        output.warn(f"Secret not saved. Set ${env} before running other commands.")


@click.command()
@pass_app
def logout(app):
    """Sign out and clear the cached session."""
    app.session.sign_out()
    output.success("Signed out. Cached session cleared.")


@click.command()
@pass_app
def whoami(app):
    """Show the currently signed-in user."""
    server = app.connect()
    user = server.users.get_by_id(server.user_id)
    if app.as_json:
        output.emit_json(
            {
                "server": app.config.server,
                "site": app.config.site or "Default",
                "user_id": user.id,
                "name": user.name,
                "fullname": user.fullname,
                "site_role": user.site_role,
            }
        )
        return
    output.table(
        ["Field", "Value"],
        [
            ("Server", app.config.server),
            ("Site", app.config.site or "Default"),
            ("Username", user.name),
            ("Full name", user.fullname or ""),
            ("Site role", user.site_role),
            ("User id", user.id),
        ],
        title="Current user",
    )


@click.command()
@pass_app
def status(app):
    """Show local login/session status without contacting the server."""
    cfg = app.config
    cache = SessionCache.load()
    rows = [
        ("Config file", str(Config.path())),
        ("Server", cfg.server or "(not set)"),
        ("Site", cfg.site or "Default"),
        ("Auth method", cfg.auth_method),
        ("Credentials stored", "yes" if cfg.has_credentials() else "no"),
        ("Cached session", "yes" if (cache and cache.is_usable()) else "no"),
    ]
    if app.as_json:
        output.emit_json({k: v for k, v in rows})
        return
    output.table(["Field", "Value"], rows, title="tab-cli status")
