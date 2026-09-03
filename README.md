# n3rv

**Invisible engineering infrastructure for opencode agents.**

> The harness that contains, restrains, and orchestrates LLMs — A2A hub, persistent semantic memory, code graph, and structured SDD workflows. The daemon runs beneath your workspace. You never see it.

Maintained by [Juan Manuel Daza](https://github.com/juanmanueldaza) · [n3rv.daza.ar](https://n3rv.daza.ar) · Apache-2.0 · Python ≥3.11

---

## What This Is

n3rv is a **runtime library and config generator** for [opencode](https://github.com/opencode-ai/opencode). It scaffolds any repo (python/node/go/generic) into an agent-native workspace: skills, MCP servers, daemon, and provider abstraction. Satellites and standalone projects use it at runtime for provider resolution and task routing.

```
your-project/
├── AGENTS.md                  ← coding standards for every agent
├── opencode.json              ← 4 MCP servers + env wiring
├── .opencode/                 ← skills, agents, commands, plugins
├── .n3rv/                     ← Geofront: memory, code_graph, hub-state, logs
│   ├── memory/chroma/         ← ChromaDB vectors (Melchior)
│   ├── memory/relations.db    ← SQLite relations (Balthasar)
│   ├── code_graph.db          ← AST index (symbols/imports/calls)
│   ├── exec.db                ← lint/test cache (XXH3)
│   ├── hub-state/             ← persisted A2A tasks
│   └── a2a-config.yaml        ← hub host/port + project name
└── .githooks/pre-push         ← SDD verification gate
```

## Features

| Subsystem | What it does |
|-----------|--------------|
| **4 MCP Servers** | `n3rv-memory` (12 tools), `n3rv-hub` (5), `n3rv-exec` (8, universal 20+ langs), `n3rv-code-graph` (6) |
| **A2A Hub** | Cross-process task delegation over `127.0.0.1:19820` — `delegate_task → check_pending_tasks → complete_task`, JSON-RPC + SSE, file-persisted |
| **MAGI Memory** | ChromaDB (vectors, ONNX/hash fallback) + SQLite (relations/judgments) + SessionManager. SDD artifacts, conflict detection (BM25), TTL pruning |
| **Code Graph** | AST index (Python) — symbols, imports, call sites, blast-radius `affected`, FTS5 search, surgical `explore` (nodes+code+call_paths+blast_radius) with watcher debounce + staleness banner |
| **Universal Exec** | One toolchain for 20+ langs: `ruff→eslint→golangci→clippy→…`, `pytest→npm→go→cargo`, `mypy→tsc→vet` — XXH3 `inputHash=fileHashes:configHash:toolHash` (70× cache) + `exec_affected` via code graph (50–75% prune) |
| **Provider Abstraction** | `ModelProvider` Protocol + `get_provider("qwen"|"openai"|"local"|"fallback")` with `N3RV_PROVIDER` + `N3RV_FALLBACK_PROVIDERS`. Includes `get_tts_provider()` / `TTSFallbackProvider` |
| **Input Validation** | `n3rv.limits` — `validate_text_input`, `validate_image_input`, `validate_audio_*`, `estimate_tokens` for satellite payloads |
| **Config Generation** | Jinja2-templated scaffold of `AGENTS.md`, `opencode.json`, skills (18), agents (7), commands (8), plugins, hooks — stack-aware (python/node/go/generic) |
| **Org Mode** | Multi-satellite workspace: `n3rv org init|add-satellite|sync|protect` — shared skills, hub registry, branch protection |
| **SDD Workflow** | 8-phase `explore → propose → spec → design → tasks → apply → verify → archive` + `converge` + lighter Spec-Kit path (`spec/plan/tasks` under `.specify/`) |
| **Daemon** | `systemd --user` unit (`n3rv daemon install|enable|start|stop|status|logs`) — one hub per machine, all projects share it |

## Quick Start

```bash
# install
pip install git+https://github.com/juanmanueldaza/n3rv.git
# or for development
pip install -e ".[dev]"

# scaffold your project
cd your-project
n3rv init                              # auto-detects stack
n3rv init --stack python --force       # explicit

# start the hub (daemon recommended)
n3rv daemon install
n3rv daemon enable --now
n3rv daemon status
# or foreground for dev
n3rv hub start

# verify
n3rv --help
n3rv-memory --help   # 12 tools
n3rv-hub --help      # 5 tools
n3rv-exec --help     # 8 tools (via MCP)
n3rv-code-graph --help
```

Generated `opencode.json` wires all 4 MCP servers with `N3RV_AGENT_SOURCE=opencode` so every agent gets memory + hub + exec + code-graph without extra config.

## CLI Reference

```
n3rv init [--root PATH] [--project-name NAME] [--stack python|node|go|generic] [--force]
n3rv update [--dry-run] [--diff] [--force-commands] [--only marker-merge|json-merge|overwrite|skip-default] [--root PATH]
n3rv converge <change_id> [--root PATH] [--issue N]          # close spec↔impl gap → sdd-*-tasks
n3rv hub start
n3rv daemon install|start|stop|status|enable [--now]|logs [--root PATH]
n3rv memory list    [--type TYPE] [--scope SCOPE] [--limit N]
n3rv memory search  <query> [--type TYPE] [--keyword KW] [--limit N]
n3rv memory prune   --scope session|personal|project [--older-than DAYS] [--type TYPES] [--hard-delete]
n3rv memory stats
n3rv memory-list    # alias for memory list
n3rv memory-search  # alias for memory search
n3rv org init [--root PATH] [--org-name The-Replacement] [--force]
n3rv org add-satellite <name> [--root PATH] [--description TEXT] [--type satellite|tool]
n3rv org sync [--root PATH] [--dry-run] [--only CATEGORY]
n3rv org protect [project] [--root PATH] [--dry-run]
n3rv code-graph init [--root PATH] [--force]
n3rv code-graph index [--root PATH] [--force]
n3rv code-graph sync [--root PATH]
n3rv code-graph status [--root PATH] [--json]
n3rv code-graph query <query> [--root PATH] [--kind KIND] [--limit N] [--json]
n3rv code-graph explore <query> [--root PATH] [--max-nodes N] [--json]
n3rv code-graph node <symbol|file> [--root PATH] [--json]
n3rv code-graph files [--root PATH] [--json]
n3rv code-graph callers <symbol> [--root PATH] [--limit N]
n3rv code-graph callees <symbol> [--root PATH] [--limit N]
n3rv code-graph impact <symbol> [--root PATH] [--depth N]
n3rv code-graph affected <files...> [--root PATH] [--depth N] [--json]
```

## MCP Servers

All four are `stdio` servers launched by opencode via `opencode.json`. See [docs/MCP-TOOLS.md](docs/MCP-TOOLS.md) for the full 31-tool reference.

| Server | Command | Tools | Purpose |
|--------|---------|-------|---------|
| `n3rv-memory` | `n3rv-memory` | 12 | `memory_save/search/recall/context/timeline/stats/judge/prune/delete/session_*` |
| `n3rv-hub` | `n3rv-hub` | 5 | `delegate_task/list_pending_tasks/check_pending_tasks/complete_task/get_task` |
| `n3rv-exec` | `n3rv-exec` | 8 | `exec_lint/typecheck/test/history/diff/timeline/cache_stats/affected` — universal + cache + staleness |
| `n3rv-code-graph` | `n3rv-code-graph` | 6 | `code_graph_index/symbols/references/imports/affected/explore` — AST + FTS5 + blast radius |

Code graph and exec are twins: both use SQLite WAL + file watcher + `pending` set + `_inject_staleness` banner (`⚠️ Stale: file pending sync — Read it directly`).

## Providers

```python
from n3rv.providers.factory import get_provider, get_tts_provider

llm = get_provider()  # N3RV_PROVIDER env, default "qwen"
llm = get_provider("openai:gpt-4o")  # model override via colon
llm = get_provider("fallback")  # N3RV_FALLBACK_PROVIDERS="qwen,openai,local"

tts = get_tts_provider()  # DASHSCOPE_API_KEY + N3RV_TTS_* env
```

Implementations: `QwenProvider` (DashScope compat), `OpenAIProvider`, `LocalProvider` (Ollama/vLLM compat), `FallbackProvider`, `TTSProvider` / `TTSFallbackProvider`. All share `ProviderDefaults` from `n3rv.config`.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `N3RV_PROVIDER` | `qwen` | Active LLM provider: `qwen` · `openai` · `local` · `fallback` |
| `N3RV_DEFAULT_MODEL` | `qwen3-coder-plus` | Global default model ID |
| `N3RV_DEFAULT_BASE_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Global default base URL |
| `N3RV_FALLBACK_PROVIDERS` | — | Comma-separated fallback chain (e.g. `qwen,openai`) |
| `N3RV_TTS_FALLBACK_MODELS` | — | Comma-separated TTS models for `TTSFallbackProvider` |
| `N3RV_FALLBACK_MODELS` | — | Legacy alias, same as above |
| `DASHSCOPE_API_KEY` | — | Qwen/DashScope API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `N3RV_LOG_LEVEL` | `INFO` | `DEBUG`·`INFO`·`WARNING`·`ERROR` |
| `N3RV_AGENT_SOURCE` | `opencode` | Agent identity for memory attribution + hub routing |
| `N3RV_HUB_URL` | `http://127.0.0.1:19820` | Hub URL for MCP delegation |
| `N3RV_MEMORY_PROFILE` | `full` | `full` (all tools) or `safe` (read-only, no delete/prune) |
| `N3RV_EXEC_DEBOUNCE_MS` | `300` | Exec watcher debounce |
| `N3RV_CODE_GRAPH_NO_WATCH` | unset | Set `1`/`true` to disable code-graph watcher |
| `N3RV_EXEC_NO_WATCH` | unset | Set `1`/`true` to disable exec watcher |
| `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS` | unset | **Process env only** — `true` enables `background:true` subagents (`n3rv-scout`/`n3rv-sensor` parallel dispatch) |

Hub host/port can also be set in `.n3rv/a2a-config.yaml`:

```yaml
hub:
  host: 127.0.0.1
  port: 19820
project: my-project
```

## SDD Workflow

```
/sdd-new <change>  →  explore → propose → spec → design → tasks → apply → verify → archive
```

Each phase is an opencode skill (`sdd-*`) that saves to memory under `sdd-<change_id>-<phase>`. The hub tracks phase on the [The-Replacement Roadmap](https://github.com/orgs/The-Replacement/projects/2) when `--issue N` is passed.

- `n3rv converge <change_id> [--issue N]` — re-runs verify in converge mode and emits remediation tasks for any `FAIL`/`PARTIAL` acceptance criteria.
- **Spec-Kit path** (lighter, 3 artifacts) — `sdd-spec-kit-{spec,plan,tasks}` with templates under `.specify/templates/` (byte-identical to GitHub Spec Kit, see `NOTICE.md`).

Full detail: [docs/SDD-WORKFLOW.md](docs/SDD-WORKFLOW.md).

## Project Structure

```
src/n3rv/
├── cli.py, cli_memory.py, cli_code_graph.py, cli_org.py
├── config.py, platform.py, limits.py, daemon.py
├── providers/        # base, qwen, openai, local, fallback, tts, tts_fallback, factory
├── models/           # memory, a2a
├── a2a/              # hub, router, state, agent_cards
├── mcp/              # memory_service, memory_server, hub_server, exec_server, code_graph_*
│   ├── exec/         # registry (20+ langs), store, watcher, service
│   └── vector_store, relation_store, session_manager, conflict_store
└── init/             # init, update, renderer, detector, context, registry, lockfile
    └── templates/    # opencode.json, AGENTS.md, skills(18), agents(7), commands(8), plugins, hooks
docs/                 # ARCHITECTURE, DEPLOYMENT, MCP-TOOLS, SDD-WORKFLOW, index.html (n3rv.daza.ar)
tests/                # pytest — a2a, cli, init, mcp, org, providers, tools, limits, config
```

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest -q                          # or pytest -v --cov=src
mypy . --ignore-missing-imports || true
n3rv init --force                  # re-scaffold templates
```

CI (`.github/workflows/ci.yml`): `Lint & Format` + `Test 3.11/3.12/3.13` — 4 required checks, `strict:true`, `enforce_admins:true`, one approval, squash-merge only.

## Documentation

| Doc | Content |
|-----|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System overview, 4 MCP servers, Evangelion map, data flows, dispatch (native subagents vs hub) |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Install, `init`/`daemon`/`org`/`code-graph`, env vars, multi-agent machine, troubleshooting |
| [docs/MCP-TOOLS.md](docs/MCP-TOOLS.md) | All 31 tools — memory (12) + hub (5) + exec (8) + code-graph (6) |
| [docs/SDD-WORKFLOW.md](docs/SDD-WORKFLOW.md) | 8 phases, memory keys, converge, Spec-Kit, `change_id` convention |
| [EVANGELION.md](EVANGELION.md) | Full N3RV↔Evangelion concept map |
| [n3rv.daza.ar](https://n3rv.daza.ar) | Public landing (served from `docs/index.html`) |

> **Wiki:** the `docs/` directory *is* the wiki. The former `wiki-sync` workflow was removed — update `docs/*.md` directly; GitHub Wiki (if enabled) should mirror `docs/`.

## License

Apache-2.0. See `LICENSE`. Evangelion concepts are thematic metaphor only — not affiliated with Gainax/Khara.
