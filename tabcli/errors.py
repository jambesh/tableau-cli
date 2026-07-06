"""Exception types used across tab-cli.

``TabCliError`` is caught at the CLI boundary and rendered as a clean, single
line error rather than a Python traceback.
"""

from __future__ import annotations


class TabCliError(Exception):
    """Base class for expected, user-facing errors."""


class NotLoggedInError(TabCliError):
    """No usable credentials/session are available."""

    def __init__(self, message: str = "Not logged in. Run `tab-cli login` first.") -> None:
        super().__init__(message)


class ResolutionError(TabCliError):
    """A named resource could not be resolved to exactly one object."""


class AmbiguousNameError(ResolutionError):
    """A name matched more than one resource; the caller must disambiguate."""
