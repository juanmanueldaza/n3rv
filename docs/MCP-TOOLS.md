# MCP Tools Reference

N3RV exposes three MCP servers with a total of 25 tools for agent integration (Memory 12 + Hub 5 + Exec 8).

## Memory Server (`n3rv-memory`)

Exposed by `src/n3rv/mcp/memory_server.py`. Provides persistent semantic memory backed by ChromaDB + SQLite.

### `memory_save`

Persist a memory observation to project-local ChromaDB.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Full text of the memory |
| `title` | string | Yes | Short, searchable title |
| `type` | string | Yes | One of: `architecture`, `bugfix`, `config`, `decision`, `discovery`, `learning`, `pattern`, `context`, `summary`, `note` |
| `topic_key` | string | No | Stable key for evolution (e.g., `architecture/auth-model`) |
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

Semantic search across stored engineering memories.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `limit` | int | No | Max results (default: 5) |
| `type_filter` | string | No | Filter by `MemoryType` |
| `keyword` | string | No | Exact keyword filter |
| `snippet_only` | bool | No | Return snippets only (default: false) |
| `include_personal` | bool | No | Include personal scope (default: false) |

Returns: `SearchResponse` with `results` list and optional `nudge` string for related memories.

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

Returns: Dict with `total`, `by_type`, `by_scope` counts.

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

Soft-delete memories of a given scope older than N days.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `scope` | string | Yes | `project`, `session`, or `personal` |
| `older_than_days` | int | Yes | Minimum age in days |

Returns: `PruneResult` with `pruned` count, `scope`, `older_than_days`.

---

## Hub Server (`n3rv-hub`)

Exposed by `src/n3rv/mcp/hub_server.py`. Provides A2A task delegation via the local hub.

### `delegate_task`

Delegate a task to another agent via the A2A hub. The task stays assigned until the delegated agent calls `complete_task`.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `skill_id` | string | Yes | Must match a registered agent skill |
| `description` | string | Yes | Task description |
| `requesting_agent` | string | No | Agent source (default: `unknown`) |

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

Check pending tasks assigned to the current agent.

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

Exposed by `src/n3rv/mcp/exec_server.py` (with `src/n3rv/mcp/exec/`). Provides universal lint/typecheck/test with XXH3 cache + blast-radius, twin to `codebase-memory-mcp`.

**Registry (`src/n3rv/mcp/exec/registry.py`):** 20+ languages — `python (.py/.pyi)`, `javascript (.js/.jsx/.mjs/.cjs)`, `typescript (.ts/.tsx)`, `go (.go)`, `rust (.rs)`, `java (.java)`, `kotlin (.kt/.kts)`, `swift (.swift)`, `objc (.m/.mm/.h)`, `ruby (.rb)`, `php (.php)`, `csharp (.cs)`, `cpp (.cpp/.c/.h/.hpp)`, `scala (.scala)`, `dart (.dart)`, `lua (.lua)`, `shell (.sh)`, `zig (.zig)`, `elixir (.ex/.exs)`, `haskell (.hs)` — all watched via `ALL_EXTS` (26+) + `ALL_CONFIGS` (20+).

**Cache:** `inputHash = XXH3(fileHashes):configHash:toolHash` via `ExecStore` (SQLite WAL, `exec_runs` + `exec_file_states`) + `ExecWatcher` debounce (`N3RV_EXEC_DEBOUNCE_MS`) + `ExecService` orchestration (70×, Turborepo/Bazel grade). Staleness banner (`⚠️ Stale: file pending sync`) via `_inject_staleness`.

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

Affected via `codebase-memory-mcp` blast radius (`detect_changes` → `Max` win).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `base_ref` | string | No | Git base (default `main`) |

Returns: `{changed_files[], affected_tests[], affected_lints[], affected[]}`.

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
