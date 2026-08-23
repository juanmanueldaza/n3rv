"""Tests for MCPRecommender — per-project MCP server recommendations."""

from __future__ import annotations

from pathlib import Path

from n3rv.init.analyzer.mcp_recommender import MCPRecommender
from n3rv.init.analyzer.profile import StructureInfo
from n3rv.init.context import Stack


class TestMCPRecommender:
    def test_universal_servers_always_included(self, tmp_path: Path) -> None:
        """Every project, regardless of stack, gets github and context7."""
        structure = StructureInfo()
        recommender = MCPRecommender()

        for stack in Stack:
            servers = recommender.detect(tmp_path, stack, structure)
            names = {s.name for s in servers}
            assert "github" in names, f"Missing github for stack={stack}"
            assert "context7" in names, f"Missing context7 for stack={stack}"

    def test_web_project_gets_chrome_devtools(self, tmp_path: Path) -> None:
        """Projects with web files get chrome-devtools MCP server."""
        structure = StructureInfo(has_web_files=True)
        recommender = MCPRecommender()

        servers = recommender.detect(tmp_path, Stack.GENERIC, structure)
        names = {s.name for s in servers}
        assert "chrome-devtools" in names

    def test_node_stack_gets_chrome_devtools_even_without_web_files(self, tmp_path: Path) -> None:
        """Node projects get chrome-devtools even if web files not explicitly detected."""
        structure = StructureInfo(has_web_files=False)
        recommender = MCPRecommender()

        servers = recommender.detect(tmp_path, Stack.NODE, structure)
        names = {s.name for s in servers}
        assert "chrome-devtools" in names

    def test_non_web_project_no_chrome_devtools(self, tmp_path: Path) -> None:
        """Non-web Python projects don't get chrome-devtools."""
        structure = StructureInfo(has_web_files=False)
        recommender = MCPRecommender()

        servers = recommender.detect(tmp_path, Stack.PYTHON, structure)
        names = {s.name for s in servers}
        assert "chrome-devtools" not in names

    def test_python_gets_sequential_thinking(self, tmp_path: Path) -> None:
        """Python projects get sequential-thinking for complex reasoning."""
        structure = StructureInfo()
        recommender = MCPRecommender()

        servers = recommender.detect(tmp_path, Stack.PYTHON, structure)
        names = {s.name for s in servers}
        assert "sequential-thinking" in names

    def test_generic_no_sequential_thinking(self, tmp_path: Path) -> None:
        """Non-Python projects don't get sequential-thinking."""
        structure = StructureInfo()
        recommender = MCPRecommender()

        for stack in (Stack.GENERIC, Stack.NODE, Stack.GO):
            servers = recommender.detect(tmp_path, stack, structure)
            names = {s.name for s in servers}
            assert "sequential-thinking" not in names, f"sequential-thinking present for stack={stack}"

    def test_no_duplicate_servers(self, tmp_path: Path) -> None:
        """Even when multiple conditions match, servers are deduplicated."""
        structure = StructureInfo(has_web_files=True)
        recommender = MCPRecommender()

        # Python + web should have sequential-thinking + chrome-devtools + universals
        servers = recommender.detect(tmp_path, Stack.PYTHON, structure)
        names = [s.name for s in servers]

        # Check no duplicates
        assert len(names) == len(set(names)), f"Duplicates found: {names}"
        # Expected: github, context7, chrome-devtools, sequential-thinking
        assert len(servers) == 4

    def test_servers_have_required_fields(self, tmp_path: Path) -> None:
        """All recommended servers have type and command (for local) or url (for remote)."""
        structure = StructureInfo(has_web_files=True)
        recommender = MCPRecommender()

        servers = recommender.detect(tmp_path, Stack.PYTHON, structure)
        for srv in servers:
            assert srv.name, "Server name is required"
            assert srv.type in ("local", "remote"), f"Invalid type for {srv.name}: {srv.type}"
            if srv.type == "local":
                assert srv.command, f"Local server {srv.name} missing command"
            else:
                assert srv.url, f"Remote server {srv.name} missing url"

    def test_universal_servers_consistent_across_stacks(self, tmp_path: Path) -> None:
        """The universal servers (github, context7) have identical config across stacks."""
        structure = StructureInfo()
        recommender = MCPRecommender()

        first = None
        for stack in Stack:
            servers = recommender.detect(tmp_path, stack, structure)
            universal = [s for s in servers if s.name in ("github", "context7")]
            current = {(s.name, tuple(s.command) if s.command else None, s.type) for s in universal}
            if first is None:
                first = current
            else:
                assert first == current, f"Universal servers differ for stack={stack}: {current} vs {first}"
