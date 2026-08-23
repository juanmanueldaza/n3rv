"""Template lockfile — SHA256 hash tracking for rendered files.

The lockfile (``.n3rverberage/template-lock.json``) records the hash of every
file rendered by ``n3rverberage init`` or ``n3rverberage update``. On subsequent
updates the lockfile is compared against the current on-disk hash to detect
drift — files modified by the user since the last render.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("n3rverberage.lockfile")

LOCKFILE_VERSION = 1
LOCKFILE_NAME = "template-lock.json"


def _sha256(path: Path) -> str:
    """Compute SHA256 of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lockfile_path(root: Path) -> Path:
    """Return the path to the template lockfile for *root*."""
    return root / ".n3rverberage" / LOCKFILE_NAME


def load_lockfile(root: Path) -> dict[str, Any]:
    """Load the lockfile, returning an empty dict if missing or corrupt."""
    path = lockfile_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load template lockfile: %s", exc)
        return {}


def save_lockfile(root: Path, entries: dict[str, Any]) -> None:
    """Save lockfile entries to disk."""
    path = lockfile_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "lockfile_version": LOCKFILE_VERSION,
        "schema_version": "1.0",
        "entries": entries,
    }
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def record_entry(
    output_path: Path,
    template_name: str,
    context_hash: str = "",
) -> dict[str, Any]:
    """Build a lockfile entry for a newly rendered file."""
    return {
        "sha256": _sha256(output_path),
        "template": template_name,
        "context_hash": context_hash,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def check_drift(root: Path, output_rel: str, current_hash: str) -> str | None:
    """Compare *current_hash* against the stored hash for *output_rel*.

    Returns ``None`` if no drift (file matches lockfile), or a short
    description of the mismatch.
    """
    lock = load_lockfile(root)
    entries = lock.get("entries", {})
    stored = entries.get(output_rel)
    if stored is None:
        return "not tracked"
    expected = stored.get("sha256")
    if expected is None:
        return "no hash stored"
    if current_hash != expected:
        return "hash mismatch (user-modified)"
    return None


def update_lockfile_entry(
    root: Path,
    output_rel: str,
    entry: dict[str, Any],
) -> None:
    """Add or update a single entry in the lockfile and persist."""
    lock = load_lockfile(root)
    entries: dict[str, Any] = lock.get("entries", {})
    entries[output_rel] = entry
    save_lockfile(root, entries)


def diff_lockfile(root: Path, rendered: dict[str, Path]) -> dict[str, str]:
    """Compare rendered files against lockfile, return drift descriptions.

    Args:
        root: Project root directory.
        rendered: Mapping of relative paths → rendered file paths.

    Returns:
        A dict mapping relative paths to drift descriptions.
        Empty dict means no drift detected.
    """
    lock = load_lockfile(root)
    entries = lock.get("entries", {})
    drift: dict[str, str] = {}

    for rel_path, abs_path in rendered.items():
        if not abs_path.is_file():
            drift[rel_path] = "file missing"
            continue
        reason = check_drift(root, rel_path, _sha256(abs_path))
        if reason is not None:
            drift[rel_path] = reason

    # Also report entries in lockfile that no longer exist as rendered
    for rel_path in entries:
        if rel_path not in rendered:
            drift[rel_path] = "not in current manifest"

    return drift
