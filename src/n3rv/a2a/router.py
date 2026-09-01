from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from n3rv.mcp.memory_service import MemoryService
from n3rv.models.a2a import AgentSkill, NervAgentCard

if TYPE_CHECKING:
    from n3rv.init.registry import SkillRegistry

logger = logging.getLogger("n3rv.router")


@dataclass(frozen=True)
class RoutingDecision:
    agent_id: str
    card: NervAgentCard
    skill: AgentSkill
    context: list[dict]


class SkillNotFoundError(RuntimeError):
    pass


# Agent-name ↔ skill-id mismatch is a common footgun (e.g. sdd-explorer vs sdd-explore).
# Alias legacy/agent-style ids to canonical skill ids so both work.
_SKILL_ALIASES: dict[str, str] = {
    "sdd-explorer": "sdd-explore",
    "sdd-proposer": "sdd-propose",
    "sdd-speccer": "sdd-spec",
    "sdd-designer": "sdd-design",
    "sdd-task-planner": "sdd-tasks",
    "sdd-verifier": "sdd-verify",
    "sdd-archiver": "sdd-archive",
}


class TaskRouter:
    """Routes delegation requests to registered agents by skill ID."""

    def __init__(
        self,
        *,
        cards: dict[str, NervAgentCard],
        memory_service: MemoryService | None = None,
        registry: SkillRegistry | None = None,
    ) -> None:
        self.cards = cards
        self.memory_service = memory_service
        self.registry = registry

    async def route(
        self,
        *,
        skill_id: str | None,
        description: str,
        requesting_agent: str,
    ) -> RoutingDecision:
        """Route a task to an agent by skill_id.

        Infers skill from description if skill_id is None.
        Prepends skill docs from registry to context.
        """
        skill_id = skill_id or self._infer_skill(description)
        # Normalize alias (e.g. sdd-explorer -> sdd-explore) before matching
        if skill_id in _SKILL_ALIASES:
            alias = skill_id
            skill_id = _SKILL_ALIASES[skill_id]
            logger.debug("aliased skill %s -> %s", alias, skill_id)
        logger.debug("routing skill=%s from=%s", skill_id, requesting_agent)
        candidates: list[tuple[str, NervAgentCard, AgentSkill]] = []
        for agent_id, card in self.cards.items():
            if agent_id == "hub":
                continue
            for skill in card.skills:
                if skill.id == skill_id:
                    candidates.append((agent_id, card, skill))
        if not candidates:
            logger.warning("no agent found for skill=%s", skill_id)
            raise SkillNotFoundError(skill_id or description)

        agent_id, card, skill = candidates[0]

        logger.debug("memory_search for context agent=%s", agent_id)
        context: list[dict] = []
        if self.memory_service:
            try:
                search_response = self.memory_service.memory_search(query=description[:1000], limit=5)
                context = search_response.get("results", [])
            except Exception:
                logger.warning(
                    "memory_search failed during routing (continuing without context)",
                    exc_info=True,
                )

        if self.registry:
            skill_entries = self.registry.find_by_skill_id(skill_id)
            skill_context = [e.as_context_item() for e in skill_entries]
            if skill_context:
                logger.debug(
                    "injecting %d skill doc(s) for skill=%s",
                    len(skill_context),
                    skill_id,
                )
            context = skill_context + context

        logger.info(
            "routed skill=%s -> agent=%s context_items=%d",
            skill_id,
            agent_id,
            len(context),
        )
        return RoutingDecision(agent_id=agent_id, card=card, skill=skill, context=context)

    def _infer_skill(self, description: str) -> str:
        """Infer skill_id from description keywords.

        Falls back to 'implementation' if no keyword matches.
        """
        lower = description.lower()
        mapping = {
            "implementation": ("implement", "implementation", "code", "build"),
            "refactoring": ("refactor", "cleanup"),
            "file-ops": ("file", "move", "rename"),
            "plan-execution": ("plan", "execute"),
        }
        for skill_id, keywords in mapping.items():
            if any(keyword in lower for keyword in keywords):
                return skill_id
        return "implementation"
