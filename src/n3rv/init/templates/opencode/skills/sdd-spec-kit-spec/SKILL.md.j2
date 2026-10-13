---
name: sdd-spec-kit-spec
description: "Create a feature specification using spec-kit template format."
compatibility: opencode
when_to_use: "After sdd-propose. Creates a testable spec in the spec-kit format with goals, requirements, and acceptance criteria."
allowed-tools:
  - Bash
  - Read
  - mcp__n3rv-memory__memory_recall
  - mcp__n3rv-memory__memory_save
model: medium
effort: medium
user-invocable: false
---

## Goal

Produce a feature specification document using the canonical spec-kit template format
(`.specify/templates/spec-template.md`) — precise enough that an implementation can be verified
against it without ambiguity. Every acceptance criterion must be testable (binary pass/fail, no
judgment calls).

## Steps

1. Load proposal: `memory_recall(topic_key="sdd-<change_id>-proposal")`
2. Load context if needed: `memory_recall(topic_key="sdd-<change_id>-context")`
3. Prompt the user for feature details (name, branch id, prioritized user stories, edge cases,
   functional requirements, success criteria, assumptions)
4. Write the specification document using the canonical spec-kit template structure:
   - **Header**: `# Feature Specification: [FEATURE NAME]`, `**Feature Branch**`, `**Created**`,
     `**Status**`, `**Input**` (the original user description)
   - **User Scenarios & Testing** *(mandatory)*: Prioritized user stories as independent,
     testable slices. Each story carries a priority (P1, P2, P3...), a rationale, an
     independent test, and Given/When/Then acceptance scenarios. P1 is the MVP slice.
   - **Edge Cases**: Boundary conditions and error scenarios
   - **Requirements** *(mandatory)*: **Functional Requirements** as `FR-xxx` MUST statements,
     plus **Key Entities** if the feature involves data
   - **Success Criteria** *(mandatory)*: **Measurable Outcomes** as `SC-xxx` technology-agnostic
     metrics
   - **Assumptions**: Reached by reasonable defaults where the feature description was silent
5. Save to memory:
   - title: `SDD Spec (spec-kit): <change_id>`
   - topic_key: `sdd-<change_id>-spec-kit-spec`
   - type: `context`
   - content: the specification document
6. **Board Update**: Check your prompt for an issue number (look for `for issue #N` or `#<number>`). If found, execute the commands below with `<ISSUE_NUMBER>` replaced by that number. **If no issue number is present in your prompt, skip this entire section.**

   ```bash
   ITEM_ID=$(gh api graphql -f query='query{organization(login:"The-Replacement"){projectV2(number:2){items(first:100){nodes{id content{...on Issue{number}}}}}}}' --jq '.data.organization.projectV2.items.nodes[] | select(.content.number == <ISSUE_NUMBER>) | .id')
   [ -n "$ITEM_ID" ] && gh project item-edit --id "$ITEM_ID" --field-id PVTSSF_lADOEeFGTc4Bc5CtzhXejII --project-id PVT_kwDOEeFGTc4Bc5Ct --single-select-option-id 47fc9ee4
   [ -n "$ITEM_ID" ] && gh project item-edit --id "$ITEM_ID" --field-id PVTSSF_lADOEeFGTc4Bc5CtzhYUpaI --project-id PVT_kwDOEeFGTc4Bc5Ct --single-select-option-id 215b5bd3
   ```

## Quality Bar

Every acceptance criterion must be testable — binary pass/fail, no judgment calls. The spec must
follow the canonical spec-kit template structure with all of: User Scenarios & Testing (each
story prioritized and independently testable), Edge Cases, Requirements (FR-xxx), Success
Criteria (SC-xxx), and Assumptions.