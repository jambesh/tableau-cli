"""`tab-cli workbook` — manage workbooks."""

from __future__ import annotations

import os

import click
import tableauserverclient as TSC

from .. import output
from ..cli import pass_app
from ..resolve import ProjectIndex, resolve_user, resolve_workbook


@click.group()
def workbook():
    """List, download, move, rename, re-own, delete and refresh workbooks."""


def _project_opt(f):
    return click.option("--project", help="Disambiguate by owning project name/path.")(f)


@workbook.command("list")
@click.option("--project", help="Only workbooks in this project.")
@pass_app
def list_workbooks(app, project):
    """List workbooks (optionally within a --project)."""
    server = app.connect()
    index = ProjectIndex.load(server)
    target_id = index.resolve(project).id if project else None
    rows = []
    for wb in TSC.Pager(server.workbooks):
        if target_id and wb.project_id != target_id:
            continue
        rows.append((wb.name, wb.project_name or "", wb.id, str(wb.updated_at or "")[:19]))
    rows.sort(key=lambda r: (r[1].lower(), r[0].lower()))
    if app.as_json:
        output.emit_json([{"name": n, "project": p, "id": i, "updated_at": u} for n, p, i, u in rows])
        return
    output.table(["Workbook", "Project", "Id", "Updated"], rows, title="Workbooks")


@workbook.command()
@click.argument("name")
@_project_opt
@click.option("-o", "--output", "dest", default=".", help="Destination file or directory.")
@click.option("--no-extract", is_flag=True, help="Download without the .hyper extract (smaller .twb).")
@pass_app
def download(app, name, project, dest, no_extract):
    """Download workbook NAME to a .twb/.twbx file."""
    server = app.connect()
    wb = resolve_workbook(server, name, project)
    if os.path.isdir(dest):
        dest = os.path.join(dest, "")  # trailing sep -> TSC uses server filename
    path = server.workbooks.download(wb.id, filepath=dest, include_extract=not no_extract)
    output.success(f"Downloaded '{wb.name}' → {path}")


@workbook.command()
@click.argument("name")
@click.argument("new_name")
@_project_opt
@pass_app
def rename(app, name, new_name, project):
    """Rename workbook NAME to NEW_NAME."""
    server = app.connect()
    wb = resolve_workbook(server, name, project)
    wb.name = new_name
    server.workbooks.update(wb)
    output.success(f"Renamed workbook '{name}' → '{new_name}'.")


@workbook.command()
@click.argument("name")
@click.argument("target_project")
@_project_opt
@pass_app
def move(app, name, target_project, project):
    """Move workbook NAME into TARGET_PROJECT."""
    server = app.connect()
    index = ProjectIndex.load(server)
    wb = resolve_workbook(server, name, project, index=index)
    dest = index.resolve(target_project)
    wb.project_id = dest.id
    server.workbooks.update(wb)
    output.success(f"Moved workbook '{wb.name}' → project '{index.path_of(dest)}'.")


@workbook.command()
@click.argument("name")
@click.argument("new_owner")
@_project_opt
@pass_app
def chown(app, name, new_owner, project):
    """Change the owner of workbook NAME to user NEW_OWNER."""
    server = app.connect()
    wb = resolve_workbook(server, name, project)
    user = resolve_user(server, new_owner)
    wb.owner_id = user.id
    server.workbooks.update(wb)
    output.success(f"Workbook '{wb.name}' owner set to '{user.name}'.")


@workbook.command()
@click.argument("name")
@_project_opt
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@pass_app
def delete(app, name, project, yes):
    """Delete workbook NAME."""
    server = app.connect()
    wb = resolve_workbook(server, name, project)
    if not yes:
        click.confirm(f"Delete workbook '{wb.name}' (project: {wb.project_name})?", abort=True)
    server.workbooks.delete(wb.id)
    output.success(f"Deleted workbook '{wb.name}'.")


@workbook.command()
@click.argument("name")
@_project_opt
@click.option("--wait", is_flag=True, help="Wait for the refresh job to finish.")
@pass_app
def refresh(app, name, project, wait):
    """Trigger an extract refresh for workbook NAME."""
    server = app.connect()
    wb = resolve_workbook(server, name, project)
    job = server.workbooks.refresh(wb)
    output.success(f"Queued refresh for '{wb.name}' (job id: {job.id}).")
    if wait:
        output.info("Waiting for job to complete …")
        server.jobs.wait_for_job(job)
        output.success("Refresh completed.")
