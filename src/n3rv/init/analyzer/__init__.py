"""Project analyzer orchestrator — runs all detectors and produces a ProjectProfile."""

from __future__ import annotations

import logging
from pathlib import Path

from n3rv.init.analyzer.frameworks import FrameworkDetector
from n3rv.init.analyzer.mcp_recommender import MCPRecommender
from n3rv.init.analyzer.profile import ProjectProfile
from n3rv.init.analyzer.structure import StructureDetector
from n3rv.init.analyzer.tools import ToolDetector
from n3rv.init.context import ProjectContext

logger = logging.getLogger("n3rv.init.analyzer")


def analyze_project(root: Path, context: ProjectContext) -> ProjectProfile:
    """Run all detectors and build a ProjectProfile.

    Each detector is isolated — failure in one does not affect others.
    """
    stack = context.stack

    try:
        frameworks = FrameworkDetector().detect(root, stack)
    except Exception as exc:
        logger.debug("Framework detector failed: %s", exc)
        frameworks = []

    try:
        tools = ToolDetector().detect(root, stack)
    except Exception as exc:
        logger.debug("Tool detector failed: %s", exc)
        tools = []

    try:
        structure = StructureDetector().detect(root, stack)
    except Exception as exc:
        logger.debug("Structure detector failed: %s", exc)
        from n3rv.init.analyzer.profile import StructureInfo as _SI

        structure = _SI()

    try:
        mcp_servers = MCPRecommender().detect(root, stack, structure)
    except Exception as exc:
        logger.debug("MCP recommender failed: %s", exc)
        mcp_servers = []

    return ProjectProfile(
        stack=stack,
        project_name=context.project_name,
        frameworks=frameworks,
        tools=tools,
        structure=structure,
        mcp_servers=mcp_servers,
    )
