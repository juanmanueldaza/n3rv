# Architecture

N3RV provides invisible engineering infrastructure for AI agents through **four integrated subsystems**: **CLI scaffolding**, **persistent memory (MAGI)**, **A2A task delegation**, and **code intelligence (graph + exec)** — plus provider abstraction and org workspace management.

## Entry Points

| Command | Purpose | Entry Function |
|---------|---------|----------------|
| `n3rv` | CLI for init, update, converge, hub, daemon, memory, org, code-graph | `src/n3rv/cli.py:main()` |
| `n3rv-memory` | MCP server exposing memory tools (12) | `src/n3rv/mcp/memory_server.py:main()` |
| `n3rv-hub` | MCP server exposing hub delegation tools (5) | `src/n3rv/mcp/hub_server.py:main()` |
| `n3rv-code-graph` | MCP server exposing code graph (6, Python AST + FTS5) | `src/n3rv/mcp/code_graph_server.py:main()` |
| `n3rv-exec` | MCP server exposing universal lint/test/typecheck (8, 20+ langs, cache, affected) | `src/n3rv/mcp/exec_server.py:main()` |

## Evangelion Concept Map

The n3rv project draws its name and thematic structure from *Neon Genesis Evangelion*. Every subsystem maps to an Evangelion concept. Understanding these mappings reveals the design philosophy:

| Evangelion Concept | N3RV Subsystem | Why |
|---|---|---|
| **MAGI Supercomputer** | Memory Service | Three independent minds (ChromaDB, SQLite, SessionManager) reach consensus — just as Melchior, Balthasar, Casper vote on N3RV's decisions |
| **EVA Units** | AI Agents | Purpose-built entities dispatched from the Command Center (A2A Hub) to execute missions (tasks) |
| **Geofront** | `.n3rv/` directory | Hidden infrastructure beneath the workspace — houses memory stores, hub state, code graph, exec cache, daemon config |
| **Command Center** | A2A Hub + MCP Hub Server | Central dispatch. Routes tasks to agents by skill ID, monitors execution, collects results |
| **Human Instrumentality Project** | SDD Workflow | The 8-phase grand protocol for achieving unity between human intent and machine output |
| **SEELE** | SDD Verify / Judgment Day | The oversight council that reviews outputs, passes verdicts, and ensures quality |
| **AT Field** | Security boundaries | Absolute isolation: localhost-only, read-only safe mode, no hardcoded secrets |
| **Dummy Plug** | Exec + Watchers | Autonomous execution without a pilot — cache, debounce, and staleness banners run headless |
| **LCL** | Knowledge layer | The orange soup of vectors, symbols, and call graphs agents swim in |
| **S² Engine** | SDD + Converge loop | Perpetual improvement — each cycle powers the next |

For the full concept map including LCL (knowledge layer), Entry Plug (context), S² Engine (workflow engine), Dummy Plug (automation), and the three MAGI personalities, see [EVANGELION.md](../EVANGELION.md).

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         opencode Agent                               │
│  (uses 4 MCP stdio servers)                                          │
└──────┬──────────────┬──────────────────┬─────────────────────────────┘
       │              │                  │                    │
       ▼              ▼                  ▼                    ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ n3rv-memory  │ │  n3rv-hub    │ │ n3rv-exec    │ │ n3rv-code-graph  │
│  (12 tools)  │ │  (5 tools)   │ │  (8 tools)   │ │   (6 tools)      │
│ memory_save  │ │ delegate_task│ │ exec_lint    │ │ code_graph_index │
│ memory_search│ │ list_pending │ │ exec_test    │ │ code_graph_explore│
│ memory_recall│ │ check_pending│ │ exec_affected│ │ code_graph_symbols│
│ memory_judge │ │ complete_task│ │ cache_stats  │ │ references/imports│
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────────┬─────────┘
       │                │ RPC            │ XXH3 cache        │ SQLite FTS5
       ▼                ▼                ▼                   ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ MemoryStore  │ │  A2A Hub     │ │ ExecStore    │ │ CodeGraphStore   │
│ ChromaDB     │ │ aiohttp RPC  │ │ exec.db      │ │ code_graph.db    │
│ + SQLite     │ │ tasks/send   │ │ exec_runs    │ │ symbols/files    │
│ + SessionMgr │ │ tasks/list   │ │ file_states  │ │ imports/calls    │
└──────────────┘ │ SSE stream   │ │ + Watcher    │ │ + Watcher        │
                 └──────┬───────┘ └──────────────┘ └──────────────────┘
                        │ routes via TaskRouter
                        ▼
                 ┌──────────────┐
                 │ Agent Cards  │
                 │ (.n3rv/a2a-  │
                 │  config.yaml)│
                 └──────────────┘

Provider abstraction (orthogonal):
  get_provider("qwen"|"openai"|"local"|"fallback") → ModelProvider
  get_tts_provider() → TTSProvider / TTSFallbackProvider
  Input validation: n3rv.limits (text/image/audio, estimate_tokens)
```

## CLI (`src/n3rv/cli.py`)

Typer-based CLI with seven sub-apps:

- **`n3rv init`** — Scaffolds target project with agent-native files using Jinja2 templates from `src/n3rv/init/templates/`. Detects stack (python/node/go/generic) via `detector.py`. Generates `AGENTS.md`, `opencode.json` (4 MCP servers), `.opencode/` (18 skills, 7 agents, 8 commands, plugins), `.n3rv/a2a-config.yaml`, `.githooks/pre-push`.
- **`n3rv update`** — Updates existing scaffolded files. Supports `--dry-run`, `--diff`, `--force-commands`, `--only` flags. Handles `marker-merge` (AGENTS.md), `json-merge` (opencode.json), `overwrite`, `skip-default`.
- **`n3rv converge <change_id>`** — Reconciliation: re-runs verify in converge mode, emits remediation tasks for any `FAIL`/`PARTIAL` acceptance criteria into `sdd-<change_id>-tasks`, optionally updates the project board.
- **`n3rv hub start`** — Launches the A2A hub server (foreground).
- **`n3rv daemon *`** — Manage hub daemon via systemd user service: `install`, `start`, `stop`, `status`, `enable --now`, `logs`.
- **`n3rv memory *`** — Direct memory inspection. Delegates to `cli_memory.py`: `list`, `search`, `prune`, `stats`.
- **`n3rv org *`** — Org workspace: `init`, `add-satellite`, `sync`, `protect`. See below.
- **`n3rv code-graph *`** — Code intelligence: `init`, `index`, `sync`, `status`, `query`, `explore`, `node`, `files`, `callers`, `callees`, `impact`, `affected`.

Key files:
- `src/n3rv/cli.py` — CLI entry point + sub-app wiring
- `src/n3rv/cli_memory.py` — memory subcommands (rich tables)
- `src/n3rv/cli_code_graph.py` — code-graph subcommands
- `src/n3rv/cli_org.py` — org subcommands
- `src/n3rv/daemon.py` — systemd integration
- `src/n3rv/init/__init__.py` — Init orchestration
- `src/n3rv/init/detector.py` — Stack detection
- `src/n3rv/init/renderer.py` — Jinja2 template rendering
- `src/n3rv/init/registry.py` — SkillRegistry (scans SKILL.md files)
- `src/n3rv/init/lockfile.py` — `.n3rv/lock.json` pinning
- `src/n3rv/init/update.py` — update logic

## A2A Hub (`src/n3rv/a2a/hub.py`)

aiohttp web server providing JSON-RPC 2.0 interface for task delegation.

**RPC Methods:**

| Method | Purpose |
|--------|---------|
| `tasks/send` | Submit task, route to agent, auto-complete |
| `tasks/get` | Fetch task state by ID |
| `tasks/cancel` | Cancel pending/working task |
| `tasks/list` | List tasks (filter by agent, state) |
| `tasks/complete` | Mark task as completed |
| `tasks/sendSubscribe` | SSE stream for task status updates |

**Task Lifecycle:**

```
SUBMITTED → WORKING → COMPLETED
              ↓
           FAILED / CANCELED
```

**Restart Recovery:**
On startup, `A2AHub._recover_tasks()` reroutes `SUBMITTED` tasks and marks `WORKING` tasks as `RESTART_RECOVERY` (since their state is unknown).

Key files:
- `src/n3rv/a2a/hub.py` — A2AHub class, RPC handler
- `src/n3rv/a2a/router.py` — TaskRouter (routes to agents by skill ID)
- `src/n3rv/a2a/state.py` — HubStateStore (file-based JSON persistence)
- `src/n3rv/a2a/agent_cards.py` — Loads agent cards from `.n3rv/a2a-config.yaml`

## Memory System (`src/n3rv/mcp/memory_store.py`)

Dual-store architecture:

- **ChromaDB** (`.n3rv/memory/chroma/`) — Vector storage for semantic search. Uses ONNXRuntime embeddings or hash fallback.
- **SQLite** (`.n3rv/memory/relations.db`) — Relations between memories (judgments, revisions).

**Memory Types** (`models/memory.py:MemoryType`):

| Type | When to use |
|------|-------------|
| `architecture` | Design decisions, system structure |
| `bugfix` | Bug fixes with root cause |
| `decision` | Architecture or design decisions |
| `discovery` | Technical findings, gotchas |
| `learning` | Lessons learned |
| `pattern` | Established conventions, naming, structure |
| `context` | Session context, transient info |
| `summary` | Session summaries |
| `note` | Miscellaneous notes |

**Memory Scopes** (`models/memory.py:MemoryScope`):

- `project` — Shared across all agents working on the project
- `session` — Current session only
- `personal` — Agent-specific, not shared by default

Conflict detection: BM25 keyword overlap triggers `ConflictCandidate` list on `memory_save`. Judgment: `memory_judge` records `supersedes`/`conflicts_with`/`related`/`duplicate`/`no_conflict` into `relations.db`.

**Key operations:**
- `save_memory` — Persist with conflict detection (BM25 similarity)
- `search_memories` — Semantic + keyword search, returns nudge for related memories
- `recall_memory` — Fetch single memory by `topic_key`
- `recent_context` — Last N memories for session context
- `judge_memory` — Record relationship verdict between two memories
- `prune` — TTL-based soft/hard delete per scope/type (see `config._DEFAULT_MEMORY_TTL`)

## Provider Abstraction (`src/n3rv/providers/`)

```
ModelProvider (Protocol) ─┬─ QwenProvider      (DashScope compat, default)
                          ├─ OpenAIProvider
                          ├─ LocalProvider     (Ollama/vLLM compat)
                          └─ FallbackProvider  (chains N3RV_FALLBACK_PROVIDERS)
TTSProvider / TTSFallbackProvider (DASHSCOPE_API_KEY, N3RV_TTS_FALLBACK_MODELS)
```

`get_provider(name?)` resolves `N3RV_PROVIDER` env (default `qwen`), supports `provider:model` override via colon (e.g. `qwen:qwen3-coder-plus`). `get_tts_provider()` similarly resolves `N3RV_TTS_FALLBACK_MODELS` into a chain.

Defaults are env-driven via `config.ProviderDefaults` (`N3RV_PROVIDER`, `N3RV_DEFAULT_MODEL`, `N3RV_DEFAULT_BASE_URL = https://dashscope-intl.aliyuncs.com/compatible-mode/v1`). Satellites call `get_provider()` without hardcoding model IDs or keys.

## Input Validation (`src/n3rv/limits.py`)

Satellite-facing guards: `validate_text_input`, `validate_image_input`, `validate_audio_file`, `validate_audio_duration`, `estimate_tokens`, plus `InputValidationError`. Used at ingestion boundaries before LLM calls.

## MCP Servers

### Memory Server (`src/n3rv/mcp/memory_server.py`)

Exposes 12 tools to agents via FastMCP. Tools are available unless `N3RV_MEMORY_PROFILE=safe`.

| Tool | Description |
|------|-------------|
| `memory_save` | Persist a memory observation |
| `memory_get` | Fetch full memory by ID |
| `memory_search` | Semantic search across memories |
| `memory_recall` | Recall by topic_key |
| `memory_context` | Recent memories (reverse chronological) |
| `memory_session_summary` | Persist session summary |
| `memory_session_start` | Start new session, return session ID |
| `memory_delete` | Delete memory (soft/hard) |
| `memory_stats` | Aggregate counts |
| `memory_timeline` | Memories around a focus ID |
| `memory_judge` | Record relationship verdict |
| `memory_prune` | Soft-delete old memories |

### Hub Server (`src/n3rv/mcp/hub_server.py`)

Exposes 5 tools for task delegation via FastMCP.

| Tool | Description |
|------|-------------|
| `delegate_task` | Delegate task to agent by skill_id |
| `list_pending_tasks` | List incomplete tasks for an agent |
| `check_pending_tasks` | Check current agent's pending tasks |
| `complete_task` | Mark task as completed |
| `get_task` | Get task state by ID |

### Exec Server (`src/n3rv/mcp/exec_server.py` + `src/n3rv/mcp/exec/`)

Twin to `codebase-memory-mcp` — universal 20+ langs (`python` `js` `ts` `go` `rust` `java` `kotlin` `swift` `ruby` `php` `csharp` `cpp` `scala` `dart` `lua` `shell` `zig` `elixir` `haskell`) via `registry.py` (26+ exts, 20+ configs). SQLite WAL (`exec_runs` + `exec_file_states` + XXH3) + `ExecWatcher` debounce + `ExecService` `inputHash=fileHashes:configHash:toolHash` (70×) + `exec_affected` blast-radius (50-75% prune) + staleness banner.

| Tool | Description |
|------|-------------|
| `exec_lint` | Universal lint (`ruff`→`eslint`→`golangci`→`clippy`→`rubocop`→...) |
| `exec_typecheck` | Universal typecheck (`mypy`→`tsc`→`go vet`→...) |
| `exec_test` | Universal test (`pytest`→`npm`→`go test`→...) |
| `exec_history` | Last runs |
| `exec_diff` | Run detail |
| `exec_timeline` | File timeline |
| `exec_cache_stats` | `hit_rate` |
| `exec_affected` | Affected via code-graph |

### Code Graph Server (`src/n3rv/mcp/code_graph_server.py`)

Python AST index, `code_graph.db` (symbols, files, imports, calls + `symbols_fts` FTS5), incremental via `_content_hash`. Twin to Exec: shares WAL + watcher + staleness pattern (`_inject_staleness`).

| Tool | Description |
|------|-------------|
| `code_graph_index` | Incremental index of `.py` files |
| `code_graph_symbols` | List symbols filtered by file/name/kind |
| `code_graph_references` | Call sites of a symbol |
| `code_graph_imports` | Import graph (`imports_from`/`imported_by`) |
| `code_graph_affected` | Transitive impact of a file change |
| `code_graph_explore` | One-call surgical: nodes + code + call_paths + blast_radius |

Watcher: `CodeGraphWatcher` over `ALL_EXTS`, debounce `N3RV_EXEC_DEBOUNCE_MS`, `pending` set → banner `⚠️ Stale: <file> pending sync — Read it directly`.

## Agent Cards & Skill Registry

Agent cards define capabilities in `.n3rv/a2a-config.yaml` (created by `n3rv init`):

```yaml
hub:
  host: 127.0.0.1
  port: 19820
project: <project-name>
```

Skill registry (`src/n3rv/init/registry.py`) scans `.opencode/skills/*/SKILL.md` files and extracts skill metadata (id, name, description, hub_skill_ids). Written to `.n3rv/skill-registry.md`. Org mode regenerates it across satellites via `write_registry`.

TaskRouter (`src/n3rv/a2a/router.py`) matches `skill_id` from delegation request to registered agents, with keyword-based fallback inference.

## Org Workspace (`src/n3rv/org.py` + `cli_org.py`)

For the `reverberage` multi-satellite layout: `org init` bootstraps `.n3rv/org-config.yaml` + shared skills dir. `add-satellite` creates a GitHub repo (`gh repo create`), clones, `n3rv init`s, and registers the project. `sync` runs `n3rv update` across all satellites and regenerates the hub registry. `protect` applies branch protection (required checks from CI workflow, PR review, admin enforcement).

## Data Flow Examples

### Initializing a Project

```
n3rv init --stack python
  → detector.py detects stack
  → renderer.py renders templates from init/templates/
  → Creates: AGENTS.md, opencode.json, .opencode/skills/*, .opencode/commands/*, .opencode/agents/*, .n3rv/a2a-config.yaml, .githooks/pre-push
```

### Saving a Memory

```
Agent calls memory_save via MCP
  → MemoryService.memory_save()
    → MemoryStore.save_memory()
      → ChromaDB: add with embedding
      → SQLite: store relations (if topic_key exists)
      → BM25 conflict scan
      → Return SaveResult with conflicts (if any)
```

### Delegating a Task

```
Agent calls delegate_task(skill_id="sdd-design", description="...")
  → Hub MCP server → RPC tasks/send to A2A Hub
    → A2AHub.tasks_send()
      → TaskRouter.route(skill_id) → RoutingDecision
      → HubMCPBridge calls agent's MCP tool via subprocess
      → Task state updated to COMPLETED
      → Memory saved to session about delegation
```

### Surgical Explore

```
Agent calls code_graph_explore(query="memory_save", max_nodes=20)
  → CodeGraphService.explore()
    → FTS5 search on symbols_fts
    → Collect symbols + imports + calls + affected (blast radius)
    → Read verbatim source grouped by file
    → _inject_staleness from CodeGraphWatcher.pending
    → Return {nodes, code_by_file, call_paths, blast_radius, banner?, footer?}
```

### Cached Lint

```
Agent calls exec_lint(path="src/n3rv/cli.py")
  → _detect_lint_tool("src/n3rv/cli.py") → ruff
  → inputHash = XXH3(files):config:tool
  → store.get_cached(inputHash) ? return cached (+ staleness banner) : run ruff
  → store.upsert_run + file_states
  → Return {pass, tool, output, errors, input_hash, cached}
```

## Agent Dispatch: Native Subagents vs A2A Hub

n3rv has **two** dispatch mechanisms. They are not rivals — each owns a distinct scope. This
is a deliberate split, not redundancy.

### opencode-native subagents (in-process, session-scoped)

Agents defined as `.opencode/agents/*.md` (the sdd-* roster, `git-ops`, `github-ops`,
`project-ops`, `n3rv-scout`, `n3rv-sensor`, and the `n3rv` primary). They are dispatched by
the primary via the **Task tool** (`permission.task`) and `@mention`.

- **Lifetime:** bounded by the current opencode session/process.
- **Scope:** execution of a single phase or investigation.
- **Cost:** cheap — no IPC/subprocess; state lives in the same session.
- **Use for:** everything that happens *within* one working session — SDD phases, code
  exploration, git/github operations, external-doc lookups (`n3rv-scout`), toolchain
  checks (`n3rv-sensor`).

### n3rv A2A hub (durable, cross-session, cross-project)

The hub (`src/n3rv/a2a/hub.py`) routes tasks by `skill_id` via `delegate_task` /
`check_pending_tasks`, persisting task state to disk and surviving hub restarts.

- **Lifetime:** survives the session; tasks persist across restarts and projects.
- **Scope:** handing work *between* agents, *across* projects, or *past* a session boundary.
- **Cost:** heavier — JSON-RPC over HTTP, subprocess bridge.
- **Use for:** long-running or multi-session jobs, cross-project handoff, anything that must
  outlive the current opencode session. opencode-native subagents *cannot* do this; the hub
  is the durable spine n3rv adds on top of opencode.

### Decision rule

> If the work must survive the current session or cross a project boundary → **A2A hub**.
> Otherwise → **opencode-native subagent** (via the Task tool).

### Background subagents (parallel dispatch)

Opencode can run a subagent in the background (return immediately, notify on completion) via
the `background: true` task parameter, e.g. launching `n3rv-scout` / `n3rv-sensor`
concurrently during SDD explore while exploration continues.

**Enablement:** this is a **process-environment** flag, **not** a config key. It cannot be set
in `opencode.json` and the `shell.env` plugin does not apply (the flag is read by the opencode
core, not a shell subprocess). It is read by the core task tool at
`packages/opencode/src/tool/task.ts`:

```
Background subagents require OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true
```

Set it in the environment of the process that launches opencode:

```bash
export OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true
opencode
```

n3rv agents using `background: true` **always degrade to foreground** when the flag is unset,
so the workflow never depends on it.
