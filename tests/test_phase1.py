"""阶段 1 验收测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.merger import merge_actions
from engine.schemas import (
    AdvanceFrontAction,
    FactionId,
    SovietInvasionAction,
)
from engine.turn import GameSession, PendingDecisionError
from engine.verifier import verify_action
from engine.world import load_scenario

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "scenarios" / "1941.yaml"


class TestAdvanceTurn:
    def test_advance_10_turns_with_stub_ai(self):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        for _ in range(10):
            snap = session.advance_turn(use_stub_ai=True)
        assert session.state.turn == 10
        assert snap.turn == 10
        assert len(snap.actions_played) >= 0

    def test_pending_decision_blocks_advance(self):
        session = GameSession.new(SCENARIO)
        assert session.has_pending_decision()
        with pytest.raises(PendingDecisionError):
            session.advance_turn(use_stub_ai=True)

    def test_resolve_decision_then_advance(self):
        session = GameSession.new(SCENARIO)
        session.resolve_decision("dp_opening_strategy")
        snap = session.advance_turn(use_stub_ai=True)
        assert snap.turn == 1


class TestVerifier:
    def test_rejects_non_neighbor_advance(self):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        bad = AdvanceFrontAction(
            faction=FactionId.CHINA,
            from_region="southwest_china",
            to_region="japan_home",
        )
        result = verify_action(session.state, bad)
        assert not result.accepted
        assert "不相邻" in (result.message or "")

    def test_rejects_soviet_invasion_before_1945(self):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        session.state.turn = 10
        bad = SovietInvasionAction(
            faction=FactionId.SOVIET, target_region="manchuria"
        )
        result = verify_action(session.state, bad)
        assert not result.accepted


class TestMerger:
    def test_contest_same_region_one_loser(self):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        state = session.state
        # 设为各方可争夺的第三方控制区
        state.get_region("central_china").owner = FactionId.NEUTRAL
        japan = AdvanceFrontAction(
            faction=FactionId.JAPAN,
            from_region="east_china",
            to_region="central_china",
        )
        china = AdvanceFrontAction(
            faction=FactionId.CHINA,
            from_region="jiangxi",
            to_region="central_china",
        )
        resolved = merge_actions(state, [japan, china])
        central = [r for r in resolved if _targets(r.action) == "central_china"]
        accepted = [r for r in central if r.accepted]
        rejected = [r for r in central if not r.accepted]
        assert len(accepted) == 1
        assert len(rejected) == 1
        assert "合并否决" in (rejected[0].message or "")

    def test_illegal_action_rejected_in_merge(self):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        bad = AdvanceFrontAction(
            faction=FactionId.CHINA,
            from_region="southwest_china",
            to_region="japan_home",
        )
        resolved = merge_actions(session.state, [bad])
        assert len(resolved) == 1
        assert not resolved[0].accepted


def _targets(action) -> str | None:
    if isinstance(action, AdvanceFrontAction):
        return action.to_region
    return getattr(action, "target_region", None)


class TestEvents:
    def test_pearl_harbor_fires_on_turn_6(self):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        for _ in range(6):
            session.advance_turn(use_stub_ai=True)
        assert "evt_pearl_harbor" in session.state.fired_events
