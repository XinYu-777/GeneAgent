"""DeepSeek 集成测试（默认 mock，不消耗 API）。"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from engine.agents.base import LLMAgent
from engine.agents.china import ChinaRuleAgent
from engine.llm_client import is_llm_configured
from engine.observation import project
from engine.schemas import FactionId, HoldGarrisonAction
from engine.turn import GameSession

ROOT = Path(__file__).resolve().parent.parent
SCENARIO = ROOT / "scenarios" / "1941.yaml"


def test_llm_agent_uses_deepseek_response(monkeypatch):
    import asyncio

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-fake")

    async def fake_chat(system: str, user: str) -> dict:
        return {
            "reasoning": "巩固西南",
            "actions": [
                {
                    "type": "hold_garrison",
                    "faction": "china",
                    "region": "southwest_china",
                }
            ],
        }

    monkeypatch.setattr("engine.agents.base.chat_json", fake_chat)

    session = GameSession.new(SCENARIO, resolve_all_decisions=True)
    obs = project(session.state, FactionId.CHINA)
    agent = LLMAgent(FactionId.CHINA, ChinaRuleAgent())

    async def _run():
        return await agent.decide(obs, session.state)

    decision = asyncio.run(_run())

    assert "[deepseek]" in decision.reasoning
    assert len(decision.actions) == 1
    assert isinstance(decision.actions[0], HoldGarrisonAction)
    assert decision.llm_model is not None


def test_is_llm_configured_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert not is_llm_configured()


def test_is_llm_configured_with_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    assert is_llm_configured()
