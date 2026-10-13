from __future__ import annotations

from pathlib import Path


def _plugin_path(slug: str) -> Path:
    return Path(__file__).resolve().parents[2] / ".opencode" / "plugins" / f"n3rv-{slug}.js"


class TestLifecyclePlugin:
    def test_file_exists(self) -> None:
        assert _plugin_path("lifecycle").is_file()

    def test_exports_compacting_hook(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        assert 'ctx.session.hook("compaction"' in content

    def test_exports_idle_hook(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        assert "ctx.event.subscribe" in content
        assert "session.idle" in content

    def test_v1_factory_api_absent(self) -> None:
        # OpenCode v2 rejects the v1 factory-function shape with
        # SchemaError(Expected object at ["default"]).
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        assert 'id: "n3rv-lifecycle"' in content
        assert "async setup(ctx)" in content
        assert "export const NervLifecycle" not in content

    def test_injects_sdd_state_in_compacting(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        assert "sdd-" in content  # searches for SDD topic keys
        # v2 pushes onto event.system; setting event.result would replace the
        # summary and skip the model call entirely.
        assert "event.system.push" in content
        assert "SDD Pipeline State" in content
        # The rationale is documented in a comment; the assignment must not exist.
        assert "event.result =" not in content

    def test_idle_threshold_configured(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        assert "300_000" in content or "300000" in content  # default idle threshold

    def test_graceful_degradation_on_mcp_failure(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        assert "catch" in content  # try/catch present
        assert "Degrade silently" in content  # safe degradation comment

    def test_compacting_never_throws(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        # Should have try/catch wrapping the whole hook body
        assert "try {" in content
        assert "} catch" in content

    def test_memory_prune_uses_shared_rpc(self) -> None:
        # The v1 code inlined a fetch against a bare MEMORY_MCP_URL identifier
        # that was never defined, so pruning always raised ReferenceError and
        # was swallowed by the surrounding catch.
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        assert 'memoryRpc("memory_prune"' in content
        # The identifier is named in the doc-comment only, never dereferenced.
        assert "${MEMORY_MCP_URL}" not in content

    def test_idle_skips_without_sdd_activity(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        # Returns early if no SDD hits
        assert "sdd-" in content


class TestShellEnvPlugin:
    def test_file_exists(self) -> None:
        assert _plugin_path("shell-env").is_file()

    def test_exports_env_hook(self) -> None:
        content = _plugin_path("shell-env").read_text(encoding="utf-8")
        assert 'ctx.shell.hook("create.before"' in content

    def test_v1_factory_api_absent(self) -> None:
        content = _plugin_path("shell-env").read_text(encoding="utf-8")
        assert 'id: "n3rv-shell-env"' in content
        assert "async setup(ctx)" in content
        assert "export const NervShellEnv" not in content

    def test_preserves_existing_n3rv_agent_source(self) -> None:
        content = _plugin_path("shell-env").read_text(encoding="utf-8")
        assert "N3RV_AGENT_SOURCE" in content
        # Should check for existing value before overwriting
        assert "event.env.N3RV_AGENT_SOURCE" in content

    def test_no_agent_name_derivation(self) -> None:
        # OpenCode v2's ShellCreateBefore carries only
        # { command, cwd, timeout, shell, env } - there is no agent field, so
        # the v1 agent-name -> source mapping is not recoverable. The plugin
        # emits the bare provider id and the mapping must stay gone.
        content = _plugin_path("shell-env").read_text(encoding="utf-8")
        assert "opencode:n3rv" not in content
        assert "opencode:git-ops" not in content
        assert "deriveSource" not in content

    def test_never_throws(self) -> None:
        content = _plugin_path("shell-env").read_text(encoding="utf-8")
        assert "try {" in content
        assert "} catch" in content
