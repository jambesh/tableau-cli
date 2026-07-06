"""Terminal rendering helpers built on :mod:`rich`.

Keeping all presentation here means the command modules stay focused on Tableau
logic, and it gives us one place to honor ``--json`` / ``--no-color`` globally.
"""

from __future__ import annotations

import json as _json
import sys
from typing import Any, Iterable, Optional

from rich.console import Console
from rich.table import Table
from rich.tree import Tree

# stderr is used for status/errors so that stdout stays pipe-friendly.
_out = Console()
_err = Console(stderr=True)


def configure(no_color: bool = False) -> None:
    global _out, _err
    _out = Console(no_color=no_color)
    _err = Console(stderr=True, no_color=no_color)


def print(*args: Any, **kwargs: Any) -> None:  # noqa: A001 - intentional shadow
    _out.print(*args, **kwargs)


def info(message: str) -> None:
    _err.print(f"[cyan]{message}[/cyan]")


def success(message: str) -> None:
    _err.print(f"[green]✓[/green] {message}")


def warn(message: str) -> None:
    _err.print(f"[yellow]![/yellow] {message}")


def error(message: str) -> None:
    _err.print(f"[red]✗ {message}[/red]")


def emit_json(payload: Any) -> None:
    """Machine-readable output on stdout."""
    sys.stdout.write(_json.dumps(payload, indent=2, default=str) + "\n")


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
def table(columns: list[str], rows: Iterable[Iterable[Any]], title: Optional[str] = None) -> None:
    t = Table(title=title, header_style="bold", show_edge=True, expand=False)
    for col in columns:
        t.add_column(col, overflow="fold")
    count = 0
    for row in rows:
        t.add_row(*[("" if c is None else str(c)) for c in row])
        count += 1
    if count == 0:
        info("No items found.")
        return
    _out.print(t)


# --------------------------------------------------------------------------- #
# Project tree
# --------------------------------------------------------------------------- #
_ICON_PROJECT = "\U0001F4C1"  # folder
_ICON_WORKBOOK = "\U0001F4CA"  # bar chart
_ICON_DATASOURCE = "\U0001F5C3️"  # card index / file box


def render_tree(root_label: str, builder) -> None:
    """``builder(node)`` populates ``node`` with children recursively."""
    tree = Tree(f"{_ICON_PROJECT} [bold]{root_label}[/bold]")
    builder(tree)
    _out.print(tree)


def add_project_node(parent: Tree, name: str) -> Tree:
    return parent.add(f"{_ICON_PROJECT} [bold blue]{name}[/bold blue]")


def add_workbook_node(parent: Tree, name: str, extra: str = "") -> None:
    suffix = f" [dim]{extra}[/dim]" if extra else ""
    parent.add(f"{_ICON_WORKBOOK} [green]{name}[/green]{suffix}")


def add_datasource_node(parent: Tree, name: str, extra: str = "") -> None:
    suffix = f" [dim]{extra}[/dim]" if extra else ""
    parent.add(f"{_ICON_DATASOURCE} [magenta]{name}[/magenta]{suffix}")
