# SDD Workflow

Spec-Driven Development (SDD) is an 8-phase workflow for making structured changes to a codebase. Each phase is implemented as an agent skill that reads from and writes to N3RV's persistent memory.

## Phases Overview

```
explore → propose → spec → design → tasks → apply → verify → archive
```

| Phase | Purpose | Memory Type | topic_key Pattern |
|--------|----------|-------------|-------------------|
| Explore | Investigate codebase, gather context | `context` | `sdd-<change_id>-context` |
| Propose | Generate 2-3 approaches, recommend one | `decision` | `sdd-<change_id>-proposal` |
| Spec | Write acceptance criteria and constraints | `context` | `sdd-<change_id>-spec` |
| Design | Technical design: components, interfaces, data flows | `architecture` | `sdd-<change_id>-design` |
| Tasks | Break design into atomic, ordered task list | `context` | `sdd-<change_id>-tasks` |
| Apply | Implement each task in order, run tests | `context` | `sdd-<change_id>-impl` |
| Verify | Check implementation against spec criteria | `context` | `sdd-<change_id>-verify` |
| Archive | Consolidate all artifacts into searchable summary | `summary` | `sdd-<change_id>-done` |

## Phase Details

### 1. Explore (`sdd-explore`)

**Goal:** Understand the current state of the codebase as it relates to the planned change. Read-only.

**What it does:**
- Searches memory for prior context on the topic
- Identifies relevant files, modules, directories
- Reads interfaces (not implementation details)
- Notes patterns, conventions, dependencies, test coverage, risks

**Output saved to memory:**
```
## Relevant Files
<file paths and their role>

## Key Patterns
<naming, structure, conventions observed>

## Dependencies
<what this change depends on or affects>

## Test Coverage
<existing tests relevant to this change>

## Risks
<potential pitfalls, breaking changes>
```

**Trigger:** Start of an SDD workflow, before any solution is proposed.

---

### 2. Propose (`sdd-propose`)

**Goal:** Generate 2-3 concrete approaches, evaluate trade-offs, recommend one.

**What it does:**
- Loads context from `sdd-<change_id>-context`
- Generates distinct approaches (obvious path + alternatives)
- Evaluates each: implementation complexity, reversibility, blast radius, testability
- Selects recommended approach with rationale

**Output saved to memory:**
```
## Approach A: <name>
<description, pros, cons>

## Approach B: <name>
<description, pros, cons>

## Approach C: <name> (if applicable)
<description, pros, cons>

## Recommended: <Approach X>
<rationale — why this one, why not the others>
```

**Constraints:**
- No implementation code
- Each approach must be genuinely distinct
- Unambiguous recommendation (one winner)

---

### 3. Spec (`sdd-spec`)

**Goal:** Define exactly what the change must do — precise enough for verification without ambiguity.

**What it does:**
- Loads proposal from `sdd-<change_id>-proposal`
- Loads context if needed from `sdd-<change_id>-context`
- Writes structured specification

**Output saved to memory:**
```
## Goals
<what this change achieves>

## Non-Goals
<explicit exclusions — what this change does NOT do>

## Acceptance Criteria
- [ ] <testable criterion 1>
- [ ] <testable criterion 2>
...

## Constraints
<technical, operational, backward-compatibility requirements>

## Out of Scope
<related work deferred to a future change>
```

**Quality bar:** Every acceptance criterion must be testable — binary pass/fail, no judgment calls.

---

### 4. Design (`sdd-design`)

**Goal:** Tell the implementer *how* to build what the spec describes.

**What it does:**
- Loads spec from `sdd-<change_id>-spec`
- Loads proposal from `sdd-<change_id>-proposal`
- Reads relevant source files to ground design in codebase
- Produces technical design

**Output saved to memory:**
```
## Components
<new or modified modules, classes, functions>

## Interfaces
<public API changes, function signatures, data models>

## Data Flow
<how data moves through the system for this change>

## Error Handling
<failure modes and how they are handled>

## Edge Cases
<boundary conditions, concurrency, empty input, large input>

## Dependencies
<new packages, external services, migration requirements>

## Testing Strategy
<unit tests needed, integration tests, fixtures>
```

**Constraints:**
- Design must be traceable to spec acceptance criteria
- No code snippets beyond signatures/pseudocode

---

### 5. Tasks (`sdd-tasks`)

**Goal:** Decompose design into smallest independent tasks that can each be implemented and reviewed in a single session.

**What it does:**
- Loads design from `sdd-<change_id>-design`
- Loads spec from `sdd-<change_id>-spec`
- Breaks work into atomic tasks
- Orders tasks so earlier ones unblock later ones

**Output saved to memory:**
```
## Task List

### T1: <title>
Files: <file paths>
What: <what to change>
Done when: <acceptance condition>

### T2: <title>
Files: <file paths>
What: <what to change>
Done when: <acceptance condition>

...

## Order Rationale
<why tasks are sequenced this way>
```

**Quality bar:**
- Each task is independently reviewable (no "and also" tasks)
- Every spec acceptance criterion covered by at least one task
- "Done when" conditions are testable

---

### 6. Apply (`sdd-apply`)

**Goal:** Implement all tasks in order, verifying each before moving on.

**What it does:**
- Loads tasks from `sdd-<change_id>-tasks`
- Loads design from `sdd-<change_id>-design`
- Loads spec from `sdd-<change_id>-spec`
- For each task:
  1. Implement the change
  2. Run test suite — fix failures before proceeding
  3. Verify "Done when" condition is met
- Saves implementation notes to memory

**Rules:**
- Do not add features beyond the task list
- Run tests after every task, not just at the end
- If task conflicts with design, note deviation — do not silently deviate
- Keep commits atomic: one task per commit

**Output saved to memory:**
Summary of what was changed, deviations from design, test results.

**Hub skill IDs:** `implementation`, `plan-execution`

---

### 7. Verify (`sdd-verify`)

**Goal:** Determine whether implementation satisfies every acceptance criterion.

**What it does:**
- Loads spec from `sdd-<change_id>-spec`
- Loads implementation notes from `sdd-<change_id>-impl`
- For each acceptance criterion:
  1. Read relevant code
  2. Run tests where applicable
  3. Mark as PASS, FAIL, or PARTIAL with evidence
- Checks for regressions (full test suite)

**Output saved to memory:**
```
## Acceptance Criteria Check

| Criterion | Status | Evidence |
|-----------|--------|----------|
| <criterion 1> | PASS/FAIL/PARTIAL | <file:line or test name> |
...

## Regression Check
<test suite result>

## Verdict
APPROVED / NEEDS_WORK

## Blocking Issues (if NEEDS_WORK)
<what must be fixed before approval>
```

**Verdict:**
- `APPROVED` → workflow proceeds to archive
- `NEEDS_WORK` → blocking issues returned for remediation

**Hub skill ID:** `review`

---

### 8. Archive (`sdd-archive`)

**Goal:** Consolidate all SDD phase artifacts into one searchable summary entry.

**What it does:**
- Loads all phase artifacts from memory (context, proposal, spec, design, tasks, impl, verify)
- Writes consolidated archive entry

**Output saved to memory:**
```
## Change: <change_id>
## Description: <original change request>
## Status: COMPLETE
## Approach taken: <one-sentence summary from proposal>
## Key design decisions: <2–3 bullet points from design>
## Tests added: <from impl notes>
## Verified: <date/session from verify>
## Artifacts: sdd-<change_id>-{context,proposal,spec,design,tasks,impl,verify}
```

This entry becomes the institutional memory for this change — searchable in future SDD runs when exploring related areas.

---

## Memory Flow Diagram

```
┌─────────────┐
│  explore    │ ──→ memory: sdd-X-context (type: context)
└──────┬──────┘
       ▼
┌─────────────┐
│  propose    │ ──→ memory: sdd-X-proposal (type: decision)
└──────┬──────┘
       ▼
┌─────────────┐
│    spec     │ ──→ memory: sdd-X-spec (type: context)
└──────┬──────┘
       ▼
┌─────────────┐
│   design    │ ──→ memory: sdd-X-design (type: architecture)
└──────┬──────┘
       ▼
┌─────────────┐
│   tasks     │ ──→ memory: sdd-X-tasks (type: context)
└──────┬──────┘
       ▼
┌─────────────┐
│    apply    │ ──→ memory: sdd-X-impl (type: context)
└──────┬──────┘
       ▼
┌─────────────┐
│   verify    │ ──→ memory: sdd-X-verify (type: context)
└──────┬──────┘
       ▼
┌─────────────┐
│   archive   │ ──→ memory: sdd-X-done (type: summary)
└─────────────┘
```

## Triggering the Workflow

The workflow is triggered by the opencode agent during development sessions. Each phase is a skill that can be invoked by the agent:

- `sdd-explore` — when starting to think through a feature
- `sdd-propose` — after exploration completes
- `sdd-spec` — after proposal is accepted
- `sdd-design` — after spec is written
- `sdd-tasks` — after design is complete
- `sdd-apply` — after task list is ready
- `sdd-verify` — after implementation completes
- `sdd-archive` — after verification passes

## `change_id` Naming Convention

Use a short, descriptive, dash-separated identifier:
- `add-user-auth`
- `fix-memory-leak`
- `refactor-cli-commands`

This becomes part of all `topic_key` values for the change, making all artifacts searchable together.
