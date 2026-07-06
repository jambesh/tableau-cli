"""`tab-cli view` — export view images and data."""

from __future__ import annotations

import os

import click
import tableauserverclient as TSC

from .. import output
from ..cli import pass_app
from ..errors import AmbiguousNameError, ResolutionError


def _resolve_view(server, name, workbook=None):
    matches = []
    for v in TSC.Pager(server.views):
        if v.name != name:
            continue
        if workbook and (v.workbook_id or "") and getattr(v, "workbook_id", None):
            # ViewItem doesn't always expose workbook name; match on id via lookup below.
            pass
        matches.append(v)
    if workbook:
        wb_ids = {w.id for w in TSC.Pager(server.workbooks) if w.name == workbook}
        matches = [m for m in matches if m.workbook_id in wb_ids]
    if not matches:
        scope = f" in workbook '{workbook}'" if workbook else ""
        raise ResolutionError(f"No view named '{name}'{scope}.")
    if len(matches) > 1:
        locs = sorted(f"{m.name} (id: {m.id})" for m in matches)
        raise AmbiguousNameError(
            f"'{name}' matches {len(matches)} views. Narrow with --workbook:\n  " + "\n  ".join(locs)
        )
    return matches[0]


@click.group()
def view():
    """List views and export them as image / PDF / CSV."""


@view.command("list")
@click.option("--workbook", help="Only views in this workbook.")
@pass_app
def list_views(app, workbook):
    """List views (optionally within a --workbook)."""
    server = app.connect()
    wb_names = {}
    if workbook:
        wb_ids = {w.id for w in TSC.Pager(server.workbooks) if w.name == workbook}
    rows = []
    for v in TSC.Pager(server.views):
        if workbook and v.workbook_id not in wb_ids:
            continue
        rows.append((v.name, v.id, v.content_url or ""))
    rows.sort(key=lambda r: r[0].lower())
    if app.as_json:
        output.emit_json([{"name": n, "id": i, "content_url": c} for n, i, c in rows])
        return
    output.table(["View", "Id", "Content URL"], rows, title="Views")


@view.command("download-image")
@click.argument("name")
@click.option("--workbook", help="Disambiguate by workbook name.")
@click.option("-o", "--output", "dest", default=".", help="Destination file or directory.")
@click.option(
    "--resolution",
    type=click.Choice(["high", "standard"]),
    default="high",
    help="Image resolution.",
)
@pass_app
def download_image(app, name, workbook, dest, resolution):
    """Export view NAME as a PNG image."""
    server = app.connect()
    v = _resolve_view(server, name, workbook)
    req = TSC.ImageRequestOptions(
        imageresolution=(
            TSC.ImageRequestOptions.Resolution.High
            if resolution == "high"
            else TSC.ImageRequestOptions.Resolution.Standard
        )
    )
    server.views.populate_image(v, req)
    path = _target(dest, name, "png")
    with open(path, "wb") as fh:
        fh.write(v.image)
    output.success(f"Saved image of '{v.name}' → {path}")


@view.command("download-pdf")
@click.argument("name")
@click.option("--workbook", help="Disambiguate by workbook name.")
@click.option("-o", "--output", "dest", default=".", help="Destination file or directory.")
@pass_app
def download_pdf(app, name, workbook, dest):
    """Export view NAME as a PDF."""
    server = app.connect()
    v = _resolve_view(server, name, workbook)
    server.views.populate_pdf(v, TSC.PDFRequestOptions())
    path = _target(dest, name, "pdf")
    with open(path, "wb") as fh:
        fh.write(v.pdf)
    output.success(f"Saved PDF of '{v.name}' → {path}")


@view.command("download-csv")
@click.argument("name")
@click.option("--workbook", help="Disambiguate by workbook name.")
@click.option("-o", "--output", "dest", default=".", help="Destination file or directory.")
@pass_app
def download_csv(app, name, workbook, dest):
    """Export the summary data of view NAME as CSV."""
    server = app.connect()
    v = _resolve_view(server, name, workbook)
    server.views.populate_csv(v, TSC.CSVRequestOptions())
    path = _target(dest, name, "csv")
    with open(path, "wb") as fh:
        for chunk in v.csv:
            fh.write(chunk)
    output.success(f"Saved CSV of '{v.name}' → {path}")


def _target(dest: str, name: str, ext: str) -> str:
    safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in name).strip() or "view"
    if os.path.isdir(dest):
        return os.path.join(dest, f"{safe}.{ext}")
    return dest
