"""Agent 基类与 DeepSeek / Mock。"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.agents.llm_parse import parse_llm_response
from engine.agents.prompts import FACTION_SYSTEM, build_user_prompt
from engine.llm_client import chat_json, is_llm_configured
from engine.observation import FactionObservation
from engine.schemas import Action, FactionId
from engine.state import GameState

logger = logging.getLogger(__name__)

TRACE_DIR = Path(__file__).resolve().parent.parent.parent / "traces"


@dataclass
class AgentDecision:
    faction: FactionId
    actions: list[Action]
    reasoning: str
    observation: FactionObservation
    llm_model: str | None = None

    def to_trace_dict(self, turn: int) -> dict[str, Any]:
        out: dict[str, Any] = {
            "turn": turn,
            "faction": self.faction.value,
            "reasoning": self.reasoning,
            "actions": [a.model_dump(mode="json") for a in self.actions],
            "observation": self.observation.model_dump_for_trace(),
        }
        if self.llm_model:
            out["llm_model"] = self.llm_model
        return out


class BaseAgent(ABC):
    faction: FactionId

    @abstractmethod
    async def decide(
        self, observation: FactionObservation, state: GameState
    ) -> AgentDecision:
        ...


def write_trace(decision: AgentDecision, turn: int, trace_dir: Path | None = None) -> Path:
    root = trace_dir or TRACE_DIR
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{turn}_{decision.faction.value}.json"
    path.write_text(
        json.dumps(decision.to_trace_dict(turn), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


class MockAgent(BaseAgent):
    """测试用：各方返回可辨识的固定行动意图。"""

    def __init__(self, faction: FactionId):
        self.faction = faction

    async def decide(
        self, observation: FactionObservation, state: GameState
    ) -> AgentDecision:
        from engine.agents.china import ChinaRuleAgent
        from engine.agents.cpc import CPCRuleAgent
        from engine.agents.japan import JapanRuleAgent
        from engine.agents.soviet import SovietRuleAgent

        agents = {
            FactionId.JAPAN: JapanRuleAgent(),
            FactionId.CHINA: ChinaRuleAgent(),
            FactionId.CPC: CPCRuleAgent(),
            FactionId.SOVIET: SovietRuleAgent(),
        }
        delegate = agents.get(self.faction)
        if delegate:
            decision = await delegate.decide(observation, state)
            return AgentDecision(
                faction=self.faction,
                actions=decision.actions,
                reasoning=f"[mock] {decision.reasoning}",
                observation=observation,
            )
        return AgentDecision(
            faction=self.faction,
            actions=[],
            reasoning="[mock] 无行动",
            observation=observation,
        )


class LLMAgent(BaseAgent):
    """DeepSeek 决策；失败或未配置 Key 时回退规则 Bot。"""

    def __init__(self, faction: FactionId, fallback: BaseAgent):
        self.faction = faction
        self.fallback = fallback

    async def decide(
        self, observation: FactionObservation, state: GameState
    ) -> AgentDecision:
        if not is_llm_configured():
            decision = await self.fallback.decide(observation, state)
            return AgentDecision(
                faction=self.faction,
                actions=decision.actions,
                reasoning=f"[deepseek-fallback] {decision.reasoning}",
                observation=observation,
            )

        from engine.llm_client import get_model

        try:
            obs_json = json.dumps(
                observation.model_dump_for_trace(),
                ensure_ascii=False,
                indent=2,
            )
            system = FACTION_SYSTEM[self.faction]
            user = build_user_prompt(obs_json, state.turn)
            payload = await chat_json(system, user)
            reasoning, actions = parse_llm_response(
                payload, self.faction, state
            )
            if not actions:
                fb = await self.fallback.decide(observation, state)
                actions = fb.actions
                reasoning = f"{reasoning}；LLM 无合法行动，回退规则：{fb.reasoning}"

            return AgentDecision(
                faction=self.faction,
                actions=actions,
                reasoning=f"[deepseek] {reasoning}",
                observation=observation,
                llm_model=get_model(),
            )
        except Exception as exc:
            logger.warning("DeepSeek 调用失败 %s: %s", self.faction.value, exc)
            decision = await self.fallback.decide(observation, state)
            return AgentDecision(
                faction=self.faction,
                actions=decision.actions,
                reasoning=f"[deepseek-error] {exc} | {decision.reasoning}",
                observation=observation,
            )
