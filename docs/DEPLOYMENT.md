# Deployment

N3RVERBERAGE is a local-only tool that runs as part of your development workflow. It is not designed for production server deployment.

## Development Machine

### Prerequisites

- Python >= 3.11
- pip (Python package manager)
- systemd (Linux) for daemon mode

### Install

```bash
git clone https://github.com/reverberage/n3rverberage.git
cd n3rverberage
pip install -e ".[dev]"
```

Entry points `n3rverberage`, `n3rverberage-memory`, and `n3rverberage-hub` are available.

### Verify Installation

```bash
n3rverberage --help
n3rverberage-memory --help
n3rverberage-hub --help
```

## Using N3RVERBERAGE in a Project

### 1. Initialize

```bash
cd /path/to/your/project
n3rverberage init
```

This scaffolds:
- `AGENTS.md` — Coding standards and agent instructions
- `.n3rverberage/a2a-config.yaml` — Hub configuration
- `opencode.json` — MCP server configuration with env vars for opencode
- `.n3rverberage/systemd/n3rverberage-hub.service` — systemd user unit template
- `.opencode/` — Agent skills, commands, and subagent definitions
- `.githooks/pre-push` — Git hook for SDD verification

### 2. Start the Hub

**Daemon mode (recommended):**

The daemon requires the systemd unit file created by `n3rverberage init`. Run init first, then:

```bash
n3rverberage daemon install   # install systemd user service
n3rverberage daemon enable --now  # enable on login + start now (equivalent to enable + start)
n3rverberage daemon status    # check status
n3rverberage daemon logs      # tail hub log file
n3rverberage daemon stop      # stop the daemon
```

**Foreground mode (development):**

```bash
n3rverberage hub start
```

The hub binds to `127.0.0.1:19820` by default. Change in `.n3rverberage/a2a-config.yaml`:

```yaml
hub:
  host: 127.0.0.1
  port: 19820
```

### 3. MCP Server Configuration

`n3rverberage init` generates an `opencode.json` with MCP servers and env vars pre-configured:

```json
{
  "mcp": {
    "n3rverberage-memory": {
      "type": "local",
      "command": ["n3rverberage-memory"],
      "environment": {"N3RVERBERAGE_AGENT_SOURCE": "opencode"}
    },
    "n3rverberage-hub": {
      "type": "local",
      "command": ["n3rverberage-hub"],
      "environment": {"N3RVERBERAGE_AGENT_SOURCE": "opencode"}
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `N3RVERBERAGE_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `N3RVERBERAGE_AGENT_SOURCE` | `opencode` | Agent identifier for memory scope and hub operations |
| `N3RVERBERAGE_HUB_URL` | `http://127.0.0.1:19820` | Hub URL for MCP delegation |
| `N3RVERBERAGE_MEMORY_PROFILE` | `full` | Memory tool availability (`full` or `safe`) |

## Multi-Agent Architecture

N3RVERBERAGE enables multiple opencode agents across different projects to coordinate through a shared hub and independent per-project memory.

### Architecture

```
Machine
├── n3rverberage hub daemon (systemd user service, localhost:19820)
│   ├── Routes tasks between agents by skill ID
│   ├── SSE streaming at GET /rpc/stream?agent_id=<id>
│   └── Task persistence in ~/.n3rverberage/hub-state/
│
├── Project A
│   ├── opencode instance → n3rverberage-memory (local ChromaDB)
│   └── opencode instance → n3rverberage-hub (RPC to daemon)
│
├── Project B
│   ├── opencode instance → n3rverberage-memory (local ChromaDB)
│   └── opencode instance → n3rverberage-hub (RPC to daemon)
│
└── Project C ...
```

- **One hub daemon per machine** — all agents share a single task router
- **Per-project memory** — each project has its own ChromaDB in `.n3rverberage/memory/`
- **Per-project MCP servers** — opencode launches `n3rverberage-memory` and `n3rverberage-hub` as project-local processes

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
- `N3RVERBERAGE_MEMORY_PROFILE=safe` disables destructive tools, saving tokens on safety checks
- Enable "Use balance" in opencode Go console to fall back to Zen credits when Go limit is hit
- Monitor usage: `opencode stats --days 7`

## Updating N3RVERBERAGE

```bash
cd /path/to/n3rverberage
git pull
pip install -e ".[dev]"
```

To update scaffolding in existing projects:

```bash
cd /path/to/your/project
n3rverberage update [--dry-run] [--force-commands] [--only <files>]
```

The daemon systemd unit is refreshed on update. `opencode.json` is JSON-merged (adds env vars without clobbering custom config).

## CI/CD Integration

N3RVERBERAGE's memory and hub components are local-only. Use the CLI for scaffolding:

```yaml
- name: Setup N3RVERBERAGE
  run: |
    pip install n3rverberage
    n3rverberage init --stack python --force
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

Kill the process or change the port in `.n3rverberage/a2a-config.yaml`.

### Daemon Not Starting

```bash
n3rverberage daemon status                    # check systemd status
journalctl --user -u n3rverberage-hub -f     # view systemd journal
n3rverberage daemon logs                      # tail hub log file (.n3rverberage/logs/hub.log)
```

### ChromaDB Corruption

```bash
rm -rf .n3rverberage/memory/chroma/
```

### ONNXRuntime Unavailable

On Python 3.14 or Windows, ONNXRuntime may not have a compatible wheel. N3RVERBERAGE falls back to hash embeddings automatically. Search quality degrades to exact keyword matching.

### Hub Connection Refused

1. Verify hub daemon is running: `n3rverberage daemon status`
2. Check direct connection: `curl http://127.0.0.1:19820/health`
3. Verify `N3RVERBERAGE_HUB_URL` matches your hub address
4. Check `.n3rverberage/a2a-config.yaml` for port conflicts
