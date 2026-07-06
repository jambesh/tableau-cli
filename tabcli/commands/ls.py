"""`tab-cli ls` — show a project's contents as a tree."""

from __future__ import annotations

import click

from .. import output
from ..cli import pass_app
from ..resolve import ProjectIndex, datasources_in, workbooks_in


@click.command()
@click.argument("project", required=False)
@click.option("-w", "--workbooks-only", is_flag=True, help="Show workbooks only.")
@click.option("-d", "--datasources-only", is_flag=True, help="Show data sources only.")
@click.option("-p", "--projects-only", is_flag=True, help="Show sub-projects only.")
@click.option("--depth", type=int, default=None, help="Limit sub-project recursion depth.")
@click.option("--owner", is_flag=True, help="Annotate workbooks/data sources with their owner.")
@pass_app
def ls(app, project, workbooks_only, datasources_only, projects_only, depth, owner):
    """List workbooks, data sources and sub-projects within PROJECT as a tree.

    PROJECT may be a name (e.g. `Finance`) or a full path (e.g.
    `Finance/Reports`). Omit it to list the site's top-level projects.

    \b
    Examples:
      tab-cli ls Finance
      tab-cli ls "Finance/Monthly Reports" --owner
      tab-cli ls --projects-only            # top-level projects
    """
    server = app.connect()
    index = ProjectIndex.load(server)

    show_wb = not (datasources_only or projects_only)
    show_ds = not (workbooks_only or projects_only)
    show_proj = not (workbooks_only or datasources_only)

    if project:
        root = index.resolve(project)
        root_id = root.id
        root_label = index.path_of(root)
        subtree_ids = _collect_ids(index, root_id, depth)
    else:
        root_id = None
        root_label = f"{app.config.server}  (site: {app.config.site or 'Default'})"
        subtree_ids = _collect_ids(index, None, depth)

    # Fetch content once for every project we intend to display.
    owner_names = _owner_lookup(server) if owner else {}
    wb_by_project = workbooks_in(server, subtree_ids) if show_wb else {}
    ds_by_project = datasources_in(server, subtree_ids) if show_ds else {}

    if app.as_json:
        output.emit_json(
            _json_node(index, root_id, root_label, wb_by_project, ds_by_project,
                       owner_names, show_wb, show_ds, show_proj, depth)
        )
        return

    def build(node, project_id, current_depth):
        if show_proj:
            for child in index.child_projects(project_id) if project_id else index.roots():
                if depth is not None and current_depth >= depth:
                    break
                child_node = output.add_project_node(node, child.name)
                build(child_node, child.id, current_depth + 1)
        if show_wb:
            for wb in sorted(wb_by_project.get(project_id, []), key=_key):
                output.add_workbook_node(node, wb.name, _annot(wb, owner_names, owner))
        if show_ds:
            for ds in sorted(ds_by_project.get(project_id, []), key=_key):
                output.add_datasource_node(node, ds.name, _annot(ds, owner_names, owner))

    output.render_tree(root_label, lambda tree: build(tree, root_id, 0))
    _print_summary(wb_by_project, ds_by_project, subtree_ids, index, root_id, show_proj, show_wb, show_ds)


def _key(item):
    return (item.name or "").lower()


def _collect_ids(index: ProjectIndex, root_id, depth):
    """Ids of root and its descendants, honoring an optional depth limit."""
    ids: list[str] = []
    if root_id is not None:
        ids.append(root_id)

    def walk(pid, level):
        if depth is not None and level >= depth:
            return
        for child in index.child_projects(pid) if pid else index.roots():
            ids.append(child.id)
            walk(child.id, level + 1)

    walk(root_id, 0)
    return ids


def _owner_lookup(server) -> dict[str, str]:
    import tableauserverclient as TSC

    return {u.id: u.name for u in TSC.Pager(server.users)}


def _annot(item, owner_names, owner) -> str:
    if owner and getattr(item, "owner_id", None):
        return f"owner: {owner_names.get(item.owner_id, item.owner_id)}"
    return ""


def _print_summary(wb, ds, ids, index, root_id, show_proj, show_wb, show_ds):
    n_proj = len(ids) - (1 if root_id is not None else 0)
    n_wb = sum(len(v) for v in wb.values())
    n_ds = sum(len(v) for v in ds.values())
    parts = []
    if show_proj:
        parts.append(f"{n_proj} sub-project(s)")
    if show_wb:
        parts.append(f"{n_wb} workbook(s)")
    if show_ds:
        parts.append(f"{n_ds} data source(s)")
    if parts:
        output.info(", ".join(parts))


def _json_node(index, project_id, label, wb, ds, owner_names, show_wb, show_ds, show_proj, depth, level=0):
    node = {"name": label, "id": project_id, "type": "project"}
    children = []
    if show_proj and not (depth is not None and level >= depth):
        for child in index.child_projects(project_id) if project_id else index.roots():
            children.append(
                _json_node(index, child.id, child.name, wb, ds, owner_names,
                           show_wb, show_ds, show_proj, depth, level + 1)
            )
    if show_wb:
        for w in wb.get(project_id, []):
            children.append({"name": w.name, "id": w.id, "type": "workbook",
                             "owner": owner_names.get(getattr(w, "owner_id", None))})
    if show_ds:
        for d in ds.get(project_id, []):
            children.append({"name": d.name, "id": d.id, "type": "datasource",
                             "owner": owner_names.get(getattr(d, "owner_id", None))})
    node["children"] = children
    return node
