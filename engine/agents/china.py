"""中国统帅部 Agent（遵循玩家战略诏令）。"""

from __future__ import annotations

from engine.agents.base import AgentDecision, BaseAgent
from engine.directives import primary_directive
from engine.observation import FactionObservation
from engine.schemas import (
    Action,
    AdvanceFrontAction,
    FactionId,
    HoldGarrisonAction,
    RouteStatus,
    SeekAlliedAidAction,
)
from engine.state import GameState
from engine.verifier import verify_action


class ChinaRuleAgent(BaseAgent):
    faction = FactionId.CHINA

    async def decide(
        self, observation: FactionObservation, state: GameState
    ) -> AgentDecision:
        directive = primary_directive(state)
        if directive:
            actions, parts = _actions_from_directive(directive, state)
        else:
            actions, parts = _default_actions(state)

        for ad in observation.active_directives:
            parts.insert(
                0,
                f"【诏令·{ad.directive.priority}】剩余{ad.turns_left}回合"
                + (f"：「{ad.directive.raw_quote[:40]}」" if ad.directive.raw_quote else ""),
            )

        valid = [a for a in actions if verify_action(state, a).accepted]
        return AgentDecision(
            faction=FactionId.CHINA,
            actions=valid,
            reasoning="；".join(parts) or "持久战",
            observation=observation,
        )


def _actions_from_directive(
    directive, state: GameState
) -> tuple[list[Action], list[str]]:
    p = directive.priority
    parts: list[str] = [f"执行战略：{p}"]

    if p == "hold_core":
        regions = ["southwest_china", "central_china", "south_china"]
        actions = [
            HoldGarrisonAction(faction=FactionId.CHINA, region=r)
            for r in regions
            if state.owns(FactionId.CHINA, r)
        ][:2]
        parts.append("全力巩固大后方，不主动进攻")
        return actions, parts

    if p == "hold_burma":
        actions: list[Action] = [
            SeekAlliedAidAction(faction=FactionId.CHINA),
        ]
        for r in ("yunnan", "southwest_china"):
            if state.owns(FactionId.CHINA, r):
                actions.append(
                    HoldGarrisonAction(faction=FactionId.CHINA, region=r)
                )
        if state.routes.get("burma_road") == RouteStatus.CUT:
            parts.append("滇缅线危急，优先求援")
        else:
            parts.append("巩固滇缅方向")
        return actions, parts

    if p == "guerrilla_expand":
        actions = [
            HoldGarrisonAction(faction=FactionId.CHINA, region="southwest_china"),
            SeekAlliedAidAction(faction=FactionId.CHINA),
        ]
        parts.append("正面牵制+国际援助，敌后由中共扩展")
        return actions, parts

    if p == "seek_allied_aid":
        actions = [SeekAlliedAidAction(faction=FactionId.CHINA)]
        if state.owns(FactionId.CHINA, "southwest_china"):
            actions.append(
                HoldGarrisonAction(faction=FactionId.CHINA, region="southwest_china")
            )
        parts.append("外交求援为主")
        return actions, parts

    if p == "counteroffensive_huabei":
        actions = []
        if (
            state.get_region("central_china").owner == FactionId.JAPAN
            and state.owns(FactionId.CHINA, "jiangxi")
        ):
            actions.append(
                AdvanceFrontAction(
                    faction=FactionId.CHINA,
                    from_region="jiangxi",
                    to_region="central_china",
                )
            )
        for r in ("north_china", "northwest_china"):
            if state.owns(FactionId.CHINA, r):
                actions.append(
                    HoldGarrisonAction(faction=FactionId.CHINA, region=r)
                )
        if not any(isinstance(a, AdvanceFrontAction) for a in actions):
            actions.append(SeekAlliedAidAction(faction=FactionId.CHINA))
        parts.append("有限反击，华北施压")
        return actions, parts

    return _default_actions(state)


def _default_actions(state: GameState) -> tuple[list[Action], list[str]]:
    actions: list[Action] = []
    parts: list[str] = []

    if (
        state.get_region("central_china").owner == FactionId.JAPAN
        and state.owns(FactionId.CHINA, "jiangxi")
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
    if state.turn >= 4 and state.turn % 3 == 0:
        actions.append(SeekAlliedAidAction(faction=FactionId.CHINA))
    return actions, parts
