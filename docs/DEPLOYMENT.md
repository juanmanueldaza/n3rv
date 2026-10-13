# Deployment

N3RV is a local-only tool that runs as part of your development workflow. It is not designed for production server deployment.

## Development Machine

### Prerequisites

- Python >= 3.11
- pip (Python package manager)
- systemd (Linux) for daemon mode

### Install

```bash
git clone https://github.com/juanmanueldaza/n3rv.git
cd n3rv
pip install -e ".[dev]"
```

Entry points `n3rv`, `n3rv-memory`, `n3rv-hub`, `n3rv-code-graph`, `n3rv-exec` are available.

### Verify Installation

```bash
n3rv --help
n3rv-memory --help   # 12 memory tools
n3rv-hub --help      # 5 hub tools
n3rv code-graph --help
n3rv memory --help
n3rv org --help
```

## Using N3RV in a Project

### 1. Initialize

```bash
cd /path/to/your/project
n3rv init                          # auto-detect stack
n3rv init --stack python --force   # explicit + overwrite
```

This scaffolds:
- `AGENTS.md` — Coding standards and agent instructions (marker-merged on update)
- `.n3rv/a2a-config.yaml` — Hub configuration (`hub.host`/`hub.port`, `project`)
- `opencode.json` — MCP server configuration with 4 servers + `N3RV_AGENT_SOURCE` for opencode
- `.n3rv/systemd/n3rv-hub.service` — systemd user unit template
- `.opencode/` — Agent skills (18), agents (7), commands (8), plugins
- `.opencode/shared/` — Spec-Kit templates under `.specify/templates/` (via opencode template)
- `.githooks/pre-push` — Git hook for SDD verification
- `.n3rv/memory/` + `.n3rv/code_graph.db` + `.n3rv/exec.db` — created lazily on first use

### 2. Start the Hub

**Daemon mode (recommended):**

The daemon requires the systemd unit file created by `n3rv init`. Run init first, then:

```bash
n3rv daemon install   # install systemd user service
n3rv daemon enable --now  # enable on login + start now (equivalent to enable + start)
n3rv daemon status    # check status
n3rv daemon logs      # tail hub log file
n3rv daemon stop      # stop the daemon
```

**Foreground mode (development):**

```bash
n3rv hub start
```

The hub binds to `127.0.0.1:19820` by default. Change in `.n3rv/a2a-config.yaml`:

```yaml
hub:
  host: 127.0.0.1
  port: 19820
```

### 3. MCP Server Configuration

`n3rv init` generates an `opencode.json` with 4 MCP servers and env vars pre-configured:

```json
{
  "mcp": {
    "n3rv-memory": {
      "type": "local",
      "command": ["n3rv-memory"],
      "environment": { "N3RV_AGENT_SOURCE": "opencode" }
    },
    "n3rv-hub": {
      "type": "local",
      "command": ["n3rv-hub"],
      "environment": { "N3RV_AGENT_SOURCE": "opencode" }
    },
    "n3rv-code-graph": {
      "type": "local",
      "command": ["n3rv-code-graph"],
      "environment": { "N3RV_AGENT_SOURCE": "opencode" }
    },
    "n3rv-exec": {
      "type": "local",
      "command": ["n3rv-exec"],
      "environment": { "N3RV_AGENT_SOURCE": "opencode" }
    }
  }
}
```

### 4. Code Graph (optional, auto)

The code graph indexes lazily. Trigger explicitly if you want it warm:

```bash
n3rv code-graph init              # first index + reconcile
n3rv code-graph status            # files/symbols/imports/calls + pending
n3rv code-graph explore "memory_save" --max-nodes 20
```

The watcher keeps it fresh via `CodeGraphWatcher` (debounce `N3RV_EXEC_DEBOUNCE_MS`). Disable with `N3RV_CODE_GRAPH_NO_WATCH=1`. When files are pending, queries carry a `banner: "⚠️ Stale: … pending sync — Read it directly"`.

### 5. Org Workspace (multi-satellite, optional)

For `The-Replacement`-style orgs with many satellites:

```bash
n3rv org init --org-name The-Replacement         # creates .n3rv/org-config.yaml
n3rv org add-satellite my-satellite           # gh repo create + clone + n3rv init + register
n3rv org sync --dry-run                       # preview n3rv update across all satellites
n3rv org sync                                 # run update + regenerate skill registry
n3rv org protect --dry-run                    # preview branch protection from CI workflow checks
n3rv org protect                              # apply (required checks, 1 approval, admin enforce)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `N3RV_PROVIDER` | `qwen` | Active LLM provider: `qwen` · `openai` · `local` · `fallback` |
| `N3RV_DEFAULT_MODEL` | `qwen3-coder-plus` | Global default model ID |
| `N3RV_DEFAULT_BASE_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Global default API base URL |
| `N3RV_FALLBACK_PROVIDERS` | — | Comma-separated fallback chain (e.g. `qwen,openai,local`) |
| `N3RV_TTS_FALLBACK_MODELS` | — | Comma-separated TTS model IDs for `TTSFallbackProvider` |
| `DASHSCOPE_API_KEY` | — | Qwen/DashScope API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `N3RV_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `N3RV_AGENT_SOURCE` | `opencode` | Agent identifier for memory scope and hub operations |
| `N3RV_HUB_URL` | `http://127.0.0.1:19820` | Hub URL for MCP delegation |
| `N3RV_MEMORY_PROFILE` | `full` | Memory tool availability (`full` or `safe`) |
| `N3RV_EXEC_DEBOUNCE_MS` | `300` | Watcher debounce (exec + code-graph) |
| `N3RV_CODE_GRAPH_NO_WATCH` | unset | Set `1`/`true` to disable code-graph watcher |
| `N3RV_EXEC_NO_WATCH` | unset | Set `1`/`true` to disable exec watcher |
| `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS` | unset | **Process-env only, not an opencode.json key.** Set to `true` in the shell that launches `opencode` to enable `background: true` subagents (parallel dispatch of `n3rv-scout`/`n3rv-sensor` during SDD). n3rv agents degrade to foreground when unset. See ARCHITECTURE.md "Background subagents". |

Provider specifics: `N3RV_DEFAULT_MODEL`/`BASE_URL` are globals via `config.ProviderDefaults`; `DASHSCOPE_API_KEY` / `OPENAI_API_KEY` are read per-provider in `providers/qwen.py` / `openai.py`. `N3RV_FALLBACK_MODELS` is a legacy alias for `N3RV_TTS_FALLBACK_MODELS`.

## Multi-Agent Architecture

N3RV enables multiple opencode agents across different projects to coordinate through a shared hub and independent per-project memory.

### Architecture

```
Machine
├── n3rv hub daemon (systemd user service, localhost:19820)
│   ├── Routes tasks between agents by skill ID
│   ├── SSE streaming at GET /rpc/stream?agent_id=<id>
│   └── Task persistence in ~/.n3rv/hub-state/  (project-local) or .n3rv/hub-state/
│
├── Project A
│   ├── opencode instance → n3rv-memory (local ChromaDB .n3rv/memory/)
│   ├── n3rv-code-graph (sqlite .n3rv/code_graph.db + watcher)
│   ├── n3rv-exec (sqlite .n3rv/exec.db + watcher)
│   └── opencode instance → n3rv-hub (RPC to daemon)
│
├── Project B
│   ├── opencode instance → n3rv-memory (local ChromaDB)
│   └── opencode instance → n3rv-hub (RPC to daemon)
│
└── Project C ...
```

- **One hub daemon per machine** — all agents share a single task router
- **Per-project memory + code graph + exec cache** — each project has its own `.n3rv/` stores
- **Per-project MCP servers** — opencode launches all four as project-local `stdio` processes
- **Universal exec cache** — `inputHash = XXH3(fileHashes):configHash:toolHash` in `exec.db` (70×), `exec_affected` via code graph (50–75% prune)
- **Code graph** — Python AST (`ast` module) + FTS5 + call graph + `affected` transitive blast radius

### Task Flow

1. Agent A in Project A delegates: `delegate_task(skill_id="implementation", description="fix bug #42")`
2. Hub routes to Agent B (assigned by skill matching via `TaskRouter`)
3. Agent B polls: `check_pending_tasks()` → sees the task
4. Agent B completes: `complete_task(task_id, result)` → hub marks COMPLETED
5. SSE subscribers notified in real-time

### opencode Go/Zen Scaling Strategy

opencode Go subscription ($10/mo, $60/mo cap) provides per-request limits that constrain concurrent agent throughput. Choose models by workload:

| Workload | Model | Est. requests/mo (Go) | Cost efficiency |
|----------|-------|----------------------|-----------------|
| Bulk/boilerplate | DeepSeek V4 Flash | 158,150 | Cheapest |
| Standard coding | Qwen3.5 Plus | 50,500 | Great value |
| Complex tasks | GLM-5.1 / DeepSeek V4 Pro | 4,300 / 17,150 | Balanced |
| Critical/blocking | Zen free models | Unlimited (free) | Zero cost |

**Scaling tips:**
- Reserve paid models for Hub-routed tasks; use free Zen models for agent-internal work
- `N3RV_MEMORY_PROFILE=safe` disables destructive tools, saving tokens on safety checks
- Enable "Use balance" in opencode Go console to fall back to Zen credits when Go limit is hit
- Monitor usage: `opencode stats --days 7`

## Updating N3RV

```bash
cd /path/to/n3rv
git pull
pip install -e ".[dev]"
```

To update scaffolding in existing projects:

```bash
cd /path/to/your/project
n3rv update [--dry-run] [--diff] [--force-commands] [--only <files>]
# or across an org
n3rv org sync --dry-run
n3rv org sync
```

The daemon systemd unit is refreshed on update. `opencode.json` is JSON-merged (adds env vars without clobbering custom config). `AGENTS.md` is marker-merged. Skills/commands/agents are `overwrite` or `skip-default` per category.

## CI/CD Integration

N3RV's memory and hub components are local-only. Use the CLI for scaffolding:

```yaml
- name: Setup N3RV
  run: |
    pip install n3rv
    n3rv init --stack python --force
```

### Testing in CI

```bash
pytest -v --cov=src --cov-report=term-missing
ruff check . && ruff format --check .
```

Required CI checks on `main`: `Lint & Format`, `Test (Python 3.11/3.12/3.13)` — branch must be up-to-date (`strict: true`), 1 approval, squash-merge only. See `.github/workflows/ci.yml`.

## Troubleshooting

### Port Already in Use

```bash
lsof -i :19820
# or
ss -tlnp | grep 19820
```

Kill the process or change the port in `.n3rv/a2a-config.yaml`.

### Daemon Not Starting

```bash
n3rv daemon status                    # check systemd status
journalctl --user -u n3rv-hub -f     # view systemd journal
n3rv daemon logs                      # tail hub log file (.n3rv/logs/hub.log)
```

### ChromaDB Corruption

```bash
rm -rf .n3rv/memory/chroma/
```

### ONNXRuntime Unavailable

On Python 3.14 or Windows, ONNXRuntime may not have a compatible wheel. N3RV falls back to hash embeddings automatically. Search quality degrades to exact keyword matching.

### Code Graph Stale

If `banner: "⚠️ Stale: … pending sync"` appears, the watcher debounce hasn't fired yet. Either wait ~300ms or read the file directly:

```bash
n3rv code-graph sync
n3rv code-graph status
# or disable watcher in CI
N3RV_CODE_GRAPH_NO_WATCH=1 pytest -q
```

### Hub Connection Refused

1. Verify hub daemon is running: `n3rv daemon status`
2. Check direct connection: `curl http://127.0.0.1:19820/health`
3. Verify `N3RV_HUB_URL` matches your hub address
4. Check `.n3rv/a2a-config.yaml` for port conflicts
