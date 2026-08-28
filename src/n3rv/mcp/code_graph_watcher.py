"""File watcher with debounce for code-graph auto-sync."""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from n3rv.mcp.code_graph_service import CodeGraphService

logger = logging.getLogger("n3rv.mcp.code_graph")


class _DebouncedEventHandler(FileSystemEventHandler):
    """Debounced handler that fires only after quiet window."""

    def __init__(
        self,
        debounce_s: float,
        on_change,
        executor: ThreadPoolExecutor,
        service: CodeGraphService,
    ) -> None:
        super().__init__()
        self._debounce_s = debounce_s
        self._on_change = on_change
        self._executor = executor
        self._service = service
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
            logger.info("CodeGraph watcher: %d change(s) scheduled", len(snapshot))
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


class CodeGraphWatcher:
    """Debounced file watcher that keeps the code graph fresh.

    Starts a ``watchdog.observers.Observer`` on ``project_root`` and debounces
    filesystem events through a single ``ThreadPoolExecutor`` so the MCP event
    loop is never blocked.  ``pending`` is exposed for staleness banner logic.
    """

    def __init__(
        self,
        project_root: Path,
        service: CodeGraphService,
        debounce_ms: int = 2000,
    ) -> None:
        self.project_root = project_root.resolve()
        self.service = service
        self.debounce_s = max(0.1, min(debounce_ms / 1000.0, 60.0))
        self.pending: set[str] = set()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cg-watcher")
        self._observer: Observer | None = None
        self._running = False
        self._lock = threading.Lock()

    def _index_changed(self, changed_files: set[str]) -> None:
        """Re-index changed files and update pending set."""
        # Track changed files as pending until re-index completes
        with self._lock:
            self.pending.update(changed_files)
        try:
            stats = self.service.index()
            logger.info("CodeGraph watcher index: %s", stats)
        except Exception as exc:
            logger.warning("CodeGraph watcher index failed: %s", exc)
        # Index done; clear pending for files that still exist on disk
        with self._lock:
            current = {str(p.relative_to(self.project_root)) for p in self.project_root.rglob("*.py")}
            self.pending.difference_update(current)

    def start(self) -> None:
        """Start the watcher. Idempotent."""
        if self._running:
            return
        # Respect env disable flag
        if os.environ.get("N3RV_CODE_GRAPH_NO_WATCH", "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            logger.info("CodeGraph watcher disabled via N3RV_CODE_GRAPH_NO_WATCH")
            self._running = True
            return
        try:
            self._observer = Observer()
            handler = _DebouncedEventHandler(
                debounce_s=self.debounce_s,
                on_change=self._index_changed,
                executor=self._executor,
                service=self.service,
            )
            self._observer.schedule(handler, str(self.project_root), recursive=True)
            self._observer.start()
            self._running = True
            logger.info(
                "CodeGraph watcher started on %s (debounce=%ss)",
                self.project_root,
                self.debounce_s,
            )
        except Exception as exc:
            logger.warning("CodeGraph watcher failed to start: %s", exc)
            self._running = True  # degrade gracefully

    def stop(self) -> None:
        """Stop the watcher and shut down the executor. Idempotent."""
        if self._observer is not None and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._executor.shutdown(wait=False)
        self._running = False
        logger.info("CodeGraph watcher stopped")

    def is_alive(self) -> bool:
        return self._running and self._observer is not None and self._observer.is_alive()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


def _resolve_debounce() -> int:
    """Resolve debounce ms from env, clamped to [100, 60000]."""
    raw = os.environ.get("N3RV_CODE_GRAPH_DEBOUNCE_MS", "2000")
    try:
        ms = int(raw)
    except ValueError:
        ms = 2000
    return max(100, min(ms, 60000))
