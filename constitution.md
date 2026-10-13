# [PROJECT_NAME] Constitution
<!-- Spec-Driven Development Project Principles -->

**Generated**: [DATE]
**Project**: [PROJECT_NAME]
**Stack**: [STACK]

## Core Principles

### [PRINCIPLE_1_NAME]
[PRINCIPLE_1_DESCRIPTION]

*Example: I. Library-First*
> Every feature starts as a standalone library; Libraries must be self-contained, independently testable, documented; Clear purpose required - no organizational-only libraries

### [PRINCIPLE_2_NAME]
[PRINCIPLE_2_DESCRIPTION]

*Example: II. CLI Interface*
> Every library exposes functionality via CLI; Text in/out protocol: stdin/args → stdout, errors → stderr; Support JSON + human-readable formats

### [PRINCIPLE_3_NAME]
[PRINCIPLE_3_DESCRIPTION]

*Example: III. Test-First (NON-NEGOTIABLE)*
> TDD mandatory: Tests written → User approved → Tests fail → Then implement; Red-Green-Refactor cycle strictly enforced

### [PRINCIPLE_4_NAME]
[PRINCIPLE_4_DESCRIPTION]

*Example: IV. Integration Testing*
> Focus areas requiring integration tests: New library contract tests, Contract changes, Inter-service communication, Shared schemas

### [PRINCIPLE_5_NAME]
[PRINCIPLE_5_DESCRIPTION]

*Example: V. Observability, VI. Versioning & Breaking Changes, VII. Simplicity*
> Text I/O ensures debuggability; Structured logging required; Or: MAJOR.MINOR.BUILD format; Or: Start simple, YAGNI principles

## Constraints & Boundaries

### Technology Stack Requirements
- [Required frameworks, languages, or tools]
- [Prohibited patterns or anti-patterns]
- [Deployment environment constraints]

### Data & Interface Contracts
- [Input/output format requirements]
- [Schema validation requirements]
- [Backward compatibility constraints]

### Quality Gates
- [Minimum test coverage requirements]
- [Linting/formatting non-negotiables]
- [Security scanning requirements]

## Development Workflow

### SDD Pipeline Integration
- [ ] Specifications drive implementation (not vice versa)
- [ ] Acceptance criteria must be testable (binary pass/fail)
- [ ] Every acceptance criterion covered by at least one task
- [ ] Design traceable to spec acceptance criteria

### SDD Phase Guidelines
- **Explore**: Read-only investigation; note patterns, conventions, dependencies, risks
- **Propose**: 2-3 distinct approaches with trade-offs; unambiguous recommendation
- **Spec**: Goals, non-goals, testable acceptance criteria, constraints, out of scope
- **Design**: Components, interfaces, data flows; traceable to spec; edge cases documented
- **Tasks**: Atomic, reviewable tasks; ordered so earlier unblock later; "done when" conditions testable
- **Apply**: One task per commit; run tests after each task; no silent deviations from design
- **Verify**: Check each acceptance criterion; PASS/FAIL/PARTIAL with evidence; full regression check
- **Archive**: Consolidate all phases into searchable summary; become institutional memory

### Spec-Kit Workflow (Optional)
When using the spec-kit integration, the following file conventions apply alongside the SDD
pipeline. These specs are stored as Markdown files in the feature directory and mirror the
SDD memory artifacts:

| Spec-Kit File | Purpose | Maps to |
|---------------|---------|---------|
| `specs/<feature>/spec.md` | Feature specification | SDD Spec phase |
| `specs/<feature>/plan.md` | Implementation plan | SDD Design phase |
| `specs/<feature>/tasks.md` | Ordered task checklist | SDD Tasks phase |
| `.specify/feature.json` | Feature metadata | SDD context |

- **Constitution Check**: Every spec and plan MUST be evaluated against this constitution's
  principles. Conflicts with a MUST are treated as CRITICAL.
- **Templates**: Use the bundled spec-template, plan-template, and tasks-template to keep
  artifacts consistent and machine-parseable.
- **Testability**: Every requirement and acceptance criterion in a spec-kit spec MUST be
  testable — binary pass/fail, no judgment calls.
- **Order Rationale**: Tasks MUST be sequenced so earlier tasks unblock later ones; each task
  MUST carry a testable "done when" condition.
- **Feature metadata**: The `.specify/feature.json` file records the feature directory path
  and is read by every spec-kit command to locate artifacts.

### Constitution Governance
- **Amendments**: Require documentation, approval, migration plan
- **Supersedes**: Constitution overrides all other practices
- **Review**: Constitution reviewed at project milestones (major version bumps)
- **Guidance**: Use `.n3rv/guidance.md` for runtime development guidance (not committed)

## Governance

[GOVERNANCE_RULES]

*Example: All PRs/reviews must verify constitution compliance; Complexity must be justified; Use .n3rv/guidance.md for runtime development guidance*

**Version**: [CONSTITUTION_VERSION] | **Ratified**: [RATIFICATION_DATE] | **Last Amended**: [LAST_AMENDED_DATE]

<!-- Example: Version: 1.0.0 | Ratified: 2026-08-29 | Last Amended: -- -->