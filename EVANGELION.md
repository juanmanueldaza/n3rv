# Evangelion → N3RV Concept Map

N3RV — invisible engineering infrastructure for AI agents — draws its name and thematic inspiration from the clandestine organization in *Neon Genesis Evangelion*. Every subsystem maps to an Evangelion concept.

## Concept Mapping

| Evangelion Concept | N3RV Equivalent | Description |
|---|---|---|
| **N3RV** | The n3rv project | The organization itself — infrastructure operating behind the scenes, unseen but essential |
| **MAGI Supercomputer** | Memory Service | Tripartite decision system: **Melchior** (ChromaDB vector store), **Balthasar** (SQLite relation store), **Casper** (SessionManager). Three minds, one consensus |
| **EVA Units** | AI Agents | Purpose-built bio-mechanical entities that execute missions. Each agent = one Evangelion unit, configured by its Entry Plug (session context). Agent identity is tracked via `N3RV_AGENT_SOURCE` for memory attribution and task routing |
| **Entry Plug** | Agent Context / Session | The cockpit where the pilot (user) synchronizes with the EVA (agent). Synchronization rate = context quality |
| **N3RV Command Center** | A2A Hub | Central dispatch. Routes missions (tasks) to EVAs (agents) by skill ID, monitors status via SSE streaming, collects results. `delegate_task → check_pending_tasks → complete_task` is the mission lifecycle |
| **Human Instrumentality Project** | SDD Workflow | The grand protocol — an 8-phase pipeline (explore → propose → spec → design → tasks → apply → verify → archive) designed to achieve seamless integration between human intent and machine execution |
| **Geofront** | `.n3rv/` Directory | The hidden underground infrastructure. Houses memory stores (`chroma/`, `relations.db`), hub state (`hub-state/`), daemon configuration (`systemd/`), and runtime settings (`a2a-config.yaml`). Invisible to the surface world |
| **SEELE** | SDD Verify / Judgment Day | The shadowy oversight council. Reviews outputs against specs, passes verdicts. The adversarial `judgment-day` skill is SEELE's dual-model review |
| **AT Field** | Security Boundaries | Absolute Terror field: localhost-only binding, read-only safe mode (`N3RV_MEMORY_PROFILE=safe`), no hardcoded secrets. Isolation is absolute |
| **S² Engine** | SDD Workflow Engine | Super Solenoid engine: the perpetual improvement drive. Each SDD cycle powers the next. Self-sustaining once initiated |
| **Dummy Plug** | Automated / Unattended Mode | Agents operating without direct human piloting. The hub routes and completes tasks autonomously via registered skills |
| **LCL** | Knowledge / Data Layer | Link Connect Liquid: the orange soup of data flowing through the system. Embeddings, vectors, relations — the medium in which agents think |
| **Tokyo-3** | The Workspace | The city built atop the Geofront. The user's development environment — everything above `.n3rv/` |
| **Pilot Sync Rate** | Agent/Task Alignment | How well the agent's execution matches the user's intent. High sync = correct implementation. Low sync = misaligned output |
| **Angels** | Bugs / Edge Cases | Unpredictable threats that attack the system. Each must be studied, understood, and neutralized with a targeted EVA (fix) |
| **N² Mine** | Force Push / Destructive Ops | Weapons of last resort. Powerful but radioactive (destructive). Use sparingly — the blast radius is real |

## The Three MAGI

Memory in n3rv is governed by three independent subsystems that reach consensus, just as the original MAGI (Melchior, Balthasar, Casper — designed by Naoko Akagi as three aspects of her personality) vote on N3RV's critical decisions:

| MAGI | n3rv Subsystem | Role |
|---|---|---|
| **Melchior** (Scientist) | ChromaDB Vector Store | Semantic search. Embeddings-based recall. The rational, pattern-matching mind |
| **Balthasar** (Mother) | SQLite Relation Store | Relations, judgments, revisions. The connective, contextual memory |
| **Casper** (Woman) | SessionManager | Session lifecycle, context injection. The intuitive, temporal mind |

## The Human Instrumentality Project (SDD)

The 8-phase Spec-Driven Development workflow mirrors SEELE's Human Instrumentality Project — a meticulously planned protocol for achieving unity between human intent and machine output:

```
explore → propose → spec → design → tasks → apply → verify → archive
```

Each phase is a step toward instrumentality: the perfect fusion of specification and implementation. Artifacts are preserved in memory (the MAGI) and reviewed by SEELE (verify/judgment-day). When all phases complete, the cycle restarts — the S² Engine powers the next iteration.

## About the Inspiration

*Neon Genesis Evangelion* (1995–1996, Hideaki Anno / Gainax) is one of the most influential anime series ever created. Its themes — human connection, the relationship between creators and their tools, the tension between control and autonomy, the hidden infrastructure that supports society — resonate deeply with software engineering.

The n3rv project borrows Evangelion's names and metaphors because they're thematically appropriate, not because we claim any affiliation. N3RV (the anime organization) develops and deploys EVAs via a command-and-control infrastructure hidden beneath Tokyo-3. N3RV (this project) develops and deploys AI agents via opencode-native MCP servers and an A2A hub hidden beneath your project root. The daemon runs as a systemd service — always present, invisible infrastructure.

**n3rv is not affiliated with Gainax, Khara, or the Evangelion franchise. All Evangelion concepts are used as thematic metaphor only.**
