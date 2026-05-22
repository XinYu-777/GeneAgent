"""日本大本营 Agent（规则 Bot）。"""

from __future__ import annotations

from engine.agents.base import AgentDecision, BaseAgent
from engine.observation import FactionObservation
from engine.schemas import (
    AdvanceFrontAction,
    FactionId,
    PacificStrikeAction,
    RaidSupplyAction,
    RouteStatus,
)
from engine.state import GameState
from engine.verifier import verify_action


class JapanRuleAgent(BaseAgent):
    faction = FactionId.JAPAN

    async def decide(
        self, observation: FactionObservation, state: GameState
    ) -> AgentDecision:
        actions: list = []
        reasoning_parts: list[str] = []

        if state.owns(FactionId.JAPAN, "east_china"):
            target_owner = state.get_region("central_china").owner
            if target_owner != FactionId.JAPAN:
                actions.append(
                    AdvanceFrontAction(
                        faction=FactionId.JAPAN,
                        from_region="east_china",
                        to_region="central_china",
                    )
                )
                reasoning_parts.append("华东向华中推进")

        if state.turn >= 6 and state.routes.get("burma_road") == RouteStatus.OPEN:
            actions.append(
                RaidSupplyAction(faction=FactionId.JAPAN, route_id="burma_road")
            )
            reasoning_parts.append("切断援华交通线")

        if state.turn >= 7 and not state.owns(FactionId.JAPAN, "philippines"):
            actions.append(
                PacificStrikeAction(
                    faction=FactionId.JAPAN, target_region="philippines"
                )
            )
            reasoning_parts.append("南进菲律宾")

        valid = [a for a in actions if verify_action(state, a).accepted]

        intel = [
            r
            for r in observation.regions
            if r.owner == FactionId.CHINA and r.intel_quality == "estimate"
        ]
        if intel:
            reasoning_parts.append(f"对华情报估计区 {len(intel)} 个")

        return AgentDecision(
            faction=FactionId.JAPAN,
            actions=valid,
            reasoning="；".join(reasoning_parts) or "维持现状",
            observation=observation,
        )
