"""`tab-cli datasource` — manage published data sources."""

from __future__ import annotations

import os

import click
import tableauserverclient as TSC

from .. import output
from ..cli import pass_app
from ..resolve import ProjectIndex, resolve_datasource, resolve_user


@click.group()
def datasource():
    """List, download, move, rename, re-own, delete and refresh data sources."""


def _project_opt(f):
    return click.option("--project", help="Disambiguate by owning project name/path.")(f)


@datasource.command("list")
@click.option("--project", help="Only data sources in this project.")
@pass_app
def list_datasources(app, project):
    """List data sources (optionally within a --project)."""
    server = app.connect()
    index = ProjectIndex.load(server)
    target_id = index.resolve(project).id if project else None
    rows = []
    for ds in TSC.Pager(server.datasources):
        if target_id and ds.project_id != target_id:
            continue
        rows.append((ds.name, ds.project_name or "", ds.datasource_type or "", ds.id))
    rows.sort(key=lambda r: (r[1].lower(), r[0].lower()))
    if app.as_json:
        output.emit_json([{"name": n, "project": p, "type": t, "id": i} for n, p, t, i in rows])
        return
    output.table(["Data source", "Project", "Type", "Id"], rows, title="Data sources")


@datasource.command()
@click.argument("name")
@_project_opt
@click.option("-o", "--output", "dest", default=".", help="Destination file or directory.")
@click.option("--no-extract", is_flag=True, help="Download without the .hyper extract.")
@pass_app
def download(app, name, project, dest, no_extract):
    """Download data source NAME to a .tds/.tdsx file."""
    server = app.connect()
    ds = resolve_datasource(server, name, project)
    if os.path.isdir(dest):
        dest = os.path.join(dest, "")
    path = server.datasources.download(ds.id, filepath=dest, include_extract=not no_extract)
    output.success(f"Downloaded '{ds.name}' → {path}")


@datasource.command()
@click.argument("name")
@click.argument("new_name")
@_project_opt
@pass_app
def rename(app, name, new_name, project):
    """Rename data source NAME to NEW_NAME."""
    server = app.connect()
    ds = resolve_datasource(server, name, project)
    ds.name = new_name
    server.datasources.update(ds)
    output.success(f"Renamed data source '{name}' → '{new_name}'.")


@datasource.command()
@click.argument("name")
@click.argument("target_project")
@_project_opt
@pass_app
def move(app, name, target_project, project):
    """Move data source NAME into TARGET_PROJECT."""
    server = app.connect()
    index = ProjectIndex.load(server)
    ds = resolve_datasource(server, name, project, index=index)
    dest = index.resolve(target_project)
    ds.project_id = dest.id
    server.datasources.update(ds)
    output.success(f"Moved data source '{ds.name}' → project '{index.path_of(dest)}'.")


@datasource.command()
@click.argument("name")
@click.argument("new_owner")
@_project_opt
@pass_app
def chown(app, name, new_owner, project):
    """Change the owner of data source NAME to user NEW_OWNER."""
    server = app.connect()
    ds = resolve_datasource(server, name, project)
    user = resolve_user(server, new_owner)
    ds.owner_id = user.id
    server.datasources.update(ds)
    output.success(f"Data source '{ds.name}' owner set to '{user.name}'.")


@datasource.command()
@click.argument("name")
@_project_opt
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@pass_app
def delete(app, name, project, yes):
    """Delete data source NAME."""
    server = app.connect()
    ds = resolve_datasource(server, name, project)
    if not yes:
        click.confirm(f"Delete data source '{ds.name}' (project: {ds.project_name})?", abort=True)
    server.datasources.delete(ds.id)
    output.success(f"Deleted data source '{ds.name}'.")


@datasource.command()
@click.argument("name")
@_project_opt
@click.option("--wait", is_flag=True, help="Wait for the refresh job to finish.")
@pass_app
def refresh(app, name, project, wait):
    """Trigger an extract refresh for data source NAME."""
    server = app.connect()
    ds = resolve_datasource(server, name, project)
    job = server.datasources.refresh(ds)
    output.success(f"Queued refresh for '{ds.name}' (job id: {job.id}).")
    if wait:
        output.info("Waiting for job to complete …")
        server.jobs.wait_for_job(job)
        output.success("Refresh completed.")
