from __future__ import annotations

from pathlib import Path

import yaml

from n3rverberage.a2a.agent_cards import (
    default_agent_cards,
    hub_agent_card,
    load_agent_cards,
    opencode_agent_card,
    sdd_archiver_card,
    sdd_designer_card,
    sdd_explorer_card,
    sdd_proposer_card,
    sdd_speccer_card,
    sdd_task_planner_card,
    sdd_verifier_card,
)

SDD_AGENTS = {
    "sdd-explorer",
    "sdd-proposer",
    "sdd-speccer",
    "sdd-designer",
    "sdd-task-planner",
    "sdd-verifier",
    "sdd-archiver",
}


def test_default_agent_cards(runtime_settings) -> None:
    cards = default_agent_cards(runtime_settings)

    expected = {"hub", "opencode"} | SDD_AGENTS
    assert set(cards) == expected
    assert cards["hub"].name == "n3rverberage-hub"
    assert cards["opencode"].skills[0].id == "implementation"
    assert cards["hub"].capabilities.model_dump() == {"streaming": True}
    assert "authentication" not in cards["hub"].model_dump()


def test_card_urls_are_localhost(runtime_settings) -> None:
    assert str(hub_agent_card(runtime_settings).url).rstrip("/") == runtime_settings.a2a_base_url
    assert str(opencode_agent_card(runtime_settings).url).startswith(f"{runtime_settings.a2a_base_url}/")


def test_sdd_explorer_card(runtime_settings) -> None:
    card = sdd_explorer_card(runtime_settings)
    assert card.name == "n3rverberage-sdd-explorer"
    assert len(card.skills) == 1
    assert card.skills[0].id == "sdd-explore"
    assert not card.capabilities.streaming


def test_sdd_proposer_card(runtime_settings) -> None:
    card = sdd_proposer_card(runtime_settings)
    assert card.name == "n3rverberage-sdd-proposer"
    assert card.skills[0].id == "sdd-propose"


def test_sdd_speccer_card(runtime_settings) -> None:
    card = sdd_speccer_card(runtime_settings)
    assert card.name == "n3rverberage-sdd-speccer"
    assert card.skills[0].id == "sdd-spec"


def test_sdd_designer_card(runtime_settings) -> None:
    card = sdd_designer_card(runtime_settings)
    assert card.name == "n3rverberage-sdd-designer"
    assert card.skills[0].id == "sdd-design"


def test_sdd_task_planner_card(runtime_settings) -> None:
    card = sdd_task_planner_card(runtime_settings)
    assert card.name == "n3rverberage-sdd-task-planner"
    assert card.skills[0].id == "sdd-tasks"


def test_sdd_verifier_card(runtime_settings) -> None:
    card = sdd_verifier_card(runtime_settings)
    assert card.name == "n3rverberage-sdd-verifier"
    assert card.skills[0].id == "sdd-verify"


def test_sdd_archiver_card(runtime_settings) -> None:
    card = sdd_archiver_card(runtime_settings)
    assert card.name == "n3rverberage-sdd-archiver"
    assert card.skills[0].id == "sdd-archive"


def test_sdd_cards_have_valid_urls(runtime_settings) -> None:
    factories = [
        sdd_explorer_card,
        sdd_proposer_card,
        sdd_speccer_card,
        sdd_designer_card,
        sdd_task_planner_card,
        sdd_verifier_card,
        sdd_archiver_card,
    ]
    for factory in factories:
        card = factory(runtime_settings)
        assert str(card.url).startswith(str(runtime_settings.a2a_base_url))


def test_sdd_cards_present_in_default(runtime_settings) -> None:
    cards = default_agent_cards(runtime_settings)
    for agent_id in SDD_AGENTS:
        assert agent_id in cards, f"Missing SDD agent card: {agent_id}"
        assert cards[agent_id].skills, f"SDD card {agent_id} has no skills"
        assert cards[agent_id].name, f"SDD card {agent_id} has no name"


# --------------------------------------------------------------------------- #
# Hybrid discovery (org-aware)
# --------------------------------------------------------------------------- #


def test_load_without_org_config_returns_only_infra(runtime_settings) -> None:
    """Without org_config_path, only 9 infrastructure cards are returned."""
    cards = load_agent_cards(runtime_settings)
    expected = {"hub", "opencode"} | SDD_AGENTS
    assert set(cards) == expected


def test_load_with_org_config_adds_satellite_cards(runtime_settings, tmp_path: Path) -> None:
    """With valid org config, satellite cards are added."""
    from n3rverberage.org import OrgConfig, OrgProject

    # Create a satellite with a2a-config.yaml
    sat_path = tmp_path / "satellites" / "transcriber"
    (sat_path / ".n3rverberage").mkdir(parents=True)
    a2a_config = {"project": "transcriber", "hub": {"host": "127.0.0.1", "port": 19821}}
    (sat_path / ".n3rverberage" / "a2a-config.yaml").write_text(yaml.safe_dump(a2a_config), encoding="utf-8")

    # Create org config
    config = OrgConfig(
        projects=[
            OrgProject(
                name="transcriber",
                path=Path("satellites/transcriber"),
                type="satellite",
            ),
        ]
    )
    config_path = tmp_path / ".n3rverberage" / "org-config.yaml"
    config.to_yaml(config_path)

    cards = load_agent_cards(runtime_settings, org_config_path=config_path)
    assert "n3rverberage-transcriber" in cards
    assert cards["n3rverberage-transcriber"].name == "n3rverberage-transcriber"

    # Infrastructure cards still present
    assert "hub" in cards
    assert "opencode" in cards


def test_load_with_invalid_org_config_returns_only_infra(runtime_settings, tmp_path: Path) -> None:
    """Invalid org config path logs warning and returns 9 infra cards."""
    bad_path = tmp_path / "nonexistent.yaml"
    cards = load_agent_cards(runtime_settings, org_config_path=bad_path)
    expected = {"hub", "opencode"} | SDD_AGENTS
    assert set(cards) == expected


def test_load_with_empty_org_config_returns_only_infra(runtime_settings, tmp_path: Path) -> None:
    """Org config with no satellites returns 9 infra cards only."""
    from n3rverberage.org import OrgConfig

    config = OrgConfig()
    config_path = tmp_path / ".n3rverberage" / "org-config.yaml"
    config.to_yaml(config_path)

    cards = load_agent_cards(runtime_settings, org_config_path=config_path)
    expected = {"hub", "opencode"} | SDD_AGENTS
    assert set(cards) == expected
