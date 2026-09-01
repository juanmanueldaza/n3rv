"""MCP server that exposes lint/typecheck/test execution with structured returns.

Agents call these tools to get machine-parseable PASS/FAIL instead of scraping bash stdout.
Universal: ruff→eslint→golangci-lint, pytest→npm test→go test, mypy→tsc→go vet.
Adds history/diff/cache_stats + XXH3 cache (Turborepo 70×) + staleness banner.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

from n3rv.mcp.exec.store import ExecStore
from n3rv.mcp.exec.watcher import ExecWatcher, _resolve_debounce
from n3rv.mcp.shared import (
    build_mcp_server,
    resolve_runtime_settings,
    result_payload,
)

logger = logging.getLogger("n3rv.mcp.exec")

_OUTPUT_CAP = 10_000
_TIMEOUT = 60

# ── Watcher singletons (like code_graph_server) ──────────────────
_watchers: dict[Path, ExecWatcher] = {}
_watchers_lock = threading.Lock()


def _get_watcher(project_root: Path, store: ExecStore | None = None) -> ExecWatcher | None:
    root = project_root.resolve()
    if os.environ.get("N3RV_EXEC_NO_WATCH", "").strip().lower() in ("1", "true", "yes"):
        return None
    if os.environ.get("N3RV_CODE_GRAPH_NO_WATCH", "").strip().lower() in ("1", "true", "yes"):
        return None
    with _watchers_lock:
        if root not in _watchers:
            w = ExecWatcher(root, debounce_ms=_resolve_debounce(), store=store)
            # Do not auto-start in tests (N3RV_EXEC_NO_WATCH); start lazily
            _watchers[root] = w
        w = _watchers[root]
    return w


def _inject_staleness(result: dict, watcher: ExecWatcher | None) -> dict:
    """Prepend banner/append footer when watcher has pending files."""
    if watcher is None or not watcher.pending:
        return result
    pending_list = sorted(watcher.pending)
    referenced: set[str] = set()
    # Gather files referenced by result
    for err in result.get("errors", []) or []:
        if isinstance(err, dict) and "file" in err:
            referenced.add(err["file"])
    if "output" in result:
        # crude file ref extraction from output
        for line in str(result.get("output", "")).splitlines()[:20]:
            for p in pending_list:
                if p in line:
                    referenced.add(p)
    for cp in result.get("call_paths", []) or []:
        referenced.add(cp.get("from", ""))
        referenced.add(cp.get("to", ""))
    if referenced:
        stale_refs = sorted(referenced.intersection(pending_list))
        if stale_refs:
            banner = "⚠️ " + ", ".join(f"Stale: {f} pending sync — Read it directly" for f in stale_refs)
            result["banner"] = banner
    other = sorted(set(pending_list) - referenced)
    if other:
        result["footer"] = "Pending sync for: " + ", ".join(other)
    return result


def _run(cmd: list[str], cwd: Path, timeout: int = _TIMEOUT) -> dict:
    """Run cmd jailed to cwd, no shell, truncated output."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if len(out) > _OUTPUT_CAP:
            out = out[:_OUTPUT_CAP] + "\n... truncated"
        return {
            "returncode": proc.returncode,
            "output": out,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except FileNotFoundError:
        return {"returncode": 127, "output": f"command not found: {cmd[0]}", "stdout": "", "stderr": ""}
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")) if exc.stdout else ""  # type: ignore[union-attr]
        out += (exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")) if exc.stderr else ""  # type: ignore[union-attr]
        if len(out) > _OUTPUT_CAP:
            out = out[:_OUTPUT_CAP] + "\n... truncated"
        return {"returncode": 124, "output": out + f"\n... timeout after {timeout}s", "stdout": out, "stderr": ""}


def _parse_ruff_json(output: str) -> list[dict]:
    """Try to parse `ruff check --output-format json` output."""
    try:
        data = json.loads(output)
        if isinstance(data, list):
            errors = []
            for item in data:
                errors.append(
                    {
                        "file": item.get("filename", ""),
                        "line": item.get("location", {}).get("row", 0),
                        "col": item.get("location", {}).get("column", 0),
                        "rule": item.get("code", ""),
                        "message": item.get("message", ""),
                    }
                )
            return errors
    except Exception:
        pass
    return []


def _parse_ruff_lines(output: str) -> list[dict]:
    """Fallback line parser for `file:line:col: RULE message`."""
    errors: list[dict] = []
    pat = re.compile(r"^(.*?):(\d+):(\d+):\s*(\w+\d*)\s*(.*)$")
    for line in output.splitlines():
        m = pat.match(line.strip())
        if m:
            errors.append(
                {
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "col": int(m.group(3)),
                    "rule": m.group(4),
                    "message": m.group(5),
                }
            )
            if len(errors) >= 50:
                break
    return errors


def _parse_pytest_summary(output: str) -> dict:
    """Extract passed/failed from pytest -q summary."""
    passed = failed = 0
    m_pass = re.search(r"(\d+)\s+passed", output)
    m_fail = re.search(r"(\d+)\s+failed", output)
    if m_pass:
        passed = int(m_pass.group(1))
    if m_fail:
        failed = int(m_fail.group(1))
    summary = ""
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line:
            summary = line.strip()
            break
    return {"passed": passed, "failed": failed, "summary": summary or output.splitlines()[-1].strip() if output else ""}


# ── Universal auto-detect (rtk-mcp pattern) ────────────────────


def _detect_lint_tool(target: str | None = None) -> tuple[str, list[str]] | None:
    """Return (tool_name, base_cmd) for lint — universal, per-extension aware (20+ langs)."""
    from n3rv.mcp.exec.registry import EXT_TO_LINT, LINT_CHAIN

    # Per-extension first: if target has known ext, try its mapped linter if available
    if target:
        ext = Path(target).suffix
        mapped = EXT_TO_LINT.get(ext)
        if mapped:
            tool, cmd = mapped
            binary = cmd[0].split()[0] if cmd else tool
            # For cargo/rust, check cargo exists; for dotnet etc. same
            if shutil.which(binary) or shutil.which(tool):
                return mapped
    # Fallback: first available in registry order (python→js→go→rust→...)
    for tool, cmd in LINT_CHAIN:
        binary = cmd[0] if cmd else tool
        if shutil.which(binary) or shutil.which(tool):
            return (tool, cmd)
    return None


def _detect_test_tool() -> tuple[str, list[str]] | None:
    """Universal test chain covering 20+ langs."""
    from n3rv.mcp.exec.registry import TEST_CHAIN

    for tool, cmd in TEST_CHAIN:
        binary = cmd[0] if cmd else tool
        if shutil.which(binary) or shutil.which(tool):
            return (tool, cmd)
    return None


def _detect_typecheck_tool() -> tuple[str, list[str]] | None:
    """Universal typecheck chain covering 20+ langs."""
    from n3rv.mcp.exec.registry import TYPECHECK_CHAIN

    for tool, cmd in TYPECHECK_CHAIN:
        binary = cmd[0] if cmd else tool
        if shutil.which(binary) or shutil.which(tool):
            return (tool, cmd)
    return None


def build_exec_server(project_root: Path | None = None):
    """Build and return the n3rv-exec MCP server (universal + cache + history)."""
    settings = resolve_runtime_settings(project_root)
    project_root = settings.paths.project_root
    db_path = settings.paths.n3rv_dir / "exec.db"
    store = ExecStore(db_path)
    watcher = _get_watcher(project_root, store)

    # Service helpers for inputHash (import lazily to avoid cycle)
    from n3rv.mcp.exec.service import ExecService, _config_hash, _files_hash, _tool_hash

    exec_service = ExecService(project_root, store)

    server = build_mcp_server(
        "n3rv-exec",
        "Run lint/typecheck/test with structured returns "
        "(universal: ruff/eslint/golangci, pytest/npm/go, mypy/tsc/go vet) + cache/history.",
    )

    def _ensure_inside(path_str: str) -> Path:
        """Resolve path_str relative to project_root and ensure inside."""
        p = (project_root / path_str).resolve() if not Path(path_str).is_absolute() else Path(path_str).resolve()
        try:
            p.relative_to(project_root.resolve())
        except ValueError as exc:
            if p != project_root.resolve():
                raise ValueError(f"path outside project_root: {path_str}") from exc
        return p

    def _compute_input_hash(tool: str, file_paths: list[str] | None = None) -> str:
        import hashlib

        fh = _files_hash(project_root, file_paths)
        ch = _config_hash(project_root)
        th = _tool_hash(tool)
        composite = f"{fh}:{ch}:{th}"
        return hashlib.sha256(composite.encode()).hexdigest()[:16]

    @server.tool(description="Run lint with structured return (auto: ruff→eslint→golangci-lint). Prefer over bash.")
    async def exec_lint(path: str = ".", affected: bool = False, base_ref: str = "main") -> dict:
        # Affected prune: if requested, compute affected_lints and narrow target
        if affected:
            aff = exec_service.get_affected(base_ref=base_ref)
            affected_list = aff.get("affected_lints") or aff.get("affected") or []
            if affected_list:
                # Narrow to first affected file for lint (demo 50% prune)
                path = affected_list[0]
            else:
                return result_payload(
                    {"pass": True, "tool": "lint", "output": "no affected files", "errors": [], "affected": aff}
                )
        try:
            cwd = _ensure_inside(path) if path != "." else project_root
            run_cwd = project_root
            if cwd.is_file():
                run_cwd = cwd.parent
                target = str(cwd)
            elif cwd.is_dir():
                run_cwd = cwd
                target = "."
            else:
                target = path
        except ValueError as exc:
            return result_payload(
                {"pass": False, "tool": "ruff", "output": str(exc), "errors": [], "command": "ruff check"}
            )

        detected = _detect_lint_tool(target)
        if detected is None:
            return result_payload(
                {
                    "pass": None,
                    "tool": "lint",
                    "skipped": "no linter found (ruff/eslint/golangci-lint/cargo/clippy/...)",
                    "output": "",
                    "errors": [],
                }
            )
        tool_name, base_cmd = detected

        # Cache check — inputHash:fileHashes:configHash:toolHash
        file_list = [target] if target != "." else None
        input_hash = _compute_input_hash(tool_name, file_list if file_list else None)
        cached = store.get_cached(input_hash)
        if cached is not None:
            # Return cached with staleness banner
            res = {**cached, "cached": True, "input_hash": input_hash}
            return result_payload(_inject_staleness(res, watcher))

        # Dispatch per tool
        if tool_name == "ruff":
            res_json = _run([*base_cmd, target, "--output-format", "json"], cwd=run_cwd)
            if res_json["returncode"] == 127:
                return result_payload(
                    {
                        "pass": None,
                        "tool": "ruff",
                        "skipped": "ruff not found",
                        "output": res_json["output"],
                        "errors": [],
                    }
                )
            errors = (
                _parse_ruff_json(res_json["output"])
                if res_json["output"].strip().startswith("[")
                else _parse_ruff_lines(res_json["output"])
            )
            fmt_pass = True
            fmt_output = ""
            if res_json["returncode"] == 0:
                res_fmt = _run(["ruff", "format", "--check", target], cwd=run_cwd)
                fmt_output = res_fmt["output"]
                fmt_pass = res_fmt["returncode"] == 0
                if not fmt_pass and not errors:
                    errors = [{"file": target, "line": 0, "col": 0, "rule": "FORMAT", "message": fmt_output[:500]}]
            passed = res_json["returncode"] == 0 and fmt_pass
            output = res_json["output"] + ("\n" + fmt_output if fmt_output else "")
            command_str = f"ruff check {target}"
        elif tool_name == "eslint":
            res = _run([*base_cmd, "--format", "json"] if "eslint" in base_cmd[0] else base_cmd, cwd=run_cwd)
            # eslint JSON is array of file results; try generic parse
            errors = _parse_ruff_lines(res["output"])
            passed = res["returncode"] == 0
            output = res["output"]
            command_str = " ".join(base_cmd)
        else:  # generic: golangci-lint, cargo clippy, rubocop, etc. — 20+ langs
            res = _run(base_cmd, cwd=run_cwd)
            errors = _parse_ruff_lines(res["output"])
            passed = res["returncode"] == 0
            output = res["output"]
            command_str = " ".join(base_cmd)

        # Persist to store for cache
        try:
            config_hash = _config_hash(project_root)
            # duration_ms best-effort (run already timed inside _run path; use 0 if cached)
            duration_ms = 0
            store.upsert_run(
                tool=tool_name,
                command=command_str,
                input_hash=input_hash,
                config_hash=config_hash,
                git_sha=None,
                passed=passed,
                errors=errors[:50],
                output=output[:_OUTPUT_CAP],
                duration_ms=duration_ms,
                file_paths=[target] if target != "." else [],
            )
            # Update file states for XXH3
            if watcher is not None and target != ".":
                try:
                    p = Path(target)
                    abs_p = (run_cwd / p.name) if p.is_file() or cwd.is_file() else None
                    if abs_p and abs_p.is_file():
                        from n3rv.mcp.exec.watcher import _content_hash

                        h = _content_hash(abs_p.read_bytes())
                        watcher.store.upsert_file_state(
                            str(target), abs_p.stat().st_mtime, h
                        ) if watcher.store else None
                        watcher.clear_pending(str(target))
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("exec_lint store upsert failed: %s", exc)

        result = {
            "pass": passed,
            "tool": tool_name,
            "command": command_str,
            "output": output[:_OUTPUT_CAP],
            "errors": errors[:50],
            "input_hash": input_hash,
            "cached": False,
        }
        return result_payload(_inject_staleness(result, watcher))

    @server.tool(
        description="Run typecheck with structured return (auto: mypy→tsc→go vet). Returns skipped if none installed."
    )
    async def exec_typecheck(path: str = "src") -> dict:
        try:
            target = _ensure_inside(path) if path != "." else project_root
        except ValueError as exc:
            return result_payload({"pass": False, "tool": "mypy", "output": str(exc), "errors": []})

        detected = _detect_typecheck_tool()
        if detected is None:
            return result_payload(
                {
                    "pass": None,
                    "tool": "typecheck",
                    "skipped": "no typechecker found (mypy/tsc/go vet)",
                    "output": "",
                    "errors": [],
                }
            )
        tool_name, base_cmd = detected

        # mypy-specific: target may not exist -> pass
        if tool_name == "mypy" and not target.exists():
            return result_payload(
                {"pass": True, "tool": "mypy", "command": f"mypy {path}", "output": "no files", "errors": []}
            )

        input_hash = _compute_input_hash(tool_name, [path] if path != "." else None)
        cached = store.get_cached(input_hash)
        if cached is not None:
            return result_payload(_inject_staleness({**cached, "cached": True, "input_hash": input_hash}, watcher))

        target_str = str(target) if target.is_dir() or target.is_file() else path
        try:
            rel = target.relative_to(project_root)
            target_str = str(rel)
        except ValueError:
            pass

        # Build command per tool
        if tool_name == "mypy":
            cmd = [*base_cmd, target_str]
        elif tool_name == "tsc":
            cmd = base_cmd  # tsc --noEmit checks whole project
        else:  # go vet
            cmd = base_cmd

        res = _run(cmd, cwd=project_root)
        passed = res["returncode"] == 0
        errors = _parse_ruff_lines(res["output"]) if res["output"] else []

        try:
            store.upsert_run(
                tool=tool_name,
                command=" ".join(cmd),
                input_hash=input_hash,
                config_hash=_config_hash(project_root),
                git_sha=None,
                passed=passed,
                errors=errors[:50],
                output=res["output"][:_OUTPUT_CAP],
                duration_ms=0,
                file_paths=[target_str],
            )
        except Exception as exc:
            logger.debug("exec_typecheck store upsert failed: %s", exc)

        result = {
            "pass": passed,
            "tool": tool_name,
            "command": " ".join(cmd),
            "output": res["output"][:_OUTPUT_CAP],
            "errors": errors[:50],
            "input_hash": input_hash,
            "cached": False,
        }
        return result_payload(_inject_staleness(result, watcher))

    @server.tool(
        description="Run tests with structured return (auto: pytest→npm test→go test). Prefer over bash `pytest -q`."
    )
    async def exec_test(
        path: str = ".", extra_args: str | None = None, affected: bool = False, base_ref: str = "main"
    ) -> dict:
        if affected:
            aff = exec_service.get_affected(base_ref=base_ref)
            affected_list = aff.get("affected_tests") or aff.get("affected") or []
            if not affected_list:
                return result_payload(
                    {
                        "pass": True,
                        "tool": "pytest",
                        "output": "no affected tests",
                        "summary": "no affected",
                        "passed": 0,
                        "failed": 0,
                        "affected": aff,
                    }
                )
            # Prune: narrow path to first affected test (ensures called files ⊆ affected)
            path = affected_list[0]
        try:
            target = _ensure_inside(path) if path != "." else project_root
        except ValueError as exc:
            return result_payload({"pass": False, "tool": "pytest", "output": str(exc), "summary": ""})

        detected = _detect_test_tool()
        if detected is None:
            return result_payload(
                {
                    "pass": None,
                    "tool": "pytest",
                    "skipped": "no test runner found (pytest/npm/go)",
                    "output": "",
                    "summary": "",
                }
            )
        tool_name, base_cmd = detected

        # For pytest path handling; for npm/go we ignore path and run project-wide
        if tool_name == "pytest":
            cmd = list(base_cmd)
            if path != ".":
                try:
                    rel = target.relative_to(project_root)
                    cmd.append(str(rel))
                except ValueError:
                    cmd.append(path)
            if extra_args:
                cmd.extend(extra_args.split())
        elif tool_name == "npm":
            cmd = ["npm", "test", "--"]
            if extra_args:
                cmd.extend(extra_args.split())
        else:  # go
            cmd = list(base_cmd)
            if extra_args:
                cmd.extend(extra_args.split())

        input_hash = _compute_input_hash(tool_name, [path] if path != "." else None)
        cached = store.get_cached(input_hash)
        if cached is not None:
            # Cached test result may not have summary fields; ensure shape
            res_cached = {**cached, "cached": True, "input_hash": input_hash}
            if "summary" not in res_cached:
                parsed = _parse_pytest_summary(cached.get("output", "") or "")
                res_cached["summary"] = parsed["summary"]
                res_cached["passed"] = parsed["passed"]
                res_cached["failed"] = parsed["failed"]
            return result_payload(_inject_staleness(res_cached, watcher))

        res = _run(cmd, cwd=project_root)
        parsed = _parse_pytest_summary(res["output"])
        passed = res["returncode"] == 0

        try:
            store.upsert_run(
                tool=tool_name,
                command=" ".join(cmd),
                input_hash=input_hash,
                config_hash=_config_hash(project_root),
                git_sha=None,
                passed=passed,
                errors=[],
                output=res["output"][:_OUTPUT_CAP],
                duration_ms=0,
                file_paths=[path] if path != "." else [],
            )
        except Exception as exc:
            logger.debug("exec_test store upsert failed: %s", exc)

        result = {
            "pass": passed,
            "tool": tool_name,
            "command": " ".join(cmd),
            "output": res["output"][:_OUTPUT_CAP],
            "summary": parsed["summary"],
            "passed": parsed["passed"],
            "failed": parsed["failed"],
            "input_hash": input_hash,
            "cached": False,
        }
        return result_payload(_inject_staleness(result, watcher))

    # ── History / diff / timeline / cache_stats (like codebase-memory-mcp get_architecture) ──

    @server.tool(description="Return last exec runs (history). Filter by tool, limit up to 100.")
    async def exec_history(limit: int = 20, tool: str | None = None) -> dict:
        lim = max(1, min(int(limit), 100))
        rows = store.get_history(limit=lim, tool=tool)
        return result_payload({"runs": rows, "count": len(rows)})

    @server.tool(description="Return diff/detail for a run by id (like exec_diff).")
    async def exec_diff(run_id: int) -> dict:
        # Use history scan to find id
        rows = store.get_history(limit=100)
        for r in rows:
            if r["id"] == int(run_id):
                return result_payload({"run": r})
        return result_payload({"error": f"run_id {run_id} not found", "run": None})

    @server.tool(description="Return timeline for a file: runs that touched file_path.")
    async def exec_timeline(file_path: str) -> dict:
        rows = store.get_timeline(file_path)
        return result_payload({"runs": rows, "count": len(rows), "file": file_path})

    @server.tool(description="Return cache stats: total_runs, unique_hashes, hit_rate.")
    async def exec_cache_stats() -> dict:
        stats = store.get_cache_stats()
        # Also expose counts
        counts = store.get_counts()
        return result_payload({**stats, **counts})

    @server.tool(description="Return affected files via code-graph blast radius (precise, 50-75% prune).")
    async def exec_affected(base_ref: str = "main") -> dict:
        affected = exec_service.get_affected(base_ref=base_ref)
        return result_payload(affected)

    return server


def run_exec_server() -> None:
    """Entry point for n3rv-exec subprocess."""
    build_exec_server().run()


def main() -> None:
    """Entry point for n3rv-exec command."""
    run_exec_server()
