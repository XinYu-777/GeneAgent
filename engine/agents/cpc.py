"""中共根据地 Agent（规则 Bot）。"""

from __future__ import annotations

from engine.agents.base import AgentDecision, BaseAgent
from engine.directives import primary_directive
from engine.observation import FactionObservation
from engine.schemas import FactionId, GuerrillaOperationAction
from engine.state import GameState
from engine.verifier import verify_action


class CPCRuleAgent(BaseAgent):
    faction = FactionId.CPC

    async def decide(
        self, observation: FactionObservation, state: GameState
    ) -> AgentDecision:
        actions: list = []
        china_d = primary_directive(state)
        targets = ["north_china", "east_china", "central_china", "fujian"]

        if china_d and china_d.priority == "guerrilla_expand":
            for tid in targets:
                if state.get_region(tid).owner == FactionId.JAPAN:
                    actions.append(
                        GuerrillaOperationAction(faction=FactionId.CPC, region=tid)
                    )
            reasoning = "响应统帅部游击战略，多线敌后牵制"
        else:
            for tid in targets:
                if state.get_region(tid).owner == FactionId.JAPAN:
                    actions.append(
                        GuerrillaOperationAction(faction=FactionId.CPC, region=tid)
                    )
                    break
            reasoning = "敌后游击牵制" if actions else "根据地巩固"

        valid = [a for a in actions if verify_action(state, a).accepted]
        return AgentDecision(
            faction=FactionId.CPC,
            actions=valid,
            reasoning=reasoning,
            observation=observation,
        )
