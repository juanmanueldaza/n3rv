/**
 * n3rv-shell-env plugin for OpenCode.
 *
 * Injects N3RV_AGENT_SOURCE into the environment of every shell subprocess.
 * Preserves an existing value if one is already set.
 *
 * OpenCode v2 plugin API: the module default-exports a definition with a
 * stable `id` and a `setup(ctx)` function. The factory-function form used by
 * v1 does not load in v2 ("Expected object at [\"default\"]").
 *
 * v1 -> v2 hook mapping:
 *   v1 `shell.env` (input, output)  ->  v2 ctx.shell.hook("create.before", event)
 *
 * Behavior change (v2): the `ShellCreateBefore` event carries
 * { command, cwd, timeout, shell, env } and no agent identifier, so the v1
 * agent-name -> source derivation is gone. Subagent-suffixed values such as
 * "opencode:sdd-apply" can no longer be derived from this hook. We now emit the
 * bare provider id, which matches the static N3RV_AGENT_SOURCE already set on
 * the n3rv MCP servers in opencode.json.
 */

const AGENT_SOURCE = "opencode";

export default {
  id: "n3rv-shell-env",

  async setup(ctx) {
    await ctx.shell.hook("create.before", (event) => {
      try {
        if (!event.env) return;

        // Never overwrite an already-set value.
        if (event.env.N3RV_AGENT_SOURCE) return;

        event.env.N3RV_AGENT_SOURCE = AGENT_SOURCE;
      } catch {
        // Degrade silently - never block OpenCode.
      }
    });
  },
};