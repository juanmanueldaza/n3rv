"""Resolve the n3rv executable path written into generated files."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def resolve_n3rv_binary() -> str | None:
    """Return the n3rv executable to bake into generated files.

    The binary installed next to the running interpreter is preferred, because
    it is guaranteed to match the interpreter that renders the file.

    Resolving through PATH instead can bake whatever happens to be first there
    into a systemd unit: a shim, an alias, or a wrapper. That path is read back
    long after the PATH that produced it has changed, so the unit keeps working
    only by accident. A shim that has since stopped resolving (for example a
    version manager with no version set) leaves a unit that cannot start.
    """
    sibling = Path(sys.executable).parent / "n3rv"
    if sibling.is_file() and os.access(sibling, os.X_OK):
        return str(sibling)
    return shutil.which("n3rv")
