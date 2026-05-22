"""阶段 2 Multi-Agent 验收测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.agents.base import MockAgent
from engine.observation import japan_cannot_see_china_true_garrison, project
from engine.schemas import FactionId, StrategicDirective
from engine.schemas import ActiveDirective
from engine.turn import GameSession
from engine.turn_runner import (
    DEFAULT_AGENT_FACTIONS,
    collect_agent_actions,
    collect_agent_decisions,
    create_default_agents,
)

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "scenarios" / "1941.yaml"


class TestObservation:
    def test_japan_sees_china_garrison_as_estimate(self):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        assert japan_cannot_see_china_true_garrison(session.state, "central_china")

    def test_china_sees_own_regions_confirmed(self):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        obs = project(session.state, FactionId.CHINA)
        sw = next(r for r in obs.regions if r.id == "southwest_china")
        assert sw.intel_quality == "confirmed"
        assert sw.garrison_estimate == session.state.get_region("southwest_china").garrison

    def test_china_observation_includes_active_directives(self):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        session.state.active_directives = [
            ActiveDirective(
                directive=StrategicDirective(
                    priority="hold_burma", duration_turns=3
                ),
                turns_left=3,
            )
        ]
        obs = project(session.state, FactionId.CHINA)
        assert len(obs.active_directives) == 1
        obs_jp = project(session.state, FactionId.JAPAN)
        assert len(obs_jp.active_directives) == 0


class TestTurnRunner:
    def test_parallel_decisions_three_plus_factions(self, tmp_path: Path):
        import asyncio

        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        agents = create_default_agents(use_llm=False)
        decisions = asyncio.run(
            collect_agent_decisions(session.state, agents, trace_dir=tmp_path)
        )
        assert len(decisions) == len(DEFAULT_AGENT_FACTIONS)
        factions_with_actions = {d.faction for d in decisions if d.actions}
        assert len(factions_with_actions) >= 3

    def test_trace_files_written(self, tmp_path: Path):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        collect_agent_actions(session.state, trace_dir=tmp_path)
        traces = list(tmp_path.glob("0_*.json"))
        assert len(traces) == 4
        sample = json.loads(traces[0].read_text(encoding="utf-8"))
        assert "faction" in sample
        assert "actions" in sample
        assert "observation" in sample

    def test_mock_agent_without_llm(self, tmp_path: Path):
        session = GameSession.new(SCENARIO, resolve_all_decisions=True)
        agents = [MockAgent(f) for f in DEFAULT_AGENT_FACTIONS]
        actions, decisions = collect_agent_actions(
            session.state, agents, trace_dir=tmp_path
        )
        assert isinstance(actions, list)
        assert all("[mock]" in d.reasoning for d in decisions)


class TestSessionMultiAgent:
    def test_advance_turn_use_multi_agent_10_rounds(self, tmp_path: Path):
        session = GameSession.new(
            SCENARIO,
            resolve_all_decisions=True,
            trace_dir=tmp_path,
        )
        for t in range(10):
            snap = session.advance_turn(use_multi_agent=True)
            assert snap.turn == t + 1
        assert session.state.turn == 10
        assert len(list(tmp_path.glob("*.json"))) >= 4
