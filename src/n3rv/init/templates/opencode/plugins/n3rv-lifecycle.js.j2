/**
 * n3rv-lifecycle plugin for OpenCode.
 *
 * Two hooks:
 * 1. session compaction - injects SDD pipeline state into the compaction
 *    request so SDD state survives context overflow.
 * 2. event stream (session.idle) - auto-archives session summaries after
 *    IDLE_THRESHOLD_MS of inactivity if SDD activity was detected, then
 *    auto-prunes old session memories.
 *
 * OpenCode v2 plugin API: the module default-exports a definition with a
 * stable `id` and a `setup(ctx)` function. The factory-function form used by
 * v1 does not load in v2 ("Expected object at [\"default\"]").
 *
 * v1 -> v2 hook mapping:
 *   v1 `experimental.session.compacting` (input, output)  ->  ctx.session.hook("compaction", event)
 *   v1 `event` hook                                       ->  ctx.event.subscribe({ signal })
 *
 * On compaction we push onto `event.system` instead of setting `event.result`:
 * `result` would replace the summary and skip the model call entirely.
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

/**
 * Triggers memory_prune for a given scope.
 *
 * Uses the shared memoryRpc helper. The v1 version inlined a fetch against a
 * bare `MEMORY_MCP_URL` identifier that was never defined in this module, so
 * every call raised a ReferenceError that the surrounding catch swallowed -
 * pruning never actually ran.
 */
async function memoryPrune(scope, typeFilter = null) {
  try {
    const params = { scope };
    if (typeFilter) params.type_filter = typeFilter;
    const result = await memoryRpc("memory_prune", params);
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
// Plugin definition (OpenCode v2 API)
// ──────────────────────────────────────────────

export default {
  id: "n3rv-lifecycle",

  async setup(ctx) {
    // Compaction hook: inject SDD pipeline state into the compaction request.
    await ctx.session.hook("compaction", async (event) => {
      try {
        const summary = await buildSDDSummary();
        if (summary) {
          event.system.push({ type: "text", text: summary });
        }
      } catch {
        // Degrade silently - never block compaction.
      }
    });

    // Event subscription: when a session goes idle, auto-archive a summary
    // if SDD activity was detected.
    const controller = new AbortController();
    let lastEventAt = Date.now();

    void (async () => {
      for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
        try {
          lastEventAt = Date.now();
          if (event?.type !== "session.idle") continue;

          // Prefer the reported duration; fall back to the gap since the last
          // observed event, which is the real idle time either way.
          const reported =
            event.properties?.idleDurationMs ?? event.properties?.idleDuration ?? 0;
          const idleMs = reported > 0 ? reported : Date.now() - lastEventAt;
          if (idleMs < IDLE_THRESHOLD_MS) return;

          // Only archive if SDD activity detected.
          const hits = await memorySearch("sdd-", 3);
          if (!hits || hits.length === 0) return;

          const summary = `Session idle after ${Math.round(idleMs / 1000)}s. SDD activity detected (${hits.length} memory keys).`;
          await memorySessionSummary(summary);

          // Auto-prune old session memories using config defaults.
          // This runs silently - failures don't block the lifecycle.
          await memoryPrune("session");
        } catch {
          // Degrade silently - never block.
        }
      }
    })();

    // Cleanup: abort the subscription when the plugin unloads.
    return () => controller.abort();
  },
};