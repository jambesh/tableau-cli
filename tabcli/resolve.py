"""Resolve human-friendly names and paths to Tableau objects.

Tableau project names are unique only within their parent, so a bare name can
be ambiguous. Everywhere a project is accepted you may pass either:

* a plain name, e.g. ``Finance`` -- resolved uniquely if only one project has
  that name, otherwise the caller is shown the full paths to choose from; or
* a slash-delimited path from the root, e.g. ``Finance/Reports/2026``.
"""

from __future__ import annotations

from typing import Iterable, Optional

import tableauserverclient as TSC

from .errors import AmbiguousNameError, ResolutionError

PATH_SEP = "/"


def _all(endpoint) -> list:
    """Fetch every item from a paginated endpoint."""
    return list(TSC.Pager(endpoint))


class ProjectIndex:
    """An in-memory index of every project on the site."""

    def __init__(self, projects: list) -> None:
        self.projects = projects
        self.by_id = {p.id: p for p in projects}
        self.children: dict[Optional[str], list] = {}
        for p in projects:
            self.children.setdefault(p.parent_id, []).append(p)
        for kids in self.children.values():
            kids.sort(key=lambda p: (p.name or "").lower())

    @classmethod
    def load(cls, server) -> "ProjectIndex":
        return cls(_all(server.projects))

    # ---- paths -----------------------------------------------------------
    def path_of(self, project) -> str:
        parts = [project.name]
        seen = {project.id}
        parent_id = project.parent_id
        while parent_id and parent_id in self.by_id and parent_id not in seen:
            parent = self.by_id[parent_id]
            parts.append(parent.name)
            seen.add(parent.id)
            parent_id = parent.parent_id
        return PATH_SEP.join(reversed(parts))

    def roots(self) -> list:
        return self.children.get(None, [])

    def child_projects(self, project_id: str) -> list:
        return self.children.get(project_id, [])

    # ---- resolution ------------------------------------------------------
    def resolve(self, name_or_path: str):
        """Return the single project matching ``name_or_path``."""
        name_or_path = name_or_path.strip().strip(PATH_SEP)
        if not name_or_path:
            raise ResolutionError("Empty project name.")

        if PATH_SEP in name_or_path:
            return self._resolve_path(name_or_path)

        matches = [p for p in self.projects if p.name == name_or_path]
        if not matches:
            raise ResolutionError(f"No project named '{name_or_path}'.")
        if len(matches) == 1:
            return matches[0]
        paths = sorted(self.path_of(p) for p in matches)
        raise AmbiguousNameError(
            f"'{name_or_path}' matches {len(matches)} projects. "
            f"Use a full path:\n  " + "\n  ".join(paths)
        )

    def _resolve_path(self, path: str):
        parts = [seg for seg in path.split(PATH_SEP) if seg]
        current = None  # start at root (parent_id is None)
        for depth, seg in enumerate(parts):
            siblings = self.child_projects(current.id) if current else self.roots()
            match = next((p for p in siblings if p.name == seg), None)
            if match is None:
                where = self.path_of(current) if current else "root"
                raise ResolutionError(f"No project '{seg}' under {where}.")
            current = match
        return current


# --------------------------------------------------------------------------- #
# Content lookups (workbooks, datasources, users, views)
# --------------------------------------------------------------------------- #
def _filtered(endpoint, name: str) -> list:
    """Server-side name filter, falling back to a full scan if unsupported."""
    try:
        opts = TSC.RequestOptions()
        opts.filter.add(
            TSC.Filter(
                TSC.RequestOptions.Field.Name,
                TSC.RequestOptions.Operator.Equals,
                name,
            )
        )
        return list(TSC.Pager(endpoint, opts))
    except TSC.ServerResponseError:
        return [i for i in _all(endpoint) if i.name == name]


def _pick(matches: list, name: str, kind: str, project_name: Optional[str], index: Optional[ProjectIndex]):
    if project_name and index is not None:
        target = index.resolve(project_name)
        matches = [m for m in matches if getattr(m, "project_id", None) == target.id]
    if not matches:
        scope = f" in project '{project_name}'" if project_name else ""
        raise ResolutionError(f"No {kind} named '{name}'{scope}.")
    if len(matches) == 1:
        return matches[0]
    locations = sorted(
        f"{m.name}  (project: {getattr(m, 'project_name', '?')}, id: {m.id})" for m in matches
    )
    raise AmbiguousNameError(
        f"'{name}' matches {len(matches)} {kind}s. Narrow with --project:\n  "
        + "\n  ".join(locations)
    )


def resolve_workbook(server, name: str, project: Optional[str] = None, index: Optional[ProjectIndex] = None):
    if index is None and project:
        index = ProjectIndex.load(server)
    return _pick(_filtered(server.workbooks, name), name, "workbook", project, index)


def resolve_datasource(server, name: str, project: Optional[str] = None, index: Optional[ProjectIndex] = None):
    if index is None and project:
        index = ProjectIndex.load(server)
    return _pick(_filtered(server.datasources, name), name, "datasource", project, index)


def resolve_user(server, name: str):
    matches = _filtered(server.users, name)
    if not matches:
        raise ResolutionError(f"No user named '{name}'.")
    if len(matches) > 1:
        raise AmbiguousNameError(f"'{name}' matches {len(matches)} users; use a unique username.")
    return matches[0]


def workbooks_in(server, project_ids: Iterable[str]) -> dict[str, list]:
    """Group all workbooks on the site by project id (only ids requested)."""
    wanted = set(project_ids)
    out: dict[str, list] = {pid: [] for pid in wanted}
    for wb in _all(server.workbooks):
        if wb.project_id in wanted:
            out[wb.project_id].append(wb)
    return out


def datasources_in(server, project_ids: Iterable[str]) -> dict[str, list]:
    wanted = set(project_ids)
    out: dict[str, list] = {pid: [] for pid in wanted}
    for ds in _all(server.datasources):
        if ds.project_id in wanted:
            out[ds.project_id].append(ds)
    return out
