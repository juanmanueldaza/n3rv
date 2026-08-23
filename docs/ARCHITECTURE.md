# Architecture

N3RVERBERAGE provides invisible engineering infrastructure for AI agents through three integrated subsystems: **CLI scaffolding**, **persistent memory**, and **A2A task delegation**.

## Entry Points

| Command | Purpose | Entry Function |
|---------|----------|----------------|
| `n3rverberage` | CLI for init, update, hub start, memory commands | `src/n3rverberage/cli.py:main()` |
| `n3rverberage-memory` | MCP server exposing memory tools | `src/n3rverberage/mcp/memory_server.py:main()` |
| `n3rverberage-hub` | MCP server exposing hub delegation tools | `src/n3rverberage/mcp/hub_server.py:main()` |

## Evangelion Concept Map

The n3rverberage project draws its name and thematic structure from *Neon Genesis Evangelion*. Every subsystem maps to an Evangelion concept. Understanding these mappings reveals the design philosophy:

| Evangelion Concept | N3RVERBERAGE Subsystem | Why |
|---|---|---|
| **MAGI Supercomputer** | Memory Service | Three independent minds (ChromaDB, SQLite, SessionManager) reach consensus — just as Melchior, Balthasar, Casper vote on N3RVERBERAGE's decisions |
| **EVA Units** | AI Agents | Purpose-built entities dispatched from the Command Center (A2A Hub) to execute missions (tasks) |
| **Geofront** | `.n3rverberage/` directory | Hidden infrastructure beneath the workspace — houses memory stores, hub state, and configuration |
| **Command Center** | A2A Hub + MCP Hub Server | Central dispatch. Routes tasks to agents by skill ID, monitors execution, collects results |
| **Human Instrumentality Project** | SDD Workflow | The 8-phase grand protocol for achieving unity between human intent and machine output |
| **SEELE** | SDD Verify / Judgment Day | The oversight council that reviews outputs, passes verdicts, and ensures quality |
| **AT Field** | Security boundaries | Absolute isolation: localhost-only, read-only safe mode, no hardcoded secrets |

For the full concept map including LCL (knowledge layer), Entry Plug (context), S² Engine (workflow engine), Dummy Plug (automation), and the three MAGI personalities, see [EVANGELION.md](../EVANGELION.md).

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      opencode Agent                        │
│  (uses MCP tools to interact with N3RVERBERAGE)                   │
└──────────────┬──────────────────────┬─────────────────────┘
               │                      │
               │ MCP tools            │ MCP tools
               ▼                      ▼
┌──────────────────────┐  ┌──────────────────────────────────┐
│   n3rverberage-memory MCP    │  │     n3rverberage-hub MCP                 │
│   (memory_server.py) │  │     (hub_server.py)              │
│                      │  │                                  │
│ Tools:               │  │ Tools:                           │
│ • memory_save        │  │ • delegate_task                  │
│ • memory_search      │  │ • list_pending_tasks             │
│ • memory_recall      │  │ • complete_task                  │
│ • memory_context     │  │ • get_task                       │
│ • memory_delete      │  │                                  │
│ • memory_prune       │  └──────────┬───────────────────────┘
│ • memory_stats       │             │ RPC (JSON-RPC over HTTP)
│ • memory_timeline    │             ▼
│ • memory_judge       │  ┌──────────────────────────────────┐
│ • memory_session_*   │  │     A2A Hub Server               │
└──────────┬───────────┘  │     (a2a/hub.py - A2AHub)       │
           │              │                                  │
           │ ChromaDB     │ RPC methods:                     │
           │ + SQLite     │ • tasks/send                     │
           ▼              │ • tasks/get                      │
┌──────────────────────┐  │ • tasks/cancel                   │
│  MemoryStore         │  │ • tasks/list                     │
│  (mcp/memory_store)  │  │ • tasks/complete                 │
│                      │  │ • tasks/sendSubscribe (SSE)      │
│ • ChromaDB (vector)  │  └──────────┬───────────────────────┘
│ • SQLite (relations) │             │
└──────────────────────┘              │ routes to
                                     ▼
                          ┌──────────────────────────────────┐
                          │  TaskRouter + HubMCPBridge       │
                          │  (a2a/router.py)                │
                          │                                  │
                          │  Routes by skill_id → agent      │
                          │  Calls agent MCP tools via       │
                          │  subprocess (HubMCPBridge)       │
                          └──────────┬───────────────────────┘
                                     │
                                     ▼
                          ┌──────────────────────────────────┐
                          │  Registered Agents               │
                          │  (from .n3rverberage/a2a-config.yaml)    │
                          │                                  │
                          │  • opencode (general)             │
                          │  • sdd-* agents (specialized)    │
                          │  • judgment-day agent             │
                          └──────────────────────────────────┘
```

## CLI (`src/n3rverberage/cli.py`)

Typer-based CLI with three subcommands:

- **`n3rverberage init`** — Scaffolds target project with agent-native files using Jinja2 templates from `src/n3rverberage/init/templates/`. Detects stack (python/node/go/generic) via `detector.py`.
- **`n3rverberage update`** — Updates existing scaffolded files. Supports `--dry-run`, `--force-commands`, `--only` flags.
- **`n3rverberage hub start`** — Launches the A2A hub server.
- **`n3rverberage memory *`** — Direct memory inspection (list, search, prune, stats). Delegates to `cli_memory.py`.

Key files:
- `src/n3rverberage/cli.py` — CLI entry point
- `src/n3rverberage/init/__init__.py` — Init orchestration
- `src/n3rverberage/init/detector.py` — Stack detection
- `src/n3rverberage/init/renderer.py` — Jinja2 template rendering
- `src/n3rverberage/init/registry.py` — SkillRegistry (scans SKILL.md files)

## A2A Hub (`src/n3rverberage/a2a/hub.py`)

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
- `src/n3rverberage/a2a/hub.py` — A2AHub class, RPC handler
- `src/n3rverberage/a2a/router.py` — TaskRouter (routes to agents by skill ID)
- `src/n3rverberage/a2a/state.py` — HubStateStore (file-based JSON persistence)
- `src/n3rverberage/a2a/agent_cards.py` — Loads agent cards from `.n3rverberage/a2a-config.yaml`

## Memory System (`src/n3rverberage/mcp/memory_store.py`)

Dual-store architecture:

- **ChromaDB** (`.n3rverberage/memory/chroma/`) — Vector storage for semantic search. Uses ONNXRuntime embeddings or hash fallback.
- **SQLite** (`.n3rverberage/memory/relations.db`) — Relations between memories (judgments, revisions).

**Memory Types** (`models/memory.py:MemoryType`):

| Type | When to use |
|------|-------------|
| `architecture` | Design decisions, system structure |
| `bugfix` | Bug fixes with root cause |
| `config` | Configuration changes, environment setup |
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

**Key operations:**
- `save_memory` — Persist with conflict detection (BM25 similarity)
- `search_memories` — Semantic + keyword search, returns nudge for related memories
- `recall_memory` — Fetch single memory by `topic_key`
- `recent_context` — Last N memories for session context
- `judge_memory` — Record relationship verdict between two memories

## MCP Servers

### Memory Server (`src/n3rverberage/mcp/memory_server.py`)

Exposes 12 tools to agents via FastMCP. Tools are available unless `N3RVERBERAGE_MEMORY_PROFILE=safe`.

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

### Hub Server (`src/n3rverberage/mcp/hub_server.py`)

Exposes 5 tools for task delegation via FastMCP.

| Tool | Description |
|------|-------------|
| `delegate_task` | Delegate task to agent by skill_id |
| `list_pending_tasks` | List incomplete tasks for an agent |
| `check_pending_tasks` | Check current agent's pending tasks |
| `complete_task` | Mark task as completed |
| `get_task` | Get task state by ID |

## Agent Cards & Skill Registry

Agent cards define capabilities in `.n3rverberage/a2a-config.yaml` (created by `n3rverberage init`):

```yaml
hub:
  host: 127.0.0.1
  port: 19820
project: <project-name>
```

Skill registry (`src/n3rverberage/init/registry.py`) scans `.opencode/skills/*/SKILL.md` files and extracts skill metadata (id, name, description, hub_skill_ids).

TaskRouter (`src/n3rverberage/a2a/router.py`) matches `skill_id` from delegation request to registered agents, with keyword-based fallback inference.

## Data Flow Examples

### Initializing a Project

```
n3rverberage init --stack python
  → detector.py detects stack
  → renderer.py renders templates from init/templates/
  → Creates: AGENTS.md, opencode.json, .opencode/skills/*, .opencode/commands/*, .opencode/agents/*, .n3rverberage/a2a-config.yaml, .githooks/pre-push
```

### Saving a Memory

```
Agent calls memory_save via MCP
  → MemoryService.memory_save()
    → MemoryStore.save_memory()
      → ChromaDB: add with embedding
      → SQLite: store relations (if topic_key exists)
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
