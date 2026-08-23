"""MCP server recommender — maps project characteristics to recommended MCP servers."""

from __future__ import annotations

import logging
from pathlib import Path

from n3rverberage.init.analyzer.profile import (
    MCPServerInfo,
    StructureInfo,
)
from n3rverberage.init.context import Stack

logger = logging.getLogger("n3rverberage.init.analyzer.mcp")


# ── Universal MCP servers (every project) ──────────────────────────

_UNIVERSAL_SERVERS: list[MCPServerInfo] = [
    MCPServerInfo(
        name="github",
        type="local",
        command=["npx", "-y", "@github/github-mcp-server"],
        environment={"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"},  # nosec — template variable, not a secret
        description="GitHub integration (repos, issues, PRs)",
    ),
    MCPServerInfo(
        name="context7",
        type="local",
        command=["npx", "-y", "@upstash/context7-mcp@latest"],
        description="Up-to-date documentation retrieval",
    ),
]

# ── Web frontend MCP servers ───────────────────────────────────────

_WEB_SERVERS: list[MCPServerInfo] = [
    MCPServerInfo(
        name="chrome-devtools",
        type="local",
        command=["npx", "-y", "chrome-devtools-mcp@latest"],
        description="Chrome DevTools for debugging and inspecting web pages",
    ),
]

# ── Python backend MCP servers ─────────────────────────────────────

_PYTHON_SERVERS: list[MCPServerInfo] = [
    MCPServerInfo(
        name="sequential-thinking",
        type="local",
        command=[
            "npx",
            "-y",
            "@modelcontextprotocol/server-sequential-thinking@latest",
        ],
        description="Complex reasoning and step-by-step analysis",
    ),
]


class MCPRecommender:
    """Detect which MCP servers to recommend based on project characteristics."""

    def detect(
        self,
        root: Path,
        stack: Stack,
        structure: StructureInfo,
    ) -> list[MCPServerInfo]:
        """Produce a deduplicated, ordered list of MCP server recommendations."""
        seen: set[str] = set()
        results: list[MCPServerInfo] = []

        # Always include universal servers
        for srv in _UNIVERSAL_SERVERS:
            if srv.name not in seen:
                seen.add(srv.name)
                results.append(srv)

        # Web frontend
        if structure.has_web_files or stack == Stack.NODE:
            for srv in _WEB_SERVERS:
                if srv.name not in seen:
                    seen.add(srv.name)
                    results.append(srv)

        # Python backend — sequential thinking helps with complex logic
        if stack == Stack.PYTHON:
            for srv in _PYTHON_SERVERS:
                if srv.name not in seen:
                    seen.add(srv.name)
                    results.append(srv)

        logger.debug(
            "MCP recommendations for %s (%s): %s",
            root.name,
            stack.value,
            [s.name for s in results],
        )
        return results
