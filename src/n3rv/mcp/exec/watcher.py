"""File watcher with debounce for n3rv-exec — twin to CodeGraphWatcher."""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from n3rv.mcp.exec.registry import ALL_CONFIGS as _WATCH_CONFIGS
from n3rv.mcp.exec.registry import ALL_EXTS as _WATCH_EXTS

logger = logging.getLogger("n3rv.mcp.exec")


def _content_hash(data: bytes) -> str:
    """XXH3 fallback via sha256[:16] — same as code_graph_store content_hash."""
    try:
        import xxhash  # type: ignore[import-not-found]

        return xxhash.xxh3_64_hexdigest(data)[:16]
    except Exception:
        return hashlib.sha256(data).hexdigest()[:16]


def _should_watch(path: Path) -> bool:
    """Check if path is a relevant exec file."""
    if path.name in _WATCH_CONFIGS:
        return True
    return path.suffix in _WATCH_EXTS


def _resolve_debounce() -> int:
    """Resolve debounce ms from env, clamped to [100, 60000]."""
    raw = os.environ.get("N3RV_EXEC_DEBOUNCE_MS", "500")
    try:
        ms = int(raw)
    except ValueError:
        ms = 500
    return max(100, min(ms, 60000))


class _DebouncedExecHandler(FileSystemEventHandler):
    """Debounced handler that marks pending after quiet window."""

    def __init__(
        self,
        debounce_s: float,
        on_change,
        executor: ThreadPoolExecutor,
    ) -> None:
        super().__init__()
        self._debounce_s = debounce_s
        self._on_change = on_change
        self._executor = executor
        self._timer: threading.Timer | None = None
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def _schedule(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._debounce_s, self._fire)
        self._timer.daemon = True
        self._timer.start()

    def _fire(self) -> None:
        self._timer = None
        snapshot: set[str] = set()
        with self._lock:
            snapshot, self._pending = self._pending, set()
        if snapshot:
            logger.info("Exec watcher: %d change(s) scheduled", len(snapshot))
            self._executor.submit(self._on_change, snapshot)

    def _enqueue(self, path: str) -> None:
        with self._lock:
            self._pending.add(path)
        self._schedule()

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        self._enqueue(event.src_path)

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        self._enqueue(event.src_path)

    def on_deleted(self, event) -> None:
        if event.is_directory:
            return
        self._enqueue(event.src_path)

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        self._enqueue(event.src_path)


class ExecWatcher:
    """Debounced watcher that tracks pending exec files via XXH3 + mtime.

    Exposes ``pending`` for staleness banner (twin to CodeGraphWatcher.pending).
    """

    def __init__(
        self,
        project_root: Path,
        debounce_ms: int | None = None,
        store=None,  # ExecStore | None — avoid circular import type
    ) -> None:
        self.project_root = project_root.resolve()
        self.store = store
        if debounce_ms is None:
            debounce_ms = _resolve_debounce()
        self.debounce_s = max(0.1, min(debounce_ms / 1000.0, 60.0))
        self.pending: set[str] = set()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="exec-watcher")
        self._observer: Observer | None = None
        self._running = False
        self._lock = threading.Lock()

    def _hash_file(self, path: Path) -> str | None:
        """Compute XXH3/sha256 for file, or None on error."""
        try:
            return _content_hash(path.read_bytes())
        except Exception:
            return None

    def _handle_changed(self, changed_files: set[str]) -> None:
        """Mark changed files as pending; update store XXH3 if present."""
        with self._lock:
            for f in changed_files:
                p = Path(f)
                try:
                    rel = str(p.relative_to(self.project_root))
                except ValueError:
                    rel = f
                if _should_watch(Path(rel)):
                    self.pending.add(rel)
                # Update store mtime+xxh3 if we can read file
                if self.store is not None:
                    try:
                        abs_path = self.project_root / rel if not Path(rel).is_absolute() else Path(rel)
                        if abs_path.is_file():
                            mtime = abs_path.stat().st_mtime
                            h = self._hash_file(abs_path)
                            if h is not None:
                                self.store.upsert_file_state(rel, mtime, h)
                    except Exception:
                        pass
        # Clear pending for files that no longer exist? keep them as stale until reconciled
        logger.debug("Exec watcher pending: %s", sorted(self.pending))

    def mark_dirty(self, file_path: str) -> None:
        """Manually mark a file as pending (for tests / --changed)."""
        with self._lock:
            self.pending.add(file_path)

    def clear_pending(self, file_path: str) -> None:
        """Clear a file from pending."""
        with self._lock:
            self.pending.discard(file_path)

    def get_dirty_files(self) -> list[str]:
        """Return watched files that are dirty vs stored XXH3."""
        dirty: list[str] = []
        if self.store is None:
            return sorted(self.pending)
        # If pending non-empty, those are dirty
        with self._lock:
            if self.pending:
                return sorted(self.pending)
        # Otherwise compare on-disk hash vs stored — use all watched extensions (20+ langs)
        for ext in _WATCH_EXTS:
            for p in self.project_root.rglob(f"*{ext}"):
                try:
                    rel = str(p.relative_to(self.project_root))
                except ValueError:
                    continue
                if not _should_watch(p):
                    continue
                state = self.store.get_file_state(rel)
                try:
                    mtime = p.stat().st_mtime
                    h = self._hash_file(p)
                except Exception:
                    continue
                if state is None or state["xxh3"] != h or state["mtime"] != mtime:
                    dirty.append(rel)
        # Also check config files
        for cfg in _WATCH_CONFIGS:
            p = self.project_root / cfg
            if p.is_file():
                rel = cfg
                state = self.store.get_file_state(rel)
                try:
                    mtime = p.stat().st_mtime
                    h = self._hash_file(p)
                except Exception:
                    continue
                if state is None or state["xxh3"] != h or state["mtime"] != mtime:
                    dirty.append(rel)
        return sorted(set(dirty))

    def start(self) -> None:
        """Start the watcher. Idempotent."""
        if self._running:
            return
        if os.environ.get("N3RV_EXEC_NO_WATCH", "").strip().lower() in ("1", "true", "yes"):
            logger.info("Exec watcher disabled via N3RV_EXEC_NO_WATCH")
            self._running = True
            return
        if os.environ.get("N3RV_CODE_GRAPH_NO_WATCH", "").strip().lower() in ("1", "true", "yes"):
            # Respect legacy flag too for test envs that disable watchers globally
            logger.info("Exec watcher disabled via N3RV_CODE_GRAPH_NO_WATCH")
            self._running = True
            return
        try:
            self._observer = Observer()
            handler = _DebouncedExecHandler(
                debounce_s=self.debounce_s,
                on_change=self._handle_changed,
                executor=self._executor,
            )
            self._observer.schedule(handler, str(self.project_root), recursive=True)
            self._observer.start()
            self._running = True
            logger.info("Exec watcher started on %s (debounce=%ss)", self.project_root, self.debounce_s)
        except Exception as exc:
            logger.warning("Exec watcher failed to start: %s", exc)
            self._running = True

    def stop(self) -> None:
        """Stop the watcher and shut down the executor. Idempotent."""
        if self._observer is not None and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._executor.shutdown(wait=False)
        self._running = False
        logger.info("Exec watcher stopped")

    def is_alive(self) -> bool:
        return self._running and self._observer is not None and self._observer.is_alive()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
