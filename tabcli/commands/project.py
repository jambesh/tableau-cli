"""`tab-cli project` — manage projects."""

from __future__ import annotations

import click
import tableauserverclient as TSC

from .. import output
from ..cli import pass_app
from ..resolve import ProjectIndex, resolve_user


@click.group()
def project():
    """Create, rename, move, re-own and delete projects."""


@project.command("list")
@click.option("--top", is_flag=True, help="Only top-level projects.")
@pass_app
def list_projects(app, top):
    """List all projects with their full paths."""
    server = app.connect()
    index = ProjectIndex.load(server)
    projects = index.roots() if top else index.projects
    rows = sorted(
        ((index.path_of(p), p.id, p.content_permissions or "") for p in projects),
        key=lambda r: r[0].lower(),
    )
    if app.as_json:
        output.emit_json([{"path": p, "id": i, "content_permissions": c} for p, i, c in rows])
        return
    output.table(["Path", "Id", "Permissions"], rows, title="Projects")


@project.command()
@click.argument("name")
@click.option("--parent", help="Parent project name or path. Omit for a top-level project.")
@click.option("--description", default=None, help="Project description.")
@pass_app
def create(app, name, parent, description):
    """Create a new project NAME (optionally under --parent)."""
    server = app.connect()
    parent_id = None
    if parent:
        parent_id = ProjectIndex.load(server).resolve(parent).id
    item = TSC.ProjectItem(name=name, description=description, parent_id=parent_id)
    created = server.projects.create(item)
    output.success(f"Created project '{name}' (id: {created.id}).")


@project.command()
@click.argument("project_name")
@click.argument("new_name")
@pass_app
def rename(app, project_name, new_name):
    """Rename PROJECT_NAME to NEW_NAME."""
    server = app.connect()
    item = ProjectIndex.load(server).resolve(project_name)
    old = item.name
    item.name = new_name
    server.projects.update(item)
    output.success(f"Renamed project '{old}' → '{new_name}'.")


@project.command()
@click.argument("project_name")
@click.argument("new_parent", required=False)
@click.option("--to-root", is_flag=True, help="Move the project to the top level.")
@pass_app
def move(app, project_name, new_parent, to_root):
    """Move PROJECT_NAME under NEW_PARENT (or --to-root)."""
    if not new_parent and not to_root:
        raise click.UsageError("Provide a NEW_PARENT project or use --to-root.")
    server = app.connect()
    index = ProjectIndex.load(server)
    item = index.resolve(project_name)
    item.parent_id = None if to_root else index.resolve(new_parent).id
    server.projects.update(item)
    dest = "root" if to_root else new_parent
    output.success(f"Moved project '{item.name}' → {dest}.")


@project.command()
@click.argument("project_name")
@click.argument("new_owner")
@pass_app
def chown(app, project_name, new_owner):
    """Change the owner of PROJECT_NAME to user NEW_OWNER."""
    server = app.connect()
    index = ProjectIndex.load(server)
    item = index.resolve(project_name)
    user = resolve_user(server, new_owner)
    item.owner_id = user.id
    server.projects.update(item)
    output.success(f"Project '{item.name}' owner set to '{user.name}'.")


@project.command()
@click.argument("project_name")
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@pass_app
def delete(app, project_name, yes):
    """Delete PROJECT_NAME (and everything inside it)."""
    server = app.connect()
    index = ProjectIndex.load(server)
    item = index.resolve(project_name)
    path = index.path_of(item)
    if not yes:
        click.confirm(
            f"Delete project '{path}' and all its contents?", abort=True
        )
    server.projects.delete(item.id)
    output.success(f"Deleted project '{path}'.")


@project.command()
@click.argument("project_name")
@pass_app
def info(app, project_name):
    """Show details for PROJECT_NAME."""
    server = app.connect()
    index = ProjectIndex.load(server)
    item = index.resolve(project_name)
    n_children = len(index.child_projects(item.id))
    data = {
        "name": item.name,
        "path": index.path_of(item),
        "id": item.id,
        "description": item.description or "",
        "content_permissions": item.content_permissions or "",
        "parent_id": item.parent_id or "(root)",
        "sub_projects": n_children,
    }
    if app.as_json:
        output.emit_json(data)
        return
    output.table(["Field", "Value"], list(data.items()), title=f"Project: {item.name}")
