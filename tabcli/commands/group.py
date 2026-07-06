"""`tab-cli group` — manage groups, including Active Directory imports."""

from __future__ import annotations

import click
import tableauserverclient as TSC

from .. import output
from ..cli import pass_app


@click.group()
def group():
    """List, create and import (Active Directory) groups."""


@group.command("list")
@pass_app
def list_groups(app):
    """List all groups."""
    server = app.connect()
    rows = []
    for g in TSC.Pager(server.groups):
        rows.append((g.name, g.domain_name or "local", g.user_count or 0, g.id))
    rows.sort(key=lambda r: r[0].lower())
    if app.as_json:
        output.emit_json(
            [{"name": n, "domain": d, "users": u, "id": i} for n, d, u, i in rows]
        )
        return
    output.table(["Group", "Domain", "Users", "Id"], rows, title="Groups")


@group.command()
@click.argument("name")
@pass_app
def create(app, name):
    """Create a local group NAME."""
    server = app.connect()
    created = server.groups.create(TSC.GroupItem(name=name))
    output.success(f"Created local group '{name}' (id: {created.id}).")


@group.command("import-ad")
@click.argument("name")
@click.option("--domain", required=True, help="Active Directory domain name, e.g. DOMAIN.")
@click.option(
    "--site-role",
    default="Unlicensed",
    help="Minimum site role granted to imported members (default: Unlicensed).",
)
@pass_app
def import_ad(app, name, domain, site_role):
    """Import an Active Directory group NAME from --domain."""
    server = app.connect()
    item = TSC.GroupItem(name=name, domain_name=domain)
    item.minimum_site_role = site_role
    created = server.groups.create_AD_group(item)
    output.success(f"Imported AD group '{domain}\\{name}' (id: {created.id}).")
