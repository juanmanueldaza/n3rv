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

Entry points `n3rv`, `n3rv-memory`, and `n3rv-hub` are available.

### Verify Installation

```bash
n3rv --help
n3rv-memory --help
n3rv-hub --help
```

## Using N3RV in a Project

### 1. Initialize

```bash
cd /path/to/your/project
n3rv init
```

This scaffolds:
- `AGENTS.md` — Coding standards and agent instructions
- `.n3rv/a2a-config.yaml` — Hub configuration
- `opencode.json` — MCP server configuration with env vars for opencode
- `.n3rv/systemd/n3rv-hub.service` — systemd user unit template
- `.opencode/` — Agent skills, commands, and subagent definitions
- `.githooks/pre-push` — Git hook for SDD verification

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

`n3rv init` generates an `opencode.json` with MCP servers and env vars pre-configured:

```json
{
  "mcp": {
    "n3rv-memory": {
      "type": "local",
      "command": ["n3rv-memory"],
      "environment": {"N3RV_AGENT_SOURCE": "opencode"}
    },
    "n3rv-hub": {
      "type": "local",
      "command": ["n3rv-hub"],
      "environment": {"N3RV_AGENT_SOURCE": "opencode"}
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `N3RV_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `N3RV_AGENT_SOURCE` | `opencode` | Agent identifier for memory scope and hub operations |
| `N3RV_HUB_URL` | `http://127.0.0.1:19820` | Hub URL for MCP delegation |
| `N3RV_MEMORY_PROFILE` | `full` | Memory tool availability (`full` or `safe`) |
| `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS` | unset | **Process-env only, not an opencode.json key.** Set to `true` in the shell that launches `opencode` to enable `background: true` subagents (parallel dispatch of `n3rv-scout`/`n3rv-sensor` during SDD). n3rv agents degrade to foreground when unset. See ARCHITECTURE.md "Background subagents". |

## Multi-Agent Architecture

N3RV enables multiple opencode agents across different projects to coordinate through a shared hub and independent per-project memory.

### Architecture

```
Machine
├── n3rv hub daemon (systemd user service, localhost:19820)
│   ├── Routes tasks between agents by skill ID
│   ├── SSE streaming at GET /rpc/stream?agent_id=<id>
│   └── Task persistence in ~/.n3rv/hub-state/
│
├── Project A
│   ├── opencode instance → n3rv-memory (local ChromaDB)
│   └── opencode instance → n3rv-hub (RPC to daemon)
│
├── Project B
│   ├── opencode instance → n3rv-memory (local ChromaDB)
│   └── opencode instance → n3rv-hub (RPC to daemon)
│
└── Project C ...
```

- **One hub daemon per machine** — all agents share a single task router
- **Per-project memory** — each project has its own ChromaDB in `.n3rv/memory/`
- **Per-project MCP servers** — opencode launches `n3rv-memory` and `n3rv-hub` as project-local processes

### Task Flow

1. Agent A in Project A delegates: `delegate_task(skill_id="implementation", description="fix bug #42")`
2. Hub routes to Agent B (assigned by skill matching)
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
n3rv update [--dry-run] [--force-commands] [--only <files>]
```

The daemon systemd unit is refreshed on update. `opencode.json` is JSON-merged (adds env vars without clobbering custom config).

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
pytest
```

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

### Hub Connection Refused

1. Verify hub daemon is running: `n3rv daemon status`
2. Check direct connection: `curl http://127.0.0.1:19820/health`
3. Verify `N3RV_HUB_URL` matches your hub address
4. Check `.n3rv/a2a-config.yaml` for port conflicts
