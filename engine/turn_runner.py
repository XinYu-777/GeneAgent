"""并行调度各方 Agent，写入 trace。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from engine.agents.base import AgentDecision, BaseAgent, write_trace
from engine.agents.china import ChinaRuleAgent
from engine.agents.cpc import CPCRuleAgent
from engine.agents.japan import JapanRuleAgent
from engine.agents.soviet import SovietRuleAgent
from engine.observation import project
from engine.schemas import Action, FactionId
from engine.state import GameState

DEFAULT_AGENT_FACTIONS = (
    FactionId.JAPAN,
    FactionId.CHINA,
    FactionId.CPC,
    FactionId.SOVIET,
)


def create_default_agents(*, use_llm: bool = False) -> list[BaseAgent]:
    """四国独立 Agent；use_llm 时无 Key 仍回退规则 Bot。"""
    from engine.agents.base import LLMAgent

    factories = {
        FactionId.JAPAN: JapanRuleAgent,
        FactionId.CHINA: ChinaRuleAgent,
        FactionId.CPC: CPCRuleAgent,
        FactionId.SOVIET: SovietRuleAgent,
    }
    agents: list[BaseAgent] = []
    for fid in DEFAULT_AGENT_FACTIONS:
        rule = factories[fid]()
        if use_llm:
            agents.append(LLMAgent(fid, rule))
        else:
            agents.append(rule)
    return agents


async def collect_agent_decisions(
    state: GameState,
    agents: list[BaseAgent],
    *,
    trace_dir: Path | None = None,
) -> list[AgentDecision]:
    """并行调用各 Agent（asyncio.gather）。"""

    async def _one(agent: BaseAgent) -> AgentDecision:
        obs = project(state, agent.faction)
        decision = await agent.decide(obs, state)
        write_trace(decision, state.turn, trace_dir)
        return decision

    return list(await asyncio.gather(*[_one(a) for a in agents]))


def collect_agent_actions(
    state: GameState,
    agents: list[BaseAgent] | None = None,
    *,
    use_llm: bool = False,
    trace_dir: Path | None = None,
) -> tuple[list[Action], list[AgentDecision]]:
    """同步入口：收集各方行动列表。"""
    roster = agents or create_default_agents(use_llm=use_llm)
    decisions = asyncio.run(
        collect_agent_decisions(state, roster, trace_dir=trace_dir)
    )
    actions: list[Action] = []
    for d in decisions:
        actions.extend(d.actions)
    return actions, decisions
