"""`tab-cli job` — inspect background jobs (extract refreshes, etc.)."""

from __future__ import annotations

import click
import tableauserverclient as TSC

from .. import output
from ..cli import pass_app


@click.group()
def job():
    """List and wait on background jobs."""


@job.command("list")
@click.option("--limit", type=int, default=25, help="Maximum jobs to show.")
@pass_app
def list_jobs(app, limit):
    """List recent background jobs."""
    server = app.connect()
    rows = []
    for j in TSC.Pager(server.jobs):
        rows.append(
            (
                j.id,
                getattr(j, "job_type", "") or "",
                _status(j),
                str(getattr(j, "created_at", "") or "")[:19],
                str(getattr(j, "ended_at", "") or "")[:19],
            )
        )
        if len(rows) >= limit:
            break
    if app.as_json:
        output.emit_json(
            [{"id": i, "type": t, "status": s, "created": c, "ended": e} for i, t, s, c, e in rows]
        )
        return
    output.table(["Id", "Type", "Status", "Created", "Ended"], rows, title="Jobs")


@job.command()
@click.argument("job_id")
@pass_app
def wait(app, job_id):
    """Block until JOB_ID finishes."""
    server = app.connect()
    output.info(f"Waiting for job {job_id} …")
    finished = server.jobs.wait_for_job(job_id)
    output.success(f"Job {job_id} finished (status: {_status(finished)}).")


def _status(j) -> str:
    code = getattr(j, "finish_code", None)
    if code is None:
        return "Running/Pending"
    return {"0": "Success", "1": "Failed", "2": "Cancelled"}.get(str(code), str(code))
