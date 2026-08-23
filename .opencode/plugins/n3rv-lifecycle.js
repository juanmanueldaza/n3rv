/**
 * n3rv-lifecycle plugin for OpenCode.
 *
 * Two hooks:
 * 1. experimental.session.compacting — injects SDD pipeline state into
 *    compaction context so SDD state survives context overflow.
 * 2. event (session.idle) — auto-archives session summaries after 300s idle
 *    if SDD activity was detected.
 *
 * Uses the OpenCode 1.14.x plugin API: a factory function returning hooks.
 */

import { memoryRpc } from "../shared/rpc.js";

// ──────────────────────────────────────────────
// Internal: best-effort memory MCP wrappers
// ──────────────────────────────────────────────

async function memorySearch(query, limit = 10) {
  try {
    const result = await memoryRpc("memory_search", { query, limit });
    return result.error ? [] : (result ?? []);
  } catch {
    return [];
  }
}

async function memorySessionSummary(summaryText) {
  try {
    const result = await memoryRpc("memory_session_summary", { summary: summaryText });
    return !result.error;
  } catch {
    return false;
  }
}

// ──────────────────────────────────────────────
// SDD pipeline state
// ──────────────────────────────────────────────

const SDD_PHASES = [
  "context",
  "proposal",
  "spec",
  "design",
  "tasks",
  "impl",
  "verify",
];

/**
 * Reads SDD pipeline state from memory and builds a compact summary.
 */
async function buildSDDSummary() {
  const hits = await memorySearch("sdd-", 20);
  if (!hits || hits.length === 0) return null;

  // Group by change_id (extract from topic_key pattern: sdd-<change_id>-<phase>)
  const byChange = {};
  for (const hit of hits) {
    const key = hit.topic_key || hit.id || "";
    const match = key.match(/^sdd-(.+)-(.+)$/);
    if (!match) continue;
    const [, changeId, phase] = match;
    if (!byChange[changeId]) byChange[changeId] = {};
    byChange[changeId][phase] = hit;
  }

  // Build summary for the 3 most recent change_ids
  const sorted = Object.entries(byChange)
    .map(([changeId, phases]) => {
      const completedPhases = SDD_PHASES.filter((p) => phases[p]);
      const currentPhase = SDD_PHASES.find((p) => !phases[p]) ?? "done";
      return { changeId, completedPhases, currentPhase };
    })
    .sort((a, b) => b.completedPhases.length - a.completedPhases.length)
    .slice(0, 3);

  if (sorted.length === 0) return null;

  const lines = ["## SDD Pipeline State (survives compaction)"];
  for (const entry of sorted) {
    lines.push(
      `- **${entry.changeId}**: ${entry.completedPhases.length}/${SDD_PHASES.length} phases complete`,
    );
    lines.push(`  Next: \`${entry.currentPhase}\``);
    lines.push(`  Completed: ${entry.completedPhases.join(", ") || "none"}`);
    lines.push(
      `  Memory keys: ${entry.completedPhases.map((p) => `\`sdd-${entry.changeId}-${p}\``).join(", ")}`,
    );
  }

  return lines.join("\n");
}

// ──────────────────────────────────────────────
// Idle threshold
// ──────────────────────────────────────────────

const IDLE_THRESHOLD_MS = 300_000; // 5 minutes

// ──────────────────────────────────────────────
// Plugin factory (OpenCode 1.14.x API)
// ──────────────────────────────────────────────

export const NervLifecycle = async (_ctx) => {
  return {
    /**
     * Compaction hook: inject SDD pipeline state into compaction context.
     * This ensures SDD state survives context overflow.
     */
    "experimental.session.compacting": async (_input, output) => {
      try {
        const summary = await buildSDDSummary();
        if (summary) {
          output.context.push("\n\n" + summary);
        }
      } catch {
        // Degrade silently — never block compaction
      }
    },

    /**
     * Event hook: when a session goes idle, auto-archive a summary
     * if SDD activity was detected.
     */
    event: async ({ event }) => {
      try {
        if (event.type !== "session.idle") return;

        const idleMs =
          event.properties?.idleDurationMs ??
          event.properties?.idleDuration ??
          0;
        if (idleMs < IDLE_THRESHOLD_MS) return;

        // Only archive if SDD activity detected
        const hits = await memorySearch("sdd-", 3);
        if (!hits || hits.length === 0) return;

        const summary = `Session idle after ${Math.round(idleMs / 1000)}s. SDD activity detected (${hits.length} memory keys).`;
        await memorySessionSummary(summary);
      } catch {
        // Degrade silently — never block
      }
    },
  };
};

export default NervLifecycle;