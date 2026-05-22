"""中国统帅部 Agent（规则 Bot，可接玩家诏令）。"""

from __future__ import annotations

from engine.agents.base import AgentDecision, BaseAgent
from engine.observation import FactionObservation
from engine.schemas import (
    AdvanceFrontAction,
    FactionId,
    HoldGarrisonAction,
    SeekAlliedAidAction,
)
from engine.state import GameState
from engine.verifier import verify_action


class ChinaRuleAgent(BaseAgent):
    faction = FactionId.CHINA

    async def decide(
        self, observation: FactionObservation, state: GameState
    ) -> AgentDecision:
        actions: list = []
        parts: list[str] = []

        for ad in observation.active_directives:
            parts.append(f"诏令[{ad.directive.priority}]剩余{ad.turns_left}回合")

        if state.get_region("central_china").owner == FactionId.JAPAN and state.owns(
            FactionId.CHINA, "jiangxi"
        ):
            actions.append(
                AdvanceFrontAction(
                    faction=FactionId.CHINA,
                    from_region="jiangxi",
                    to_region="central_china",
                )
            )
            parts.append("反攻华中")

        actions.append(
            HoldGarrisonAction(faction=FactionId.CHINA, region="southwest_china")
        )
        parts.append("巩固西南大后方")

        priority = _directive_priority(observation)
        if priority == "hold_burma" or state.turn % 3 == 0:
            if state.turn >= 4:
                actions.append(SeekAlliedAidAction(faction=FactionId.CHINA))
                parts.append("寻求同盟援助")

        valid = [a for a in actions if verify_action(state, a).accepted]

        return AgentDecision(
            faction=FactionId.CHINA,
            actions=valid,
            reasoning="；".join(parts) or "持久战",
            observation=observation,
        )


def _directive_priority(observation: FactionObservation) -> str | None:
    if not observation.active_directives:
        return None
    return observation.active_directives[0].directive.priority
