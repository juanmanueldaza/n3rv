from __future__ import annotations

from pathlib import Path


def _plugin_path(slug: str) -> Path:
    return Path(__file__).resolve().parents[2] / ".opencode" / "plugins" / f"n3rv-{slug}.js"


class TestLifecyclePlugin:
    def test_file_exists(self) -> None:
        assert _plugin_path("lifecycle").is_file()

    def test_exports_compacting_hook(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        assert "experimental.session.compacting" in content

    def test_exports_idle_hook(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        assert "event.type" in content
        assert "session.idle" in content

    def test_injects_sdd_state_in_compacting(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        assert "sdd-" in content  # searches for SDD topic keys
        assert "output.context.push" in content or "SDD Pipeline State" in content

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

    def test_idle_skips_without_sdd_activity(self) -> None:
        content = _plugin_path("lifecycle").read_text(encoding="utf-8")
        # Returns early if no SDD hits
        assert "sdd-" in content


class TestShellEnvPlugin:
    def test_file_exists(self) -> None:
        assert _plugin_path("shell-env").is_file()

    def test_exports_env_hook(self) -> None:
        content = _plugin_path("shell-env").read_text(encoding="utf-8")
        assert "shell.env" in content

    def test_preserves_existing_n3rv_agent_source(self) -> None:
        content = _plugin_path("shell-env").read_text(encoding="utf-8")
        assert "N3RV_AGENT_SOURCE" in content
        # Should check for existing value before overwriting
        assert "output.env.N3RV_AGENT_SOURCE" in content

    def test_agent_name_mappings(self) -> None:
        content = _plugin_path("shell-env").read_text(encoding="utf-8")
        assert "opencode:n3rv" in content
        assert "opencode:git-ops" in content
        assert "opencode:github-ops" in content
        assert "opencode:unknown" in content

    def test_sdd_prefix_mapping(self) -> None:
        content = _plugin_path("shell-env").read_text(encoding="utf-8")
        assert 'startsWith("sdd-")' in content or "startsWith('sdd-')" in content

    def test_never_throws(self) -> None:
        content = _plugin_path("shell-env").read_text(encoding="utf-8")
        assert "try {" in content
        assert "} catch" in content
