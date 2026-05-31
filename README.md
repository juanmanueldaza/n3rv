```
█████████████████████████████████████████████████████████

██    ██  ███████  ████████  ██     ██
███   ██ ██     ██ ██     ██ ██     ██
████  ██        ██ ██     ██ ██     ██
██ ██ ██  ███████  ████████  ██     ██
██  ████        ██ ██   ██    ██   ██
██   ███ ██     ██ ██    ██    ██ ██
██    ██  ███████  ██     ██    ███

  Because an angel without a harness is unmanageable.
  And a harness without an angel is just expensive metal.

█████████████████████████████████████████████████████████
```

`n3rv` is an open-source engineering harness designed to contain, restrain, and orchestrate Large Language Models (LLMs). Instead of treating agents as independent chatbots, N3RV builds a rigid operational framework — handling tools, dual-store memory, and real-time project context injection. Integrates natively with opencode via MCP servers, agent skills, slash commands, and sub-agents.

[Architecture](docs/ARCHITECTURE.md) • [SDD Workflow](docs/SDD-WORKFLOW.md) • [MCP Tools](docs/MCP-TOOLS.md) • [Deployment](docs/DEPLOYMENT.md) • [Evangelion](EVANGELION.md) • [Security](SECURITY.md) • [Contributing](CONTRIBUTING.md)

---

## ⚡ Core Architecture

The base model is the Angel: raw, uncontained, and unpredictable. N3RV is the restraint harness that binds it to your local development environment.

*   **MAGI Consensus Architecture:** Dual-layer memory routing utilizing **ChromaDB** for semantic long-term retrieval and **SQLite** for rigid ACID-compliant session state tracking (verdicts, relations).
*   **LCL Project Injection:** Automatic parsing of environment manifests (`pyproject.toml`, `package.json`). The agent "breathes" your project architecture from session one.
*   **14 Synchronized Agent Skills (The EVAs):** Specialized skill files for distinct phases of the software development lifecycle — code, testing, commits, GitHub ops, git ops, SDD (explore → propose → spec → design → tasks → apply → verify → archive), judgment-day review.
*   **10 Sub-Agents:** Dedicated agent configs for each SDD phase + git-ops + github-ops, isolated by responsibility.
*   **MCP Protocol Integration:** 5 native MCP servers — n3rv-memory (semantic + relational memory), n3rv-hub (A2A task delegation), GitHub wrapper, Context7 contextual search, sequential-thinking.

---

## 🚀 Synchronization Sequence

Initialize the harness inside your local repository:

```bash
uv tool install git+https://github.com/juanmanueldaza/n3rv.git
cd your-project
n3rv init
```

Or run without installing:

```bash
uvx --from git+https://github.com/juanmanueldaza/n3rv.git n3rv init
```

`n3rv init` provisions your workspace with:

```
📂 Project root
├── 📄 AGENTS.md              # Coding standards with LCL-injected project context
├── 📄 opencode.json          # opencode config: MCP servers, agents, instructions
├── 📄 CONTRIBUTING.md
├── 📄 SECURITY.md
├── 📂 .opencode/
│   ├── 📂 skills/            # 14 skills (code, testing, commits, SDD phases, etc.)
│   ├── 📂 agents/            # 10 sub-agents (SDD phases + git-ops + github-ops)
│   ├── 📂 commands/          # 4 slash commands (sdd-new, judgment-day, review, handoff)
│   ├── 📂 plugins/           # lifecycle & shell-env plugins
│   └── 📂 scripts/           # MCP wrapper scripts
├── 📂 .n3rv/
│   ├── 📄 a2a-config.yaml    # Agent-to-Agent hub configuration
│   ├── 📄 skill-registry.md  # Auto-generated skill index
│   ├── 📂 memory/            # ChromaDB + SQLite (MAGI storage)
│   └── 📂 systemd/           # Background service unit
└── 📂 .githooks/
    └── 📄 pre-push            # Git pre-push hook
```

---

## 🛠️ Usage

```bash
n3rv init [--stack python|node|go|generic] [--force]
n3rv update [--dry-run] [--force-commands]
n3rv hub start                          # foreground A2A hub (development)
n3rv daemon install|start|stop|status|enable|logs   # background service
n3rv memory list|search|prune|stats     # MAGI memory operations
```

### MCP Servers (auto-configured in opencode.json)

| Server | Purpose |
|--------|---------|
| `n3rv-memory` | ChromaDB + SQLite dual-store memory |
| `n3rv-hub` | A2A task delegation (JSON-RPC 2.0) |
| `github` | GitHub API via MCP |
| `context7` | Contextual search across codebase |
| `sequential-thinking` | Chain-of-thought reasoning |

---

## 🧠 Memory: The MAGI

Dual-store persistent memory:

- **ChromaDB** — Vector embeddings for semantic long-term recall
- **SQLite** — Relations between memories (judgments, revisions, verdicts)

Memory types: `architecture`, `bugfix`, `config`, `decision`, `discovery`, `learning`, `pattern`, `context`, `summary`, `note`.

Scopes: `project` (shared), `session` (current), `personal` (agent-specific).

---

## 📋 SDD Workflow

8-phase Spec-Driven Development pipeline, started via `/sdd-new <change>`:

```
explore → propose → spec → design → tasks → apply → verify → archive
```

Each phase is a dedicated skill + sub-agent. Phases write to persistent memory with `topic_key: sdd-<change_id>-<phase>`.

---

## 🗺️ Project Status

N3RV is currently under active development, built in public. We are testing restraint stability and optimizing context-delivery pipelines.

**Install from source after updates:**

```bash
cd ~/Projects/n3rv && git pull && uv tool install --reinstall .
```

---

## 📄 License

Distributed under the **GNU General Public License v2.0 (GPL-2.0)**. N3RV is copyleft software — keeping the armor open ensures the angels stay contained.

---

<p align="center">
  <b>God's in his heaven. All's right with the world.</b>
</p>
