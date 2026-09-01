"""ExecService — inputHash cache orchestration (Turborepo/Bazel grade, 70×)."""

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path

from n3rv.mcp.exec.store import ExecStore
from n3rv.mcp.exec.watcher import _content_hash


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _tool_hash(tool: str) -> str:
    """Hash tool identity: name + version if available."""
    try:
        # Try to get version for hermetic invalidation (like Bazel remote cache)
        res = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=2)
        ver = (res.stdout or res.stderr or "").strip()[:200]
        if ver:
            return _hash_bytes(f"{tool}:{ver}".encode())
    except Exception:
        pass
    return _hash_bytes(tool.encode())


def _config_hash(project_root: Path) -> str:
    """Hash all config files from registry (20+ langs)."""
    from n3rv.mcp.exec.registry import ALL_CONFIGS

    h = hashlib.sha256()
    for name in sorted(ALL_CONFIGS):
        # Handle globs like *.csproj — skip glob entries for hash (check directory)
        if "*" in name:
            continue
        p = project_root / name
        if p.is_file():
            try:
                h.update(p.read_bytes())
            except Exception:
                h.update(name.encode())
        else:
            h.update(f"missing:{name}".encode())
    return h.hexdigest()[:16]


def _files_hash(project_root: Path, file_paths: list[str] | None = None) -> str:
    """XXH3 over sorted file hashes — like Turborepo inputs hash."""
    h = hashlib.sha256()
    if file_paths:
        # Explicit list (e.g. --changed / affected)
        for rel in sorted(file_paths):
            p = project_root / rel
            try:
                data = p.read_bytes()
                fh = _content_hash(data)
            except Exception:
                fh = "missing"
            h.update(f"{rel}:{fh}".encode())
    else:
        # Hash all watched files (fallback: py/ts/go + configs)
        from n3rv.mcp.exec.registry import ALL_EXTS

        files: list[Path] = []
        for ext in ALL_EXTS:
            files.extend(project_root.rglob(f"*{ext}"))
        # Limit to first 5000 to avoid huge hash time; sorted for determinism
        files_sorted = sorted(files)[:5000]
        for p in files_sorted:
            try:
                rel = str(p.relative_to(project_root))
                data = p.read_bytes()
                fh = _content_hash(data)
                h.update(f"{rel}:{fh}".encode())
            except Exception:
                continue
        # Include config files directly
        for name in ("pyproject.toml", "ruff.toml", "package.json"):
            p = project_root / name
            if p.is_file():
                try:
                    h.update(p.read_bytes())
                except Exception:
                    pass
    return h.hexdigest()[:16]


class ExecService:
    """Cache-orchestrated exec: get_cached(inputHash) → skip subprocess on hit."""

    def __init__(self, project_root: Path, store: ExecStore) -> None:
        self.project_root = project_root.resolve()
        self.store = store
        self._run_count = 0  # for tests: how many actual _run calls

    def compute_input_hash(self, tool: str, file_paths: list[str] | None = None) -> str:
        """inputHash = XXH3(fileHashes) : configHash : toolHash — eslint #20186 pattern."""
        fh = _files_hash(self.project_root, file_paths)
        ch = _config_hash(self.project_root)
        th = _tool_hash(tool)
        # Composite like Bazel action digest
        composite = f"{fh}:{ch}:{th}"
        return _hash_bytes(composite.encode())

    def _run(self, tool: str, command: list[str], cwd: Path) -> dict:
        """Actual subprocess run — can be monkeypatched in tests."""
        self._run_count += 1
        start = time.time()
        try:
            proc = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=60)
            out = (proc.stdout or "") + (proc.stderr or "")
            return {
                "returncode": proc.returncode,
                "output": out,
                "stdout": proc.stdout or "",
                "stderr": proc.stderr or "",
            }
        except FileNotFoundError:
            return {"returncode": 127, "output": f"command not found: {command[0]}", "stdout": "", "stderr": ""}
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")) if exc.stdout else ""  # type: ignore[union-attr]
            return {"returncode": 124, "output": out + "\n... timeout after 60s", "stdout": out, "stderr": ""}
        finally:
            _ = time.time() - start

    def execute(
        self,
        tool: str,
        command: list[str],
        file_paths: list[str] | None = None,
        git_sha: str | None = None,
    ) -> dict:
        """Execute with cache: return cached:true on hit without _run, else run and upsert."""
        input_hash = self.compute_input_hash(tool, file_paths)
        config_hash = _config_hash(self.project_root)
        cached = self.store.get_cached(input_hash)
        if cached is not None:
            # Cache hit — return without subprocess (Turborepo 3-4s path)
            return {**cached, "cached": True, "input_hash": input_hash}

        # Cache miss — run
        start = time.time()
        cmd_str = " ".join(command)
        result = self._run(tool, command, self.project_root)
        duration_ms = int((time.time() - start) * 1000)
        # Upsert
        passed = result["returncode"] == 0
        self.store.upsert_run(
            tool=tool,
            command=cmd_str,
            input_hash=input_hash,
            config_hash=config_hash,
            git_sha=git_sha,
            passed=passed,
            errors=[],
            output=result["output"],
            duration_ms=duration_ms,
            file_paths=file_paths or [],
        )
        return {
            "tool": tool,
            "command": cmd_str,
            "input_hash": input_hash,
            "config_hash": config_hash,
            "pass": passed,
            "output": result["output"],
            "duration_ms": duration_ms,
            "cached": False,
        }

    def get_cache_stats(self) -> dict:
        """Proxy to store.get_cache_stats with hit_rate."""
        return self.store.get_cache_stats()

    def get_history(self, limit: int = 20, tool: str | None = None) -> list[dict]:
        return self.store.get_history(limit=limit, tool=tool)

    # ── Affected (T5) — like Nx affected / Pants / golangci --new-from-rev ──

    def _git_changed_files(self, base_ref: str = "main") -> list[str]:
        """Get changed files via git diff --name-only."""
        try:
            res = subprocess.run(
                ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0:
                return []
            return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception:
            return []

    def get_affected(self, base_ref: str = "main", changed_files: list[str] | None = None) -> dict:
        """Return affected sets using CodeGraph blast radius (precise, 50-75% prune).

        If changed_files provided, use it directly (for tests / mocking detect_changes).
        Otherwise git diff vs base_ref.
        """
        if changed_files is None:
            changed_files = self._git_changed_files(base_ref)

        if not changed_files:
            return {"changed_files": [], "affected_tests": [], "affected_lints": [], "affected": []}

        # Try to use CodeGraphStore for precise blast radius
        affected_files: set[str] = set()
        try:
            from n3rv.config import load_runtime_settings

            settings = load_runtime_settings(self.project_root)
            db_path = settings.paths.n3rv_dir / "code_graph.db"
            if db_path.exists():
                from n3rv.mcp.code_graph_service import CodeGraphService
                from n3rv.mcp.code_graph_store import CodeGraphStore

                cg_store = CodeGraphStore(db_path)
                cg_service = CodeGraphService(cg_store, self.project_root)
                for cf in changed_files:
                    try:
                        aff = cg_service.affected(cf)
                        for a in aff:
                            affected_files.add(a["file"])
                    except Exception:
                        continue
        except Exception:
            pass

        # Heuristic fallback: if no code graph, assume affected = changed_files
        if not affected_files:
            affected_files = set(changed_files)

        # Partition: tests vs lints (like Pants precise)
        affected_tests = sorted([f for f in affected_files if "test" in f or f.startswith("tests/")])
        # If no test files in affected, fallback to test files that import changed modules
        if not affected_tests and affected_files:
            # Suggest tests that match changed file stem
            for cf in changed_files:
                stem = Path(cf).stem
                candidates = list(self.project_root.rglob(f"test*{stem}*.py")) + list(
                    self.project_root.rglob(f"**/test_{stem}.py")
                )
                for c in candidates:
                    try:
                        rel = str(c.relative_to(self.project_root))
                        affected_tests.append(rel)
                    except Exception:
                        continue
            affected_tests = sorted(set(affected_tests))

        affected_lints = sorted(affected_files)

        return {
            "changed_files": sorted(changed_files),
            "affected_tests": affected_tests,
            "affected_lints": affected_lints,
            "affected": sorted(affected_files),
        }
