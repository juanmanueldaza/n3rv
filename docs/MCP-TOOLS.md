# MCP Tools Reference

N3RV exposes **four** MCP servers — **31 tools** total — for agent integration:

| Server | Tools | Command |
|--------|-------|---------|
| Memory | 12 | `n3rv-memory` |
| Hub | 5 | `n3rv-hub` |
| Exec | 8 | `n3rv-exec` |
| Code Graph | 6 | `n3rv-code-graph` |

All four are `stdio` MCP servers launched by opencode via `opencode.json` (`N3RV_AGENT_SOURCE=opencode`). Twin servers `n3rv-exec` and `n3rv-code-graph` share SQLite WAL + watcher + staleness-banner infrastructure (`_inject_staleness`).

---

## Memory Server (`n3rv-memory`)

Exposed by `src/n3rv/mcp/memory_server.py`. Dual-store MAGI: ChromaDB (Melchior, vector/semantic) + SQLite `relations.db` (Balthasar, judgments/revisions) + `SessionManager` (Casper, lifecycle). ONNXRuntime embeddings with hash fallback. Conflict detection via BM25; TTL pruning per scope/type.

### `memory_save`

Persist a memory observation to project-local ChromaDB.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Full text of the memory |
| `title` | string | Yes | Short, searchable title |
| `type` | string | Yes | One of: `architecture`, `bugfix`, `config`, `decision`, `discovery`, `learning`, `pattern`, `context`, `summary`, `note` |
| `topic_key` | string | No | Stable key for evolution (e.g., `architecture/auth-model` or `sdd-<change_id>-<phase>`) |
| `scope` | string | No | `project` (default), `session`, `personal` |

Returns: `SaveResult` with `id`, `topic_key`, `status`, `timestamp`, `revision_count`, `conflicts`

---

### `memory_get`

Fetch full content of a single active memory by ID.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Memory ID |

Returns: Full memory object or `{"error": "not found"}`.

---

### `memory_search`

Semantic search across stored engineering memories (vector + BM25 keyword).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `limit` | int | No | Max results (default: 5) |
| `type_filter` | string | No | Filter by `MemoryType` |
| `keyword` | string | No | Exact keyword filter |
| `snippet_only` | bool | No | Return snippets only (default: false) |
| `include_personal` | bool | No | Include personal scope (default: false) |

Returns: `SearchResponse` with `results` list and optional `nudge` string for related memories. Nudge fires after `_SEARCH_NUDGE_THRESHOLD` (3) searches without a write.

---

### `memory_recall`

Recall a single memory by `topic_key`. Returns the most recent active memory for that key.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `topic_key` | string | Yes | Topic key to recall |

Returns: `RecallResult` with `found`, `id`, `title`, `content`, `type`, `timestamp`.

---

### `memory_context`

Return recent memories in reverse chronological order.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `n` | int | No | Number of memories (default: 10) |

Returns: `ContextResult` with `count` and `memories` list.

---

### `memory_session_summary`

Persist a session summary as a memory of type `summary`.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `summary` | string | Yes | Session summary text |

Returns: `SaveResult`.

---

### `memory_session_start`

Persist a session-start context entry and return the new session ID.

Returns: `SessionStartResult` with `session_id`, `started_at`, `context` list.

---

### `memory_delete`

Delete a stored memory by ID. Available only when `N3RV_MEMORY_PROFILE != "safe"`.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Memory ID |
| `hard_delete` | bool | No | Permanently remove (default: false = soft delete) |

Returns: `{"status": "deleted", "id": ...}`.

---

### `memory_stats`

Return aggregate counts for active memories.

Returns: Dict with `total`, `by_type`, `by_scope`, `by_agent` counts.

---

### `memory_timeline`

Return active memories surrounding a focus memory ID (before + after).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Focus memory ID |
| `before` | int | No | Memories before focus (default: 5) |
| `after` | int | No | Memories after focus (default: 5) |

Returns: `TimelineResult` with `focus`, `before` list, `after` list.

---

### `memory_judge`

Record an agent verdict on the relationship between two memories.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `source_id` | string | Yes | Source memory ID |
| `target_id` | string | Yes | Target memory ID |
| `verdict` | string | Yes | One of: `supersedes`, `conflicts_with`, `related`, `duplicate`, `no_conflict` |
| `reason` | string | No | Explanation for the verdict |

Returns: `JudgeResult` with `source_id`, `target_id`, `verdict`, `status`, `is_new`.

---

### `memory_prune`

Soft-delete memories of a given scope older than N days (or per `config.memory_ttl`).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `scope` | string | Yes | `project`, `session`, or `personal` |
| `older_than_days` | int | Yes | Minimum age in days (if omitted, per-type TTL from `_DEFAULT_MEMORY_TTL` applies) |
| `type_filter` | string | No | Comma-separated types (e.g. `summary,context`) |
| `hard_delete` | bool | No | Permanently remove (default: false) |

Returns: `PruneResult` with `pruned` count, `scope`, `older_than_days`.

---

## Hub Server (`n3rv-hub`)

Exposed by `src/n3rv/mcp/hub_server.py`. Provides A2A task delegation via the local hub (`127.0.0.1:19820`, `src/n3rv/a2a/hub.py`).

### `delegate_task`

Delegate a task to another agent via the A2A hub. The task stays assigned until the delegated agent calls `complete_task`.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `skill_id` | string | Yes | Must match a registered agent skill (e.g. `sdd-design`, `review`, `implementation`) |
| `description` | string | Yes | Task description |
| `requesting_agent` | string | No | Agent source (default: `unknown`, usually `N3RV_AGENT_SOURCE`) |

Returns: Task object with `id`, `status`, `assigned_agent`.

---

### `list_pending_tasks`

List tasks assigned to an agent that are not yet completed.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | No | Agent ID (defaults to `N3RV_AGENT_SOURCE`) |

Returns: List of task objects.

---

### `check_pending_tasks`

Check pending tasks assigned to the current agent (alias for `list_pending_tasks` with current agent).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | No | Agent ID (defaults to `N3RV_AGENT_SOURCE`) |

Returns: List of task objects.

---

### `complete_task`

Mark a task as completed after executing it.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | Yes | Task ID from `check_pending_tasks` |
| `result` | string | Yes | Result summary |
| `completing_agent` | string | No | Agent completing (default: `unknown`) |

Returns: Updated task object.

---

### `get_task`

Get the current state of a task by its ID.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |

Returns: Task object with `id`, `status`, `assigned_agent`, `metadata`.

---

## Exec Server (`n3rv-exec`)

Exposed by `src/n3rv/mcp/exec_server.py` + `src/n3rv/mcp/exec/`. Universal lint/typecheck/test with XXH3 cache + blast-radius — twin to `codebase-memory-mcp`.

**Registry (`src/n3rv/mcp/exec/registry.py`):** 20+ languages — `python (.py/.pyi)`, `javascript (.js/.jsx/.mjs/.cjs)`, `typescript (.ts/.tsx)`, `go (.go)`, `rust (.rs)`, `java (.java)`, `kotlin (.kt/.kts)`, `swift (.swift)`, `objc (.m/.mm/.h)`, `ruby (.rb)`, `php (.php)`, `csharp (.cs)`, `cpp (.cpp/.c/.h/.hpp)`, `scala (.scala)`, `dart (.dart)`, `lua (.lua)`, `shell (.sh)`, `zig (.zig)`, `elixir (.ex/.exs)`, `haskell (.hs)` — all watched via `ALL_EXTS` (26+) + `ALL_CONFIGS` (20+).

**Cache:** `inputHash = XXH3(fileHashes):configHash:toolHash` via `ExecStore` (SQLite WAL, `exec_runs` + `exec_file_states`) + `ExecWatcher` debounce (`N3RV_EXEC_DEBOUNCE_MS`) + `ExecService` orchestration (70×, Turborepo/Bazel grade). Staleness banner (`⚠️ Stale: file pending sync`) via `_inject_staleness`. Jail: `cwd` inside `project_root`, `no shell`, `60s` timeout, `10KB` cap (`AT Field`).

### `exec_lint`

Run lint with universal auto-detect per-extension (`ruff`→`eslint`→`golangci-lint`→`cargo clippy`→`rubocop`→`phpcs`→`checkstyle`→`ktlint`→`swiftlint`→`clang-tidy`→`dotnet`→`scalastyle`).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | No | File or dir (default `.`) |
| `affected` | bool | No | If true, only lint `affected_lints` from `exec_affected` (50-75% prune) |
| `base_ref` | string | No | Git base for affected (default `main`) |

Returns: `{pass, tool, command, output, errors[], input_hash, cached, banner?, footer?}`. Jail: `cwd` inside `project_root`, `no shell`, `60s` timeout, `10KB` cap (`AT Field`).

### `exec_typecheck`

Universal typecheck (`mypy`→`tsc`→`go vet`→`cargo check`→...).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | No | Target (default `src`) |

Returns: `{pass, tool, command, output, errors[], input_hash, cached}`.

### `exec_test`

Universal test (`pytest`→`npm test`→`go test`→`cargo test`→...).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | No | Path (default `.`) |
| `extra_args` | string | No | Extra args split safely (no shell) |
| `affected` | bool | No | If true, only run `affected_tests` (50% prune) |
| `base_ref` | string | No | Git base |

Returns: `{pass, tool, command, output, summary, passed, failed, input_hash, cached}`.

### `exec_history`

Return last runs.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `limit` | int | No | Max (default 20, max 100) |
| `tool` | string | No | Filter by tool |

Returns: `{runs[], count}`.

### `exec_diff`

Diff/detail for a run.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `run_id` | int | Yes | Row id |

Returns: `{run}` or `{error}`.

### `exec_timeline`

Timeline for a file.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | string | Yes | File |

Returns: `{runs[], count, file}`.

### `exec_cache_stats`

Cache stats.

Returns: `{total_runs, unique_hashes, hit_rate, runs, file_states}`.

### `exec_affected`

Affected via `code-graph` blast radius (`CodeGraphService.affected` → `Max` win).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `base_ref` | string | No | Git base (default `main`) |

Returns: `{changed_files[], affected_tests[], affected_lints[], affected[]}`.

---

## Code Graph Server (`n3rv-code-graph`)

Exposed by `src/n3rv/mcp/code_graph_server.py` + `src/n3rv/mcp/code_graph_service.py` / `code_graph_store.py` / `code_graph_watcher.py`. Python AST index (incremental, hash-skipped) with FTS5 search, call graph, and transitive `affected` — twin to `n3rv-exec` (SQLite WAL + watcher + staleness banner).

Watcher: `CodeGraphWatcher` over `ALL_EXTS` (Python `.py`), debounce `N3RV_EXEC_DEBOUNCE_MS`, `pending` set surfaced via `_inject_staleness` (`banner`/`footer`). Store: `code_graph.db` (symbols, files, imports, calls + `symbols_fts`).

### `code_graph_index`

Index project Python files into the code graph. Incremental (skips unchanged files via `_content_hash`).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `project_path` | string | Yes | Absolute project root to walk |

Returns: `{files_indexed, symbols_found, imports_found, calls_found, files_skipped, errors?}`. Skips `__pycache__`, `.git`, `.venv`, `node_modules`, `.mypy_cache`, `.ruff_cache`, `*.egg-info`.

### `code_graph_symbols`

List symbol definitions (functions, classes, methods) in a file or across the project.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `project_path` | string | Yes | Project root |
| `file_path` | string | No | Restrict to this file (relative or absolute) |
| `name` | string | No | Exact symbol name |
| `kind` | string | No | `function` · `class` · `method` |

Returns: List of `{name, kind, file, line, end_line, parent, docstring, args}`.

### `code_graph_references`

Find all call sites for a function or method by name.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `project_path` | string | Yes | Project root |
| `name` | string | Yes | Symbol name |

Returns: List of `{file, line, context}`. Used by CLI `callers` and `impact`.

### `code_graph_imports`

Show import graph for a file: what it imports, and what imports it.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `project_path` | string | Yes | Project root |
| `file_path` | string | Yes | File to inspect (relative to root) |

Returns: `{imports_from: string[], imported_by: string[]}`.

### `code_graph_affected`

Impact analysis: which files would be affected if this file changes (transitive import + call graph).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `project_path` | string | Yes | Project root |
| `file_path` | string | Yes | Changed file (relative) |
| `max_depth` | int | No | Traversal depth (default 5) |

Returns: List of `{file, reason, depth}`. Powers `exec_affected` (50–75% prune) and CLI `affected`.

### `code_graph_explore`

Surgical explore: **one call** returns relevant source + call paths + blast radius. The workhorse for `sdd-explore` and `/review`.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `project_path` | string | Yes | Project root |
| `query` | string | Yes | FTS5 keyword query (e.g. `memory_save`, `A2A hub`) |
| `max_nodes` | int | No | Max symbol nodes (default 20) |
| `include_code` | bool | No | Include verbatim source grouped by file (default true) |

Returns: `{nodes: SymbolInfo[], code_by_file: Record<file, code>, call_paths: {from,to,via}[], blast_radius: {affected_files, affected[]}, banner?, footer?}`. Verbatim source is grouped by file for agent consumption. During active debounce, files in `pending` carry a staleness banner: `⚠️ Stale: <file> pending sync — Read it directly`.

---

## Task States

Defined in `src/n3rv/models/a2a.py:TaskState`:

| State | Value | Meaning |
|-------|-------|---------|
| SUBMITTED | `submitted` | Task created, awaiting routing |
| WORKING | `working` | Agent is processing the task |
| COMPLETED | `completed` | Task finished successfully |
| FAILED | `failed` | Task encountered an error |
| CANCELED | `canceled` | Task was canceled |

## Error Codes

| Code | Meaning |
|------|---------|
| `SKILL_NOT_FOUND` | `skill_id` doesn't match any registered agent |
| `MCP_TOOL_ERROR` | Agent's MCP tool call failed |
| `DELEGATION_FAILED` | General delegation failure |
| `RESTART_RECOVERY` | Hub restarted while task was in WORKING state |
