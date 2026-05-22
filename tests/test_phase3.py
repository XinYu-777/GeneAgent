"""阶段 3：玩家决断链路验收。"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.agents.china import ChinaRuleAgent
from engine.directives import primary_directive
from engine.observation import project
from engine.player_intent import DirectiveRejectError, parse_player_input
from engine.schemas import Action, AdvanceFrontAction, FactionId, HoldGarrisonAction
from engine.turn import GameSession, PendingDecisionError

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "scenarios" / "1941.yaml"


class TestPlayerDecision:
    def test_opening_decision_by_intent(self):
        session = GameSession.new(SCENARIO)
        assert session.get_pending_decision_point().id == "dp_opening_strategy"
        d, summary = session.submit_player_decision(
            intent_id="hold_core", text="巩固西南"
        )
        assert d.priority == "hold_core"
        assert "hold_core" in summary or "国力" in summary or "诏令" in summary
        assert not session.has_pending_decision()
        assert len(session.state.active_directives) == 1

    def test_reject_illegal_nl(self):
        session = GameSession.new(SCENARIO)
        with pytest.raises(DirectiveRejectError):
            session.submit_player_decision(text="立刻占领东京，一年灭日")

    def test_cannot_advance_with_pending_decision(self):
        session = GameSession.new(SCENARIO)
        with pytest.raises(PendingDecisionError):
            session.advance_turn(use_multi_agent=False)

    def test_hold_core_changes_china_actions(self):
        session = GameSession.new(SCENARIO)
        session.submit_player_decision(intent_id="hold_core")
        import asyncio

        obs = project(session.state, FactionId.CHINA)
        decision = asyncio.run(
            ChinaRuleAgent().decide(obs, session.state)
        )
        assert decision.actions
        assert all(
            isinstance(a, HoldGarrisonAction) for a in decision.actions
        )
        assert not any(isinstance(a, AdvanceFrontAction) for a in decision.actions)

    def test_counteroffensive_allows_advance(self):
        session = GameSession.new(SCENARIO)
        session.submit_player_decision(intent_id="hold_core")
        session.state.resolved_decision_ids.add("dp_post_pearl_harbor")
        session.state.fired_events.update(
            {"evt_pearl_harbor", "evt_china_1944_pressure"}
        )
        session.state.turn = 28
        assert session.get_pending_decision_point().id == "dp_1944_crisis"
        session.submit_player_decision(intent_id="counteroffensive_huabei")
        session.state.get_region("central_china").owner = FactionId.JAPAN
        import asyncio

        obs = project(session.state, FactionId.CHINA)
        decision = asyncio.run(ChinaRuleAgent().decide(obs, session.state))
        assert any(isinstance(a, AdvanceFrontAction) for a in decision.actions)

    def test_guerrilla_boosts_cpc(self):
        session = GameSession.new(SCENARIO)
        session.submit_player_decision(intent_id="guerrilla_expand")
        assert primary_directive(session.state).priority == "guerrilla_expand"
        from engine.agents.cpc import CPCRuleAgent

        import asyncio

        obs = project(session.state, FactionId.CPC)
        d = asyncio.run(CPCRuleAgent().decide(obs, session.state))
        assert len(d.actions) >= 1

    def test_three_decisions_lifecycle(self):
        session = GameSession.new(SCENARIO, use_llm_agents=False)
        session.submit_player_decision(intent_id="guerrilla_expand")
        for _ in range(6):
            session.advance_turn(use_stub_ai=True)
        assert "evt_pearl_harbor" in session.state.fired_events
        assert session.get_pending_decision_point().id == "dp_post_pearl_harbor"
        session.submit_player_decision(intent_id="hold_burma")
        for _ in range(22):
            if session.has_pending_decision():
                break
            session.advance_turn(use_stub_ai=True)
        assert session.get_pending_decision_point().id == "dp_1944_crisis"

    def test_nl_maps_to_burma_keywords(self):
        dp = GameSession.new(SCENARIO).get_pending_decision_point()
        session = GameSession.new(SCENARIO)
        session.resolve_decision("dp_opening_strategy")  # clear opening
        session.state.turn = 6
        session.state.fired_events.add("evt_pearl_harbor")
        dp2 = session.get_pending_decision_point()
        assert dp2.id == "dp_post_pearl_harbor"
        d = parse_player_input(
            dp2, text="不惜代价保住滇缅公路和缅甸交通线"
        )
        assert d.priority == "hold_burma"
