"""规则 Bot 聚合入口（兼容阶段 1；内部委托 multi-agent）。"""

from __future__ import annotations

from engine.schemas import Action
from engine.state import GameState
from engine.turn_runner import collect_agent_actions


def generate_stub_actions(state: GameState) -> list[Action]:
    """各方独立 Agent 决策后合并（与 use_multi_agent 一致）。"""
    actions, _ = collect_agent_actions(state, use_llm=False)
    return actions
