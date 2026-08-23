from __future__ import annotations

import logging
from pathlib import Path

from n3rv.config import RuntimeSettings
from n3rv.models.a2a import AgentCapabilities, AgentSkill, NervAgentCard

logger = logging.getLogger("n3rv.agent_cards")


def hub_agent_card(settings: RuntimeSettings) -> NervAgentCard:
    return NervAgentCard(
        name="n3rv-hub",
        description="Orchestration hub - routes tasks between agents.",
        url=settings.a2a_base_url,
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="orchestration",
                name="Task Orchestration",
                description="Route tasks to the best-fit agent based on skill matching.",
            ),
        ],
    )


def opencode_agent_card(settings: RuntimeSettings) -> NervAgentCard:
    return NervAgentCard(
        name="opencode",
        description="Code generation, implementation, refactoring, and plan execution agent.",
        url=f"{settings.a2a_base_url}/agents/opencode",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="implementation",
                name="Code Implementation",
                description="Generate production code from designs, specs, or instructions.",
            ),
            AgentSkill(
                id="refactoring",
                name="Code Refactoring",
                description="Restructure existing code while preserving behavior.",
            ),
            AgentSkill(
                id="file-ops",
                name="File Operations",
                description="Create, move, rename, and bulk-edit files across the project tree.",
            ),
            AgentSkill(
                id="plan-execution",
                name="Plan Execution",
                description="Execute step-by-step implementation plans.",
            ),
        ],
    )


def sdd_explorer_card(settings: RuntimeSettings) -> NervAgentCard:
    return NervAgentCard(
        name="n3rv-sdd-explorer",
        description="Explore the codebase to build context for a planned change. First phase of the SDD workflow.",
        url=f"{settings.a2a_base_url}/agents/sdd-explorer",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="sdd-explore",
                name="SDD Explore",
                description="Explore the codebase to build context for a planned change.",
            ),
        ],
    )


def sdd_proposer_card(settings: RuntimeSettings) -> NervAgentCard:
    return NervAgentCard(
        name="n3rv-sdd-proposer",
        description="Propose 2-3 solution approaches for a planned change, evaluating trade-offs and recommending one.",
        url=f"{settings.a2a_base_url}/agents/sdd-proposer",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="sdd-propose",
                name="SDD Propose",
                description="Propose solution approaches with trade-off analysis.",
            ),
        ],
    )


def sdd_speccer_card(settings: RuntimeSettings) -> NervAgentCard:
    return NervAgentCard(
        name="n3rv-sdd-speccer",
        description="Write a formal specification for a planned change: goals, acceptance criteria, constraints.",
        url=f"{settings.a2a_base_url}/agents/sdd-speccer",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="sdd-spec",
                name="SDD Spec",
                description="Write formal specifications with acceptance criteria.",
            ),
        ],
    )


def sdd_designer_card(settings: RuntimeSettings) -> NervAgentCard:
    return NervAgentCard(
        name="n3rv-sdd-designer",
        description="Write the technical design for a planned change: components, interfaces, data flows, edge cases.",
        url=f"{settings.a2a_base_url}/agents/sdd-designer",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="sdd-design",
                name="SDD Design",
                description="Create technical design with components and data flow.",
            ),
        ],
    )


def sdd_task_planner_card(settings: RuntimeSettings) -> NervAgentCard:
    return NervAgentCard(
        name="n3rv-sdd-task-planner",
        description="Break the technical design into an ordered list of atomic, reviewable implementation tasks.",
        url=f"{settings.a2a_base_url}/agents/sdd-task-planner",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="sdd-tasks",
                name="SDD Tasks",
                description="Break design into ordered, reviewable tasks.",
            ),
        ],
    )


def sdd_verifier_card(settings: RuntimeSettings) -> NervAgentCard:
    return NervAgentCard(
        name="n3rv-sdd-verifier",
        description="Verify the implementation against the spec's acceptance criteria. Produces a pass/fail verdict.",
        url=f"{settings.a2a_base_url}/agents/sdd-verifier",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="sdd-verify",
                name="SDD Verify",
                description="Verify implementation against spec acceptance criteria.",
            ),
        ],
    )


def sdd_archiver_card(settings: RuntimeSettings) -> NervAgentCard:
    return NervAgentCard(
        name="n3rv-sdd-archiver",
        description="Archive all SDD artifacts for a change as a single completed record in memory.",
        url=f"{settings.a2a_base_url}/agents/sdd-archiver",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="sdd-archive",
                name="SDD Archive",
                description="Persist completed SDD records to memory.",
            ),
        ],
    )


def default_agent_cards(settings: RuntimeSettings) -> dict[str, NervAgentCard]:
    return {
        "hub": hub_agent_card(settings),
        "opencode": opencode_agent_card(settings),
        "sdd-explorer": sdd_explorer_card(settings),
        "sdd-proposer": sdd_proposer_card(settings),
        "sdd-speccer": sdd_speccer_card(settings),
        "sdd-designer": sdd_designer_card(settings),
        "sdd-task-planner": sdd_task_planner_card(settings),
        "sdd-verifier": sdd_verifier_card(settings),
        "sdd-archiver": sdd_archiver_card(settings),
    }


def load_agent_cards(
    settings: RuntimeSettings,
    org_config_path: Path | None = None,
) -> dict[str, NervAgentCard]:
    """Load agent cards.

    Without *org_config_path*, returns the default 9 infrastructure cards.
    With a valid *org_config_path*, extends with satellite agent cards
    discovered from the org config.
    """
    cards = default_agent_cards(settings)
    if org_config_path is not None:
        try:
            from n3rv.org import OrgConfig

            org = OrgConfig.from_yaml(org_config_path)
            config_dir = org_config_path.parent.parent
            satellite_cards = org.discover_satellite_cards(config_dir)
            for card in satellite_cards:
                cards[card.name] = card
            logger.info(
                "loaded %d satellite agent cards from %s",
                len(satellite_cards),
                org_config_path,
            )
        except Exception as exc:
            logger.warning("Failed to load org agent cards from %s: %s", org_config_path, exc)
    return cards
