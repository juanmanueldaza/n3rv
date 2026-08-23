# n3rv

**Invisible engineering infrastructure for opencode agents.**

Maintained by [Juan Manuel Daza](https://github.com/juanmanueldaza). Apache-2.0.

---

## What This Is

n3rv is a runtime library and config generator for [opencode](https://github.com/opencode-ai/opencode).
It bootstraps an opencode workspace with agent skills, MCP servers (memory, task delegation),
and provider abstraction for LLM APIs. Satellites use it at runtime for provider resolution.

**It is NOT a satellite.** It's the harness satellites plug into.

## Relation to Hub

| Repo | Role |
|------|------|
| `juanmanueldaza/n3rv` | Runtime engine: providers, A2A hub, memory, daemon, CLI, init |
| `reverberage/hub` | Contracts: satellite protocol, specs, roadmap, scaffold scripts |

Both are Apache-2.0. Hub ships the spec; this repo ships the implementation.

## Quick Start

```bash
pip install git+https://github.com/juanmanueldaza/n3rv.git
cd your-project
n3rv init
```

This generates: `AGENTS.md`, `opencode.json`, `.opencode/` (skills, agents, commands, plugins),
`.n3rv/` (memory, hub config), `.githooks/`.

## CLI

```
n3rv init [--stack python|node|go|generic] [--force]
n3rv update [--dry-run] [--force-commands]
n3rv hub start
n3rv daemon install|start|stop|status|enable|logs
n3rv memory list|search|prune|stats
n3rv org init|list|add|remove|protect
```

## Capabilities

- **Provider abstraction** — `ModelProvider` Protocol + `get_provider()` factory.
  Supports Qwen (DashScope), OpenAI, and local (Ollama/vLLM). Satellites resolve
  providers at runtime without hardcoding model IDs or API keys.
- **A2A Hub** — Cross-process agent-to-agent task delegation via HTTP
  (`127.0.0.1:19820`). Routes by `skill_id`, persists to JSON files.
- **MAGI Memory** — Dual-store: ChromaDB for semantic vector search, SQLite for
  relations. Persists SDD artifacts, session summaries, agent verdicts.
- **MCP Servers** — `n3rv-memory` (MCP stdio server for memory ops),
  `n3rv-hub` (MCP stdio server for A2A task delegation).
- **Config Generation** — Jinja2-templated generation of AGENTS.md, opencode.json,
  skills, commands, agents, plugins, git hooks.
- **Org Mode** — Multi-project workspace management with shared skills and GitHub
  branch protection.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DASHSCOPE_API_KEY` | — | Qwen/DashScope API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `N3RV_PROVIDER` | `qwen` | Active provider: `qwen`, `openai`, `local` |
| `N3RV_DEFAULT_MODEL` | `qwen3-coder-plus` | Default model ID |
| `N3RV_DEFAULT_BASE_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Default API base URL |

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

## License

Apache-2.0. Upstream (juanmanueldaza/n3rv) is GPL-2.0.
