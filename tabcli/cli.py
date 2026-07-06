"""tab-cli entry point: the root command group and shared context."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Optional

import click

from . import output
from .config import Config
from .errors import TabCliError
from .session import Session

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"], "max_content_width": 100}


@dataclass
class AppContext:
    """Shared state threaded through every command via ``click`` context."""

    as_json: bool = False
    _config: Optional[Config] = None
    _session: Optional[Session] = None

    @property
    def config(self) -> Config:
        if self._config is None:
            self._config = Config.load()
        return self._config

    @property
    def session(self) -> Session:
        if self._session is None:
            self._session = Session(self.config)
        return self._session

    def connect(self):
        """Return a signed-in :class:`TSC.Server`."""
        return self.session.connect()


pass_app = click.make_pass_decorator(AppContext, ensure=True)


class TabCliGroup(click.Group):
    """Group that renders expected errors as clean one-liners."""

    def invoke(self, ctx: click.Context):
        try:
            return super().invoke(ctx)
        except TabCliError as exc:
            output.error(str(exc))
            ctx.exit(1)
        except click.ClickException:
            raise
        except KeyboardInterrupt:
            output.error("Interrupted.")
            ctx.exit(130)


@click.group(cls=TabCliGroup, context_settings=CONTEXT_SETTINGS)
@click.version_option(package_name="tab-cli", prog_name="tab-cli")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON on stdout.")
@click.option("--no-color", is_flag=True, help="Disable colored output.")
@click.pass_context
def cli(ctx: click.Context, as_json: bool, no_color: bool) -> None:
    """tab-cli — a friendlier command line for Tableau Server / Cloud.

    Sign in once with `tab-cli login`, then manage projects, workbooks and
    data sources: browse a project as a tree (`tab-cli ls`), download content,
    move or rename items, change ownership, and refresh extracts.
    """
    output.configure(no_color=no_color)
    ctx.obj = AppContext(as_json=as_json)


# ---- register sub-commands ------------------------------------------------ #
from .commands import auth, datasource, group, job, ls, project, view, workbook  # noqa: E402

cli.add_command(auth.login)
cli.add_command(auth.logout)
cli.add_command(auth.whoami)
cli.add_command(auth.status)
cli.add_command(ls.ls)
cli.add_command(project.project)
cli.add_command(workbook.workbook)
cli.add_command(datasource.datasource)
cli.add_command(view.view)
cli.add_command(job.job)
cli.add_command(group.group)


def main(argv: Optional[list[str]] = None) -> int:
    try:
        return cli.main(args=argv, standalone_mode=False) or 0
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except (click.exceptions.Abort, KeyboardInterrupt):
        output.error("Aborted.")
        return 130
    except SystemExit as exc:  # in case anything raises it directly
        return int(exc.code or 0)


if __name__ == "__main__":
    sys.exit(main())
