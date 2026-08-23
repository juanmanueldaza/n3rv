/**
 * N3RV custom tools for OpenCode.
 *
 * These tools communicate with N3RV MCP servers via HTTP, bypassing the
 * MCP subprocess round-trip for faster LLM tool calls.
 *
 * All tools have a 2s hard timeout and return structured JSON on failure.
 *
 * Uses @opencode-ai/plugin tool() helper to avoid Zod version conflicts.
 */

import { tool } from "@opencode-ai/plugin";
import { memoryRpc, hubRpc, healthCheck } from "../shared/rpc.js";

// ──────────────────────────────────────────────
// Tools
// ──────────────────────────────────────────────

export const n3rv_memory_stats = tool({
  description: "Return aggregate counts for active memories in N3RV memory store.",
  args: {},
  async execute() {
    const result = await memoryRpc("memory_stats", {});
    if (result.error) {
      return JSON.stringify({ error: "memory_stats unavailable", detail: result.error });
    }
    return JSON.stringify(result);
  },
});

export const n3rv_task_status = tool({
  description: "Get the current state of an A2A hub task by its ID.",
  args: {
    task_id: tool.schema.string().describe("The task ID to look up"),
  },
  async execute(args) {
    const result = await hubRpc("get_task", { task_id: args.task_id });
    if (result.error) {
      return JSON.stringify({ error: "task_status unavailable", detail: result.error });
    }
    return JSON.stringify(result);
  },
});

export const n3rv_hub_health = tool({
  description: "Check whether the N3RV A2A hub is reachable and healthy.",
  args: {},
  async execute() {
    const result = await healthCheck();
    return JSON.stringify(result);
  },
});

export const n3rv_check_pending_tasks = tool({
  description:
    "List all pending tasks assigned to an agent. Falls back to N3RV_AGENT_SOURCE env var if agent_id omitted.",
  args: {
    agent_id: tool.schema
      .string()
      .optional()
      .describe("The agent ID to check. If omitted, uses N3RV_AGENT_SOURCE from environment."),
  },
  async execute(args) {
    const agentId = args.agent_id ?? process.env.N3RV_AGENT_SOURCE ?? "unknown";
    const result = await hubRpc("list_pending_tasks", { agent_id: agentId });
    if (result.error) {
      return JSON.stringify({ error: "check_pending_tasks unavailable", detail: result.error });
    }
    return JSON.stringify(result);
  },
});