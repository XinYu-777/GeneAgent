"""苏联远东 Agent（规则 Bot）。"""

from __future__ import annotations

from engine.agents.base import AgentDecision, BaseAgent
from engine.observation import FactionObservation
from engine.schemas import FactionId, SovietInvasionAction
from engine.state import GameState
from engine.verifier import verify_action


class SovietRuleAgent(BaseAgent):
    faction = FactionId.SOVIET

    async def decide(
        self, observation: FactionObservation, state: GameState
    ) -> AgentDecision:
        actions: list = []
        if state.turn >= 38 or "evt_soviet_invasion" in state.fired_events:
            if state.owns(FactionId.JAPAN, "manchuria"):
                actions.append(
                    SovietInvasionAction(
                        faction=FactionId.SOVIET, target_region="manchuria"
                    )
                )

        valid = [a for a in actions if verify_action(state, a).accepted]
        return AgentDecision(
            faction=FactionId.SOVIET,
            actions=valid,
            reasoning="远东军入关" if valid else "苏日中立，远东观望",
            observation=observation,
        )
